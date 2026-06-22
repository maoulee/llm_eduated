# 环境信息

## Python
- **版本**: Python 3.14.0（注意：比 plan 里说的 3.12+ 更新，dataclass/typing 语法都兼容）
- **路径**: `C:\Python314\python.exe`（`python` 命令直接可用）

## 已装的关键依赖
验证命令：`python -c "import X; print(X.__version__)"`

| 包 | 版本 | 用途 |
|----|------|------|
| anthropic | 0.111.0 | Task 5 AnthropicProvider 用 |
| pytest | 9.1.1 | 跑测试 |
| pyyaml | (装了) | Task 11 agent_router 读 YAML |
| openai | (装了) | 现有 RemoteAPIProvider |
| httpx | (装了) | 连接池/重试 |

## pytest 配置
- 已装 `pytest-asyncio` 吗？**需要你验证**：`python -c "import pytest_asyncio; print(pytest_asyncio.__version__)"`
- 如果没装：`pip install pytest-asyncio`
- plan 里的 async 测试（如 `test_backoff_is_exponential`）需要它

## 配置 pytest-asyncio（如果需要）

如果跑 async 测试报 "fixture event_loop not found" 或类似错误，在项目根加 `pytest.ini` 或 `pyproject.toml` 配置：

**方案 A: pyproject.toml 加配置**（推荐，已有 pyproject.toml）
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**方案 B: 单个测试文件加 marker**
```python
import pytest
@pytest.mark.asyncio
async def test_xxx(): ...
```

plan 里的测试已经用了 `@pytest.mark.asyncio`，所以只要装了 pytest-asyncio 就行。但 `asyncio_mode = "auto"` 更省事（不用每个 async 测试都加 marker）。

---

## Git

### ⚠️ 关键坑点：git 不在默认 PATH

Windows cmd.exe 里直接敲 `git` 会报 `'git' 不是内部或外部命令`。

**解决方案**（每次开新 shell 都要做一次）：
```cmd
set PATH=C:\Users\11325\AppData\Roaming\MobaXterm\slash\bin;%PATH%
```

之后 `git --version` 能用（版本 2.21.0，来自 MobaXterm）。

**或者**用完整路径：
```cmd
C:\Users\11325\AppData\Roaming\MobaXterm\slash\bin\git.exe status
```

### Git 配置（已设）
- user.name: `zcode`
- user.email: `zcode@local`
- 这是**仓库级**配置（`.git/config`），不影响全局

### 分支
- 当前分支：`feature/hybrid-solver-annotation`
- 远程：`origin`（github.com/maoulee/llm_eduated）
- **本任务不 push**，只本地 commit

### 代理配置（已设，影响 git 网络操作）
之前 clone 时设了全局代理（为了访问 GitHub）：
- `http.proxy = http://127.0.0.1:7890`
- `https.proxy = http://127.0.0.1:7890`

**本任务不涉及网络**（只本地 commit），所以代理配置不影响。但如果以后要 push/pull，代理必须开着（用户用 7890 端口）。

---

## 关键文件路径

```
D:\code\llm_eduated\                          ← 项目根
├── pyproject.toml                            ← Task 1 已改（加 pyyaml）
├── config.py                                 ← Task 7 要改（加 glm5.2 provider）
├── .env                                      ← GLM 配置（已正确，不动）
├── core_new\
│   ├── agent_roles.py                        ← Task 2 要改（TransportRetryPolicy）
│   ├── llm_gateway.py                        ← Task 3/8/9/10 要改
│   └── agent_router.py                       ← Task 11 要新建
├── llm_providers_new\
│   ├── __init__.py                           ← Task 6 要改（工厂分支）
│   ├── base.py                               ← BaseLLMProvider 基类（参考）
│   ├── remote_api.py                         ← Task 4 要改（加 stream()）
│   ├── anthropic_provider.py                 ← Task 5 要新建
│   └── local_batch.py                        ← 不动（批量标注独立）
├── config\
│   └── agents_llm.yaml                       ← Task 11 要新建
├── tests\                                    ← 各 task 的测试新建在这里
│   └── __init__.py                           ← 已存在（空，pytest 发现已装）
└── handoff\                                  ← 本交接资料目录
    ├── 00-README.md
    ├── 01-SPEC.md
    ├── 02-PLAN.md
    ├── 03-STATUS.md
    └── 04-ENVIRONMENT.md（本文件）
```

---

## .env 关键配置（已正确，不动）

```
GLM_API_BASE="https://open.bigmodel.cn/api/anthropic"   ← anthropic 端点 ✅
GLM_API_KEY="<你的真实 GLM key，不要写在这里，从 .env 读取>"  ← 机密，勿提交
GLM_MODEL=glm-5.2                                        ← ✅
GLM_THINKING_CONTROL_METHOD=none                         ← ✅（effort 由 gateway 注入）
GLM_DEFAULT_MAX_TOKENS=30000                             ← 注意：不是 4096
```

**⚠️ 安全警告**：`GLM_API_KEY` 是机密，**绝对不能 commit 到 git**（本仓库是公开的）。
- `.env` 已在 `.gitignore` 里，安全 ✅
- 本交接资料**不要**写真实 key（已用占位符替代）
- 测试代码用 `os.getenv("GLM_API_KEY")` 从 .env 读取，不硬编码

**Task 5/12 的 e2e 测试**会用到 `GLM_API_KEY`（从 .env 加载）。

---

## 验证环境就绪的命令

交接后第一步，跑这些命令确认环境 OK：

```cmd
cd D:\code\llm_eduated

REM 1. Python + 依赖
python -c "import anthropic, pytest, yaml, openai, httpx; print('deps OK')"

REM 2. pytest-asyncio（如果没有，pip install pytest-asyncio）
python -c "import pytest_asyncio; print('asyncio OK')"

REM 3. git（设 PATH 后）
set PATH=C:\Users\11325\AppData\Roaming\MobaXterm\slash\bin;%PATH%
git --version
git status

REM 4. 现有测试能跑（基线）
python -m pytest tests/ -v -k "not e2e" --co -q
```

如果 4 报错（collecting error），说明现有测试有 import 问题——这可能是项目原有的，不影响你的新测试（你的测试是独立文件）。但如果基线测试能跑，说明环境完全 OK。

---

## 常见坑点

1. **async 测试需要 pytest-asyncio**：如果没装，`@pytest.mark.asyncio` 装饰的测试会被 skip 或报错。
2. **frozen dataclass 加字段要有默认值**（Task 2）：`TransportRetryPolicy` 是 `frozen=True`，新字段必须有默认值，否则破坏现有调用。
3. **anthropic SDK 的流式 API**（Task 5）：用 `async with client.messages.stream(**kwargs) as stream`，不是 `client.messages.create(stream=True)`。详见 spec §3.5。
4. **anthropic 的 thinking 字段**：实测发现 `reasoning_effort` 必须配合 `thinking.type: enabled` 才生效（单独传 effort 被忽略）。详见 spec 附录 A。
5. **不要碰 batch 接口**：`RemoteAPIProvider` 的 `generate_with_think_and_parse_batch` / `generate_json_batch` 是批量标注用的，本次只加 `stream()` 方法，不改这两个。
6. **Windows 路径用反斜杠**：`D:\code\llm_eduated\...`，但 Python 里用 `Path()` 对象或正斜杠都行。
