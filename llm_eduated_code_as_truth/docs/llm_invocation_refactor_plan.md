# 大模型调用层重构方案（本地模型 / 本地 API / 在线 OpenAI 客户端统一）

## 1. 问题诊断（基于当前代码）

当前仓库存在两套 provider 体系（`llm_providers/` 与 `llm_providers_new/`）并行，且脚本入口较多，导致调用链不一致、配置分散、错误处理策略不统一。

### 1.1 主要风险点

1. **双栈并存且接口不完全一致**
   - 旧实现：`llm_providers/local_batch.py`、`llm_providers/remote_api.py`。
   - 新实现：`llm_providers_new/base.py` + `llm_providers_new/remote_api.py` + `llm_providers_new/local_batch.py`。
   - 这会导致不同脚本导入不同 provider，出现“同名能力、不同语义”。

2. **异步 / 同步边界混乱**
   - 新接口是统一 async（`BaseLLMProvider`），但仍有大量脚本以同步方式组织流程。
   - 容易出现 event loop 管理问题、并发参数失控，或超时重试行为不一致。

3. **超时、重试、限流策略未统一收敛**
   - 各 provider 内部自行处理异常并直接返回错误字符串，调用方难以准确判断是业务失败还是网络失败。
   - `batch_size`、`request_timeout`、`max_retries` 在不同通路表现不一致。

4. **“思考模式/JSON模式”控制分散**
   - `enable_thinking`、`/no_think`、`response_format`、`chat_template_kwargs` 等逻辑散落在实现里。
   - 结果是模型切换时，行为漂移明显（例如同样请求在本地与在线模型输出格式不同）。

5. **配置模型命名与用途耦合**
   - `config.py` 中 provider 配置项较多且风格不同，脚本若直接拼装参数容易偏离标准配置。

---

## 2. 重构目标

1. **单一调用入口**：所有上层业务只依赖一个 Facade（例如 `LLMGateway`）。
2. **统一契约**：仅保留 async 接口；同步脚本通过 `asyncio.run` 包一层。
3. **统一错误模型**：失败必须是结构化异常 / 结果对象，而非字符串。
4. **统一可观测性**：每次请求记录 trace_id、provider、model、tokens、latency、重试次数。
5. **统一配置解析**：所有 provider 参数从 `get_provider_config()` 获取，禁止脚本内硬编码。

---

## 3. 目标架构

```text
业务层（core / run_*.py）
        |
        v
LLMGateway（唯一入口）
  - generate_text_batch()
  - generate_json_batch()
  - generate_reasoned_batch()
        |
        v
ProviderFactory（按 provider_name 创建）
        |
        +-- LocalVLLMProvider
        +-- RemoteAPIProvider（OpenAI-compatible, GLM, vLLM API）
```

### 3.1 关键原则

- **业务层只传“任务意图”**（text/json/reasoned），不关心 `/no_think` 或 `response_format` 细节。
- **Provider 层负责协议差异适配**（OpenAI chat / vllm batch / completions fallback）。
- **Gateway 层负责横切逻辑**：超时、重试、熔断、日志、指标。

---

## 4. 分阶段落地计划（建议 4 个迭代）

### 迭代 A：收敛入口（1~2 天）

1. 新建 `core/llm_gateway.py`（或 `core_new/llm_gateway.py`）。
2. Gateway 内部只调用 `llm_providers_new.get_llm_provider()`。
3. 在 Gateway 暴露统一的三个方法：
   - `generate_reasoned_batch(...)`
   - `generate_json_batch(...)`
   - `generate_text_batch(...)`
4. 先改 2~3 个主流程脚本接入（如 `main_batch.py`、`main_batch_local.py`、`main_batch_api.py`）。

### 迭代 B：统一错误与重试（2 天）

1. 定义错误类型：`LLMTimeoutError`、`LLMRateLimitError`、`LLMProtocolError`、`LLMParseError`。
2. Provider 内部仅抛异常，不再返回 `"Error: ..."` 字符串。
3. Gateway 做分层重试：
   - 网络类错误：指数退避重试；
   - 解析类错误：按低温参数重试一次；
   - 业务类错误：直接失败并记录。
4. 增加“单条失败不拖垮整批”的 partial result 机制。

### 迭代 C：配置与策略中心化（1~2 天）

1. 统一 provider 选择参数：只允许传 `provider_name`。
2. 在 Gateway 内解析配置并注入默认策略（timeout/retry/thinking/json mode）。
3. 清理脚本中对 `model_path/api_url/api_key` 的重复拼装。
4. 增加配置校验启动检查（缺 key、URL 格式不对、model_name 为空）。

### 迭代 D：下线旧栈 + 回归测试（2 天）

1. 将旧目录 `llm_providers/` 标记 deprecated（先只读不删）。
2. 所有运行脚本迁移至新 Gateway。
3. 增加回归集：
   - 本地模型通路
   - 本地 API(vLLM) 通路
   - 在线 API(GLM/OpenAI-compatible) 通路
4. 通过后删除旧调用路径并更新 README / 运维脚本。

---

## 5. 关键实现建议（可直接编码）

### 5.1 统一返回结构

建议统一为：

```python
@dataclass
class LLMResult:
    ok: bool
    content: str | None
    reasoning: str | None
    parsed_json: dict | None
    error_code: str | None
    error_message: str | None
    provider: str
    model: str
    latency_ms: int
```

这样上层不用再靠字符串前缀判断错误。

### 5.2 统一重试器

- 把重试逻辑从 provider 下沉到 Gateway。
- provider 只做“一次请求 + 协议适配”。
- Gateway 根据异常类型和幂等性决定是否重试。

### 5.3 统一并发模型

- 批量调用统一用 `asyncio.Semaphore(batch_size)` 控流。
- 对在线 API 增加 `max_in_flight_requests`，避免突发 429。
- 对本地 vLLM 增加动态 batch 建议（可从平均 latency 反推）。

### 5.4 统一 JSON 可靠性

- 优先 `response_format={"type":"json_object"}`（支持时）。
- 不支持时走 prompt 约束 + 容错 parser。
- JSON 解析失败时：自动二次修复请求（repair prompt）。

---

## 6. 迁移清单（建议优先级）

1. **第一批（高频主流程）**
   - `main_batch.py`
   - `main_batch_local.py`
   - `main_batch_api.py`

2. **第二批（实验脚本）**
   - `run_experiment_*.py`
   - `run_generation_*.py`
   - `run_extraction_*.py`

3. **第三批（测试脚本）**
   - `test_*.py` 全量改为通过 Gateway 注入 provider。

---

## 7. 验收标准（Definition of Done）

1. 代码中不再直接 import `llm_providers/`（旧栈）。
2. 所有 LLM 调用统一经过 `LLMGateway`。
3. 三种通路（本地模型、本地 API、在线 API）执行同一批样例时：
   - 返回结构一致；
   - 错误码体系一致；
   - 日志字段一致。
4. 压测 200 条请求：无 event loop 错误、无未捕获异常、失败可追踪。

---

## 8. 建议你们先做的“最小可行重构（MVP）”

如果你们希望本周快速止血，优先做这 3 件事：

1. **统一入口**：先实现 `LLMGateway`，把 `main_batch*.py` 全接过去。
2. **统一错误**：移除 provider 内的 `return "Error: ..."`，改抛异常 + Gateway 包装。
3. **统一配置**：所有脚本只接收 `provider_name`，禁止直传 `api_url/model_path`。

这 3 步做完，80% 的“本地模型 / 本地 API / 在线 OpenAI 客户端调用总出问题”的不稳定性会明显下降。
