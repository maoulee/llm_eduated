# K-radar 升级 + 端到端测试报告

> 日期: 2026-06-10
> 状态: 已实现 + 端到端验证通过
> 基于: 2026-06-09-interaction-agent-spec.md

## 1. K-radar 升级：1 维标签 → 5 维认知向量

### 1.1 问题

`k_target: "K2"` 把 5 维认知雷达压成 1 个标签。LLM 凭空猜测导致 K4（陷阱型）几乎从不出现，与真实题位数据严重偏离。

### 1.2 解决方案

**核心原则：K 值从数据中读取，不从 LLM 推断。**

3 级数据源优先级：

| 优先级 | 来源 | k_source 值 | 实现 |
|--------|------|------------|------|
| 1 | 题位经验卡 K值锚点 | `experience_card` | `read_slot_k_radar(slot_id)` |
| 2 | 题目经验文件聚合 | `question_aggregate` | `aggregate_question_k_radar(files)` |
| 3 | 关键词启发式估算 | `heuristic` | `estimate_k_radar_heuristic(mode)` |

### 1.3 Schema 变更

`contracts.py` — SlotBlueprint 新增字段：

```python
k_radar: dict[str, int] = field(default_factory=dict)  # {"K1":3, "K2":3, "K3":2, "K4":4, "K5":1}
k_dominant: str = ""   # 最高分维度 "K4"
k_source: str = ""     # "experience_card" | "question_aggregate" | "heuristic"
```

旧 `k_target` 保留为 `k_dominant` 别名，`single_question_adapter.py` 自动映射。

### 1.4 双通道规范

| 通道 | 受众 | 格式 |
|------|------|------|
| 通道 1 | 教师（草案 markdown） | 自然语言："需多步参数推算"、"概念辨析" |
| 通道 2 | 下游（交接 YAML） | `k_radar: {K1:n, K2:n, ...}` + `k_dominant` + `k_source` |

**硬规则**：教师可见文本中禁止出现 K1-K5 字样。

### 1.5 变更文件清单

| 文件 | 变更 |
|------|------|
| `core_new/doc_pipeline/contracts.py` | 新增 k_radar/k_dominant/k_source 字段 |
| `compose/k_radar_reader.py` | **新建** — 3 级数据提取 + 统一入口 `resolve_k_radar()` |
| `core_new/doc_pipeline/agents/interact.md` | K-radar 数据驱动规则 + 双通道硬规则 |
| `core_new/doc_pipeline/skills/interact_core/SKILL.md` | YAML 示例更新 + k_radar 获取指南 |
| `compose/single_question_adapter.py` | k_target → k_dominant 别名映射 |
| `compose/outline_yaml_generator.py` | 输出 k_radar YAML 替代 k_target |
| `compose/artifact_store.py` | 认知雷达渲染 + 主导维度显示 |
| `core_new/agents/single_choice_team.py` | k_radar 展示兼容旧 k_target |
| `tests/test_k_radar.py` | **新建** — 24 个测试覆盖全部路径 |

## 2. Interact 层改进

### 2.1 Write-before-confirm 协议

Agent 生成草案时必须先展示内容、询问教师确认，然后才 write_file。

实现方式：
- `interact.md` 中增加"文件写入协议"规则
- `_response_contains_draft()` 检测回复中的草案标记（`[✓]`/`[✗]`）
- Turn counter fallback：≥4 轮无草案更新时注入提醒

### 2.2 两轮流程（场景 C）

无经验卡时采用两轮迭代：

```
Round 1: 知识点选择（粗筛）— 纯 LLM 内部知识，不加载 KG/经验卡
    ↓ 教师选择知识点
Round 2: 考察模式展开（细筛）— grep 检索选中的知识点
    ↓ 教师选择考察模式
生成交接 YAML
```

### 2.3 调度器修复

| 修复项 | 旧值 | 新值 |
|--------|------|------|
| 工具轮次上限 | 10 | **15** |
| Context 预裁剪 | 无 | 保留 system + 最近 20 条 |
| 工具结果截断 | 无 | 4000 chars |
| 单轮工具调用上限 | 无 | 5 次 |
| Interact max_tokens | 默认 | 4096 |
| Draft hint 注入 | 新增 system message | 追加到 messages[0]（vLLM 兼容） |

## 3. GLM-5.1 思考控制修复

### 3.1 问题

`thinking_control_method` 默认 `"none"` 导致 `_extra_body_for_thinking()` 返回空 dict。
GLM-5.1 的思考参数从未传递给 API，模型使用默认行为（默认开启思考）。

### 3.2 修复

`config.py` GLM provider: `"none"` → `"param"`

```python
# remote_api.py 中的实现
def _extra_body_for_thinking(self, enable_thinking: bool):
    if self.thinking_control_method == "param":
        return {"thinking": {"type": "enabled" if enable_thinking else "disabled"}}
```

验证：
- thinking ON → `{"thinking": {"type": "enabled"}}` → `reasoning=522` tokens
- thinking OFF → `{"thinking": {"type": "disabled"}}` → `reasoning=0`

## 4. 端到端测试结果

### 4.1 测试案例

| Case | 场景 | 模型 | 结果 |
|------|------|------|------|
| B-DS | 单题（AVL树） | Qwen3.6-27B 本地 | ✅ 完整 YAML + k_radar |
| A-408 | 408 组卷 Q12-Q16 | Qwen3.6-27B 本地 | ✅ 5 slots 全部 k_source=experience_card |
| C-Free | 自由组卷（数据结构） | Qwen3.6-27B 本地 | ✅ 两轮迭代成功 |
| B-Topo | 单题（拓扑排序） | GLM-5.1 thinking ON | ✅ reasoning=522 |
| B-Topo | 单题（拓扑排序） | GLM-5.1 thinking OFF | ✅ reasoning=0 |

### 4.2 K-radar 数据验证

**A-408 案例 Q14**：`k_radar: {K1:3, K2:3, K3:2, K4:4, K5:1}` 
→ 与 `data/slot_experiences/Q14_experience.md` 经验卡 K值锚点数据完全一致。

### 4.3 组装文档验证

`assemble_slot_experience_doc()` 成功消费 interact 生成的 YAML：
- 输入：slot_blueprint (k_radar + examination_mode + teacher_annotation)
- 输出：4671 chars 组装文档，包含：
  - final_machine_contract YAML
  - 认知雷达 K1=3 K2=3 K3=2 K4=4 K5=1
  - 经验卡模式概览（计算型——多步数值推演）
  - 往年真题经验（2009 Q14 完整题干+K值+选项分析+陷阱）
  - K-radar 完整定义

### 4.4 模型性能对比（GLM-5.1 拓扑排序题）

| 维度 | Thinking ON | Thinking OFF |
|------|-------------|--------------|
| Turn 1 耗时 | 54.2s | **49.4s** |
| Turn 2 耗时 | 61.2s | 102.3s |
| 总耗时 | **115.4s** | 151.7s |
| Retry 总数 | 5 | 10 |
| K 值泄露 | 有（"K3"） | 有（"K4"） |
| YAML 完整性 | ✅ | ✅ |

**建议**：日常使用 GLM-5.1 thinking OFF（更快），复杂组卷用 thinking ON。

### 4.5 已知问题

1. **K 值泄露**：所有模型都会在回复文本中泄露 K 值（"K主导: K3"），尽管 prompt 已明确禁止。
   - 方案 A：post-processing 过滤回复中的 K1-K5 字样
   - 方案 B：使用更强指令遵从度的模型

## 5. 测试命令

```bash
# 单元测试
python -m pytest tests/test_k_radar.py tests/test_doc_pipeline.py -x -q

# CLI 端到端测试
python scripts/test_interact_cli.py api_vllm <session> --msg "..." --show-draft
python scripts/test_interact_cli.py glm5.1 <session> --msg "..." --thinking  # GLM+思考
```
