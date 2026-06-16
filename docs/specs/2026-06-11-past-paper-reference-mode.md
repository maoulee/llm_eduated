# 往年试卷参考出题模式 — 设计 Spec

> 版本: 1.0 | 日期: 2026-06-11
> 状态: **设计中**

---

## 1. 定位

交互层的一个**新入口模式**。教师不再描述需求，而是提供一张往年试卷（结构化数据），系统基于往年试卷的考法和难度规划新试卷的知识点，生成组合方案供教师选择。

与现有入口并行：

| 入口 | 触发 | 先验知识 | 流程 |
|------|------|---------|------|
| A | 408/经验卡组卷 | 经验卡提供考法+知识点 | 直接 combined |
| B | 指定知识点出题 | 教师指定知识点 | grep → combined |
| C | 自由描述出题 | 无先验 | knowledge → examination |
| **D（新增）** | **往年试卷参考** | **往年卷提供考法+难度** | **分析 → 知识点组合** |

---

## 2. 核心思路

**可复用（从往年卷提取）**：
- 试卷结构：题量、题型分布、分值分布
- 每题的考法模式：从题干推断（GLM-5.1 参数知识）
- 每题的难度：从分值和题型推断

**不可复用（需重新规划）**：
- 具体知识点：不同年份可能考不同知识点

**约束**：
- 题型映射为 4 种：选择题、填空题、判断题、主观题
- **同题型内知识点不重复**（选择题之间不能重复考"树"）
- **跨题型知识点可以重复**（选择题考"树" + 主观题考"树" 是允许的）
- 生成 2-3 套整体知识点组合方案，教师选一套

---

## 3. 流程

```
教师在聊天中提供往年试卷数据
  ↓
Agent: read_file 读取试卷数据
  ↓
Agent: 分析往年试卷（GLM-5.1 参数知识）
  → 试卷结构：题量、题型分布、分值
  → 每题：题型、考法（从题干推断）、难度（从分值推断）
  → 题型映射：原始标签 → 选择/填空/判断/主观
  ↓
Agent: 生成 2-3 套知识点组合方案
  → 固定：题型 + 考法 + 难度 + 分值
  → 变化：每题的具体知识点（GLM 参数知识 + KG）
  → 约束：同题型内知识点不重复
  ↓
write_file 写入草案（[PHASE: knowledge]）
  → 每套方案一个 section
  → 每题列出知识点选项
  ↓
教师选择一套方案
  ↓
Agent 生成 paper_request.yaml
  → question_type: 映射后的 4 种题型之一
  → examination_mode: 从往年卷考法推断
  → primary_target_name: 教师选择的知识点
  → target_difficulty: 从往年卷推断
  ↓
进入出题流水线
```

---

## 4. 数据输入

### 4.1 输入形式

教师将往年试卷数据文件放入 workspace，在聊天中给出文件路径。Agent 用 `read_file` 读取。

### 4.2 数据假设

系统不假设固定的 JSON 结构。唯一保证：
- 能获取每道题的**题干**（stem）
- 能获取试卷的基本信息（科目、题型分布等）
- 具体结构可能因学校而异，Agent 需要动态理解

---

## 5. 草案格式

组合方案沿用现有草案格式，增加"方案"层级：

```markdown
[SCENARIO: D]
[ROUND: 1]
[PHASE: knowledge]

## 方案 A

### 选择题（10题）

## Q1（选择题·2分）
[ ] 线性表 — 链表操作时间复杂度分析
[ ] 栈和队列 — 操作特性对比

## Q2（选择题·2分）
[ ] 字符串 — KMP 模式匹配比较次数
[ ] 散列表 — 冲突处理方法

...

### 主观题

## Q11（主观题·4分）
[ ] 二叉树 — 遍历序列还原与转换
[ ] 图 — 邻接矩阵遍历

...

## 方案 B
（同结构，不同知识点分配）
```

---

## 6. 题型映射

从往年卷的原始题型标签映射为系统支持的 4 种：

| 往年卷可能出现的标签 | 映射为 |
|---------------------|--------|
| 选择题、单项选择题 | 选择题 |
| 填空题 | 填空题 |
| 判断题 | 判断题 |
| 应用题、简答题、综合题、算法分析题、算法设计题、论述题 | 主观题 |

映射后的标签直接写入 `paper_request.yaml` 的 `question_type` 字段，透传给出题团队。

---

## 7. 知识点去重规则

```
同题型内：不允许重复
  选择题 Q1: 树 ✅
  选择题 Q2: 树 ❌ → 方案无效

跨题型：允许重复
  选择题 Q1: 树 ✅
  主观题 Q11: 树 ✅ → 合理
```

每套组合方案必须满足此约束。Agent 在生成方案时自检。

---

## 8. SKILL.md 新增内容

```markdown
## 往年试卷参考模式

当教师在聊天中提供往年试卷文件时：

1. read_file 读取试卷数据
2. 分析试卷结构：题量、题型分布、分值分布
3. 将题型映射为 4 种：选择/填空/判断/主观
4. 从每题题干推断考法模式和难度
5. 生成 2-3 套知识点组合方案：
   - 固定：题型 + 考法 + 难度 + 分值
   - 变化：知识点（参数知识 + KG）
   - 约束：同题型内知识点不重复
6. write_file 写入草案让教师选择方案
7. 教师选定后生成 paper_request.yaml，question_type 透传映射后的标签
```

---

## 9. 不需要改的部分

| 层面 | 说明 |
|------|------|
| 后端 API | `/turn` 接口传文件路径即可，agent 用 read_file 读取 |
| 前端 | 教师将文件放入 workspace，聊天中给路径 |
| 出题流水线 | 接收 paper_request.yaml 后按 question_type 出题 |
| 现有场景 A/B/C | 不受影响，并行入口 |

---

## 10. 已决策

1. ~~分析缓存~~ → 不做。每次重新分析。
2. ~~单题微调~~ → 不需要新功能。教师选定方案后，通过现有批注流程对每题知识点微调。
3. ~~概念题处理~~ → 见 §11。

---

## 11. 概念题轻量路径

往年试卷中存在概念性题目（纯记忆型判断题、知识点定义选择题等），这类题目难度低，不需要走完整的出题团队流程（设计 → 求解 → 审核）。

### 判断标准

Agent 在分析往年卷时，将每题标记为 `complexity: conceptual | standard`：

- **conceptual**：纯概念记忆、定义判断、简单辨析（如"栈和队列的共同点是___"）
- **standard**：需要推理、计算、算法设计、多步分析

### 出题路径

```
paper_request.yaml 中每个 slot 带 complexity 标签
  ↓
conceptual 题目 → 轻量路径：
  单个 LLM 智能体直接出题（交互层就地处理 或 后端分支独立智能体）
  一次性批量处理所有 conceptual 题目
  生成后直接写入，跳过求解阶段
  ↓
standard 题目 → 现有完整路径：
  出题团队 → design → solve → review
```

### 交互层角色

交互层负责：
1. 分析时标记每题的 complexity
2. 草案中展示标记（让教师知道哪些题走轻量路径）
3. paper_request.yaml 中包含 `complexity` 字段
4. 下游路由根据 complexity 分发到不同出题路径

**不做的事**：交互层不负责概念题的实际出题。只负责标记和分发。

---

## 12. 后端编排优化

### 12.1 问题：orchestrator 平铺结构

`DocPipelineOrchestrator.run_pipeline()` 当前是 400+ 行平铺方法，同时负责 Layer 路由、Agent 调用、结果检查、循环控制、回退路由、格式化。加入概念题分支后维护性更差。

### 12.2 方案：拆分为子方法 + complexity 路由

```python
class DocPipelineOrchestrator:
    async def run_pipeline(self, slot_id, slot_data, ...):
        complexity = slot_data.get("complexity", "standard")
        self._ensure_blueprint(slot_id, slot_data, ...)
        
        if complexity == "conceptual":
            return await self._run_conceptual_pipeline(slot_id, slot_data, ...)
        return await self._run_standard_pipeline(slot_id, slot_data, ...)
    
    async def _run_standard_pipeline(self, ...):
        self._run_design_card(...)
        self._run_question_review_loop(...)    # Layer 2-3
        self._run_solve(...)                    # Layer 4
        self._run_final_review_loop(...)        # Layer 5
        self._format_final(...)
    
    async def _run_conceptual_pipeline(self, ...):
        self._run_question_review_loop(...)     # Layer 2-3（一轮）
        # 跳过 Layer 4 Solve
        # 跳过 Layer 5 Final Review 回退路由
        self._format_final(...)
```

**收益**：概念题分支独立方法不影响标准路径；每个 Layer 封装；断点续跑可改为字符串状态。

### 12.3 改动清单

| 文件 | 改动 |
|------|------|
| `orchestrator.py` | `run_pipeline()` 拆为子方法 + `_run_conceptual_pipeline()` |
| `pipeline_trigger.py` | `_generate_one()` 传入 `complexity` 字段 |
| `SKILL.md` | Entry D 指令 + `[SCENARIO: D]` |
| `interact.md` | scenario 列表加 D |
| `interact_v2_service.py` L298 | 正则 `[ABC]` → `[ABCD]` |
| `scheduler.py` L1108 | D 入口 max_tokens 提升（4096 → 8192） |

### 12.4 不引入 LangGraph

当前分支复杂度 = 1 个 if/else（standard vs conceptual），手工编排足够。LangGraph 适合多轮对话 agent 编排和人工中断恢复，不匹配此处的批量流水线场景。过早引入是 YAGNI。

---

## 13. Solve 智能体优化

### 13.1 问题：职责混杂

Solve agent 同时承担求解、题面修正、参数搜索三个职责，优先级不清晰。

### 13.2 问题：概念题走完整 Solve 是浪费

概念题（纯记忆判断、定义辨析）不需要代码验证、不需要题面修正。当前走 Layer 4-5 是多余的 LLM 调用。

### 13.3 方案：概念题由 Question agent 直接产出 solution

**Option A（推荐）**：概念题的 Question agent 出题时直接写 `solution.md`。
- 概念题答案由出题意图决定，不存在"独立验证"需求
- 减少一次 LLM 调用（Layer 4）+ 一次终审调用（Layer 5）
- 改动：`question_sc.md` / `question_comp.md` 加条件分支

**Option B**：独立轻量 solve agent，只推理不写代码，一轮完成。
- 保持了"出题者不写答案"的隔离，但多一次调用。

选择 A，与 §11 概念题轻量路径一致。

### 13.4 数值题 Solve 约束强化

| 约束 | 当前 | 优化 |
|------|------|------|
| edit 循环 | 无上限（仅"兜底"） | 最多 edit 2 次，超过直接提交 |
| 参数搜索 | "仅作为兜底" | 禁止。参数搜索由 design_card 的 parameter_plan 负责 |
| 题面修正反馈 | 无记录 | solve agent 的 edit 写入 `solve_notes.md` |

### 13.5 改动清单

| 文件 | 改动 |
|------|------|
| `solve.md` | 加 edit 上限（2次）+ 禁止参数搜索 + 加 solve_notes |
| `question_sc.md` | 加概念题条件分支：complexity=conceptual 时同时写 solution.md |
| `orchestrator.py` | `_run_conceptual_pipeline` 跳过 Layer 4-5 |

---

## 14. 智能体行为与技能分离（md vs SKILL）

> 日期: 2026-06-13 | 状态: 设计中

### 14.1 问题：行为与经验混杂

当前各 agent 的 `.md`（行为）和 `SKILL.md`（技能）边界模糊。例如 `solve_skill.md` 同时包含"权责边界/禁止行为"（应属 md 通用行为）和"三步工作流程/代码模板"（应属 SKILL 具体逻辑）。

### 14.2 分离原则（参照 CLAUDE.md 模式）

```
.md（通用行为手册，CLAUDE.md 式）
├── 角色身份（1-2 句）
├── 思考控制（何时简单/复杂思考）⭐ 核心
├── 核心原则（如"代码是唯一数值来源"）
├── 工具使用纪律（先读再写、exec 验证等通用规则）
└── 红线（通用行为禁忌）

SKILL.md（具体处理逻辑）
├── 处理流程（这道题具体怎么做）
├── 输出契约（产出什么，不含代码模板）
├── 领域经验（参数怎么选、流程怎么走）
└── 常见模式
```

### 14.3 思考控制是 md 的核心

每个 agent 的 md 必须明确"什么时候简单思考、什么时候复杂思考、什么时候禁止思考"：

| Question Agent | Solve Agent | Design Card | Form Gate |
|----------------|-------------|-------------|-----------|
| 选参数：⚡快速直觉 | 执行：⚡无思考 | 知识点分解：中等 | 形式比对：中等 |
| 写 solve.py 逻辑：中等 | 读输出：快速 | 干扰策略：中等 | ⚠️心算验证：禁止 |
| ⚠️脑内算结果：禁止 | ⚠️质疑 exec：禁止 | ⚠️算答案值：禁止 | |

**通用铁律：绝不脑内推演参数的数值结果。** 数值由 solve.py 执行确定。

### 14.4 SKILL 不给代码模板

GLM-5.1 是强模型，能自己写代码。SKILL 只给**输出契约 + 原则**，代码结构让模型自主决定。

- ❌ 错误：给死模板（`def correct(): ... def distractor_1(): ...`）
- ✅ 正确：给契约（"solve.py 必须输出正确答案 + 3 个干扰值，干扰值由错误算法产生，不是硬编码常量"）

SKILL 保留的是"为什么"（为什么用错误算法不用硬编码），不是"怎么写"（代码结构）。

### 14.5 通用干扰模式归 Design Card

干扰设计模式（符号错误/单位换算/偏移错误/非叶节点纳入/遗漏项等）是**跨题型通用认知错误模式**，不是选择题专属。

归属调整：
- 通用干扰模式库 → `design_card_v1/SKILL.md`（Design Card 在规划阶段选择用哪些干扰策略）
- `question_sc_draft/SKILL.md` 不放干扰模式，只放出题流程 + 参数经验 + 题干风格
- Question Agent 只"实现"设计卡选定的干扰策略，不自己选

---

## 15. 代码即真值出题流程

> 日期: 2026-06-13 | 状态: 设计中

### 15.1 核心原则

模型只设计框架，所有数值由 `solve.py` 执行确定，模型绝不做脑内算术。

### 15.2 流程

```
Layer 1.5  Design Card
  产出: design_card.md
  内容: 知识点、考察形式、K值、参数结构约束、干扰策略(错误类型)、solve_logic_intent
  禁止: 预设答案值、预设干扰值、写代码

Layer 2    Question Agent
  产出: question.md(仅题干) + solve.py(参数+正确算法+错误算法)
  内容: 题干框架、参数值、计算逻辑(正确+干扰错误算法)
  禁止: 脑内算结果、写最终选项值、硬编码干扰值

Layer 3    Form Gate (Review)
  审: 形式/意图/solve.py 逻辑是否与设计卡一致
  不审: 数值(此时无数值)、选项值(未生成)
  fail → 回 Layer 2

Layer 4    Solve
  执行: exec solve.py → solve_output.txt
  产出: solution.md + 组装选项进 question.md
  不做: 脑内计算、改题干、改 solve.py 逻辑

Layer 5    Final Review
  审: 表述/格式/交付完整性
  不审: 数值正确性(代码保证)
```

### 15.3 solve.py 契约（不给模板）

```
solve.py 必须满足:
1. 从题干参数计算正确答案
2. 输出正确答案 + 3 个干扰值(选择题) / 各子问答案(综合题)
3. 干扰值由"错误算法"产生，非硬编码常量
4. print 每个值 + 对应逻辑标签(正确/干扰1/干扰2/干扰3)

代码结构、函数组织方式由模型自主决定。
```

### 15.4 文件依赖

| 文件 | L2 写 | L3 读 | L4 读 | L4 写 | L5 读 |
|------|-------|-------|-------|-------|-------|
| question.md | ✅题干 | ✅ | ✅ | ✅补选项 | ✅ |
| solve.py | ✅ | ✅ | ✅执行 | — | 可选 |
| solve_output.txt | — | — | — | ✅ | ✅ |
| solution.md | — | — | — | ✅ | ✅ |

**风险**: question.md 被 L2 和 L4 都写。L4 补选项必须是追加（edit_file），不能覆盖题干。

### 15.5 各角色职责边界

| 角色 | md 通用行为 | SKILL 具体逻辑 |
|------|------------|---------------|
| Design Card | 只规划不算值；思考控制 | 规划流程；通用干扰模式库；solve_logic_intent 写法 |
| Question Agent | 不脑内算术；选参数快速直觉 | 出题流程；参数经验；题干风格 |
| Form Gate | 审形式不审数值；不心算 | 审核清单；形式偏离识别 |
| Solve | exec 即真值；不质疑不改题干 | 执行流程；选项组装规则；exec 失败处理 |
| Final | 审表述不重算 | 收尾流程；交付标准 |

### 15.6 关键决策（已确认）

1. **演进 5-agent**（不切换 2-agent）：复用现有 design_card/form_gate/conceptual 路径，质量门更完整。吸收 creator_solve 的占位符替换思路。
2. **Solve Agent 失去独立性**：接受，代码即真值。solve.py 逻辑错误靠 Form Gate 审"计算逻辑与意图一致"兜底。
3. **综合题混合子问**：solve.py 统一覆盖所有子问，不细化 complexity 到子问级。分析型子问的计算函数返回推理描述。

---

## 16. 结构复用 + DAG 求解架构（验证后）

> 日期: 2026-06-14 | 状态: 已验证（实验数据支持）

### 16.1 核心发现：分析复用 vs 发明（实测）

综合题 K3-K4 设计的过度思考（脑内模拟验证结构），根源是**模型"发明"具体结构后需"验证它成立"**。实验对照（同一 case，GLM-5.2）：

| 方案 | reasoning | 产出 |
|------|-----------|------|
| 合并单 agent（发明+验证）| ~25000c | ✗ 失败（length） |
| 拆分 设计求解 agent | ~13800c | ✗ 失败 |
| 考察形式 agent 单独 | 1684c | ✓（判断任务干净） |
| **分析往年同类型题→复用骨架** | **4700c** | **✓ 成功** |

**结论**：结构（考什么+怎么设问）从**往年同类型题分析**得来，不发明。分析是"提取"（已知成立，无需验证），发明才需验证（触发脑内模拟）。

### 16.2 两层分离

```
考什么 + 怎么设问（骨架层）← 往年同类型题分析
求解（计算层）            ← DAG 代码，见 §16.4
```

- **骨架**：子问组织、考察意图递进、设问方式。来自往年同类型综合题的结构分析（不是发明）。
- **求解**：把考察形式变成参数化计算（DAG），模型给初始参数，代码传播出全部参数+结果+推理。

### 16.3 难度三要点（待落地）

> **难度 = K-雷达图（5 维向量），不是单个等级**。K1（基础认知）/K2（单步代入）/K3（机制推演）/K4（条件路由）/K5（跨域联动）每个维度各有自己的值（1-5）。它是细粒度多维评估，形状（各维组合）决定题目特征，不是单一"难度4"。
> **锚定方式**：基于上游传递的**考察需求**锚定 K-雷达图形状（如 K1=2,K2=3,K3=4,K4=4,K5=1 的形状），骨架选择与缩放都按这个形状来。

1. **基于 K-雷达形状选骨架**：往年题带 K-雷达标注，按形状匹配选骨架（如 K3 主导→多步串行骨架；K4 主导→陷阱辨析骨架；K1 主导→概念辨析骨架）。不是按单一难度档。
2. **骨架表述优化**：把往年题的具体表述抽象成可复用骨架模板（去特化，留结构）。
3. **基于骨架调节 K-雷达形状**：同一骨架可调各维值——增/减串行步数（调 K3）、加/去陷阱（调 K4）、加/去跨域联动（调 K5）、改概念辨析深度（调 K1）。骨架可缩放，缩放的是雷达各维。

### 16.4 求解 = DAG（核心：不搜参数，固定计算路径）

**不是**让模型搜索/设计所有参数。**而是**把考察形式变成一段参数化代码（有向无环图 DAG）：

```python
# 模型写的不是"具体题"，是"参数化计算图"
def generate(initial_params):
    # 计算路径固定（DAG）：输入 → 中间参数 → 各子问结果 → 推理过程
    p1 = f(initial_params)           # DAG 节点1
    p2 = g(p1)                        # DAG 节点2（依赖 p1）
    answers = [h_i(p2) for i in ...]  # 各子问答案
    return question_params, answers, reasoning_trace
```

- **计算路径由代码固定**（DAG），不同输入参数 → 不同题目参数和结果，自然产生
- **模型只给 1-2 个初始参数**（基于经验预设，如插入序列首项/树高），**代码传播**出所有中间参数 + 结果 + 推理过程
- 本质：题 = 参数化 DAG + 约束。模型基于经验给初始参数，直接获得全套参数和推理
- **禁止参数搜索**：模型不枚举凑答案；DAG 是确定性计算（或约束满足），不是搜索匹配

### 16.5 完整流程（验证后架构）

```
考点（路由定位）+ 题型 + 目标难度
   ↓
检索同类型往年题（按 题型+考点，避免取错类型——综合题别取成选择题）
   ↓
基于难度选骨架（§16.3-1）+ 优化骨架表述（§16.3-2）+ 难度可调（§16.3-3）
   ↓
分析往年结构 → 复用骨架（考什么+设问，符号化题干）  ← 替代"发明"，消除过度思考
   ↓
求解 = DAG：模型把考察形式写成参数化代码（计算路径固定）
   ↓
模型给初始参数（经验预设）→ DAG 传播 → 全部参数 + 结果 + 推理
   ↓
具体题 + 答案 + 求解过程
```

### 16.6 设计 agent 职责（窄化后）

设计 agent 不发明结构、不算参数、不验证，只做：
1. 分析往年同类型题结构 → 提炼骨架
2. 按难度选/调骨架
3. 符号化题干（套骨架，参数符号占位）
4. 把考察形式写成参数化 DAG 代码（solve.py）+ 给初始参数

### 16.7 与 §15 code-as-truth 的关系

§15 的"代码即真值"（数值由 solve.py 执行确定）不变。§16 细化：
- **结构来源**：往年分析（§16），不是发明（§15 未明确，导致过度思考）
- **求解本质**：参数化 DAG（§16.4），不是参数搜索/单点计算
- §16 是 §15 的演进，补上了"结构从哪来"+"参数怎么来"两个缺口

---

## 17. 拆分聚焦架构 + 审核介入（最终定型）

> 日期: 2026-06-14 | 状态: 实验定型，待实施

### 17.1 核心原则：拆分聚焦 agent，不整合

打通测试证明：**整合单 agent**（承载 考察形式+骨架+雷达+融合+DAG 全部）→ 综合题过度思考（17-25k，失败）；**拆分聚焦 agent**（各单一职责）→ 全部成功（各 <5k）。提速来自拆分，不是整合。

| | 整合单 agent | 拆分聚焦 agent |
|---|---|---|
| 综合题 reasoning | 17-25k | 考察形式 1.7k + 骨架 4.7k + solve ~3k ≈ 9k |
| 产出 | ✗ 失败 | ✓ 成功 |

### 17.2 设计层共享，后处理分支

考察形式 + 骨架分析 + 审核 + solve 两类题**共享**；solve 后**分支**：
- 选择题：correct → 干扰项 → 组装选项 + verify distinct
- 综合题：correct 各子问答案 → 填回符号题干

### 17.3 agent 清单（拆分 + 审核介入）

```
1. 考察形式 agent    — KP + K-雷达 → 选定考察形式（窄，判断任务）
2. 骨架分析 agent    — 检索同题型往年题 → 分析复用骨架 → 符号题干
                      （只出题干+问题，不出答案、不出选项）
   [条件] 融合 agent — 仅 K3-K4 高难度且单骨架不够才触发（同考点多侧重，非跨考点）
3. 审核介入 agent    — 审符号题干：考察形式/雷达/骨架/设问自洽（form_gate，fail-fast）
4. solve(DAG) agent — 只算【正确答案】（确定性计算路径，给初始参数→传播）
5. 分支组装          — 选择：correct→干扰项(轻)→组装+verify distinct
                      综合：correct 填回符号题干
```

### 17.4 设计不出答案/选项（关键）

设计 agent 只产出**题干 + 问题**，不出答案、不出选项。

**原因**：设计阶段若连选项/答案一起出 → solve 算出的正确值对不上预设选项 → 触发脑内算（凑/改）。设计只出框架，答案由 solve 定，选项由 solve 后组装。

### 17.5 solve 只算正确，干扰项轻给（修正 §16.4）

- **solve(DAG)**：只算**正确答案**一条确定性路径（**不含错误算法**）。给初始参数 → 代码传播出全部正确参数 + 结果。
- **干扰项**：基于 correct + 题目情境，**直接给合理错误值**（plausible 范围/风格的错值，或从 correct 派生：±offset / off-by-one / 符号 / 单位）。**非代码计算**——干扰项本就要求错，不需算对，直接给符合考察要求的错值即可。verify 4 值互不相同 + 不撞正确值。
- **修正 §16.4**：DAG 不再编码 3 个错误算法；只算正确，干扰项分离轻给。

### 17.6 条件融合规则

融合（同考点多侧重）= 难度调节工具，**条件触发**，不默认：
- K1-K2 / K3 简单·正常题：**不融合**（单骨架够，融合会超纲）
- 仅 K3-K4 高难度且单骨架不足以达难度时：才融合多侧重

硬约束：难度已满足目标 K-雷达 → 不额外融合（避免超纲）。融合是为了达标，不是越多越好。

### 17.7 审核介入位置与职责

```
骨架符号题干 → ⭐审核介入 → solve
```

审核查（form_gate 职责，锚定骨架复用题干）：
- 题干符合选定考察形式 + 目标 K-雷达形状
- 骨架复用到位（没跑偏发明新结构）
- 设问自洽（子问链/选项结构对题型；选择题无选项是正常的——选项在 solve 后组装，不得因此打回）

fail-fast：题干错 → solve 全错，故在 solve 前卡形式审核。

### 17.8 每环节都是轻任务（无发明+验证）

设计只出框架、solve 只算对、干扰项只给错值、审核只判形式。**没有任何环节"发明具体结构+脑内验证它成立"** → 不触发脑内模拟。这是整个重构治本的落点。

---

## 18. 求解即解题代码 + 两纪律（最终修正）

> 日期: 2026-06-14 | 状态: 定型，待实施

### 18.1 核心原则：不深度重复思考

**出题不是难事。** 过度思考（54k-60k）源于"设计既给参数又验证参数成立"。修正：**设计大胆给不验证，代码验证纠错**——把"验证"从设计脑内挪到代码 exec。设计变快（不背验证），代码是唯一真值。

### 18.2 两个纪律

**① 设计纪律：大胆设计，不验证**
设计智能体基于骨架 + 经验给出：题干 + 设问 + **初步参数**。**不脑内验证**（不算、不验证结构是否成立）。验证是后面代码的事。大胆给 → 设计快 → 不过度思考。

**② 代码纪律：验证 + 纠错**
solve 代码负责验证与纠错：写解题代码 → exec → 错了改**代码**（绝不改题面）→ 快速迭代 → 算出正确答案 + solution。代码是唯一真值。

分工本质：**设计"敢给"（经验驱动），代码"把关"（exec 验证 + 纠错）**。

### 18.3 solve.py = 解题代码（非 DAG，修正 §16.4/§17.5）

solve.py 就是**这道题的解题代码**：拿到题干，brief 想解法，直接写 Python 实现。像程序员解题——**brief-think-then-code**，不该 54k。

- **是**：解题代码（compute answer），写→exec→fix 代码→solution
- **不是**：参数化 DAG、计算路径、有向无环图、完整数据结构模拟、参数搜索——全是过度架构包装，**删除这些措辞**
- 代码只需**能求解题目**（算出答案），不需完整模拟整个数据结构

### 18.4 设计智能体不写 solve.py

**修正权责**（§17 的 skeleton_design 既出题干又写 solve.py 负荷过大）：
- **设计智能体**：只出题干 + 设问 + 初步参数（不写 solve.py）
- **求解智能体**：拿题干 → brief 想 → 写解题代码 → exec → fix 代码 → 答案 + solution

### 18.5 流程 + 选择题/主观题分支

```
设计（大胆不验证）：骨架+经验 → 题干+设问+初步参数     ← 纪律①
  ↓
求解（代码验证纠错）：brief想 → 写解题代码 → exec → [fix代码，不改题面] → 答案+solution  ← 纪律②
  ↓
分支：
  选择题 → 设计（第2遍：基于答案+solution 设计干扰选项）→ 最终审核
  主观题 → 答案填回题干 → 最终审核（直接前进，不回退）
```

- **选择题**：需第2遍（基于正确答案设计干扰选项），再终审
- **主观题（综合）**：solve 算出各子问答案 → 填回符号题干 → **直接终审，不回退**（无选项，无需二次设计）
- 第2遍选项设计后**直接传最终审核**（不再循环）

### 18.6 求解智能体行为（简单快速迭代编码）

像程序员/Claude 写代码——简单、快速迭代：
```
分析题目（brief 想解法，不深推）
  → write solve.py（解题代码，直接写）
  → exec 执行
  → 出错？→ fix solve.py（改代码，不改题干）→ 再 exec（快速迭代）
  → 没错 → 读 exec 输出 → write solution.md
```
核心纪律：brief-think-then-code；exec 出错只改 solve.py 不改题面；快速迭代不过度思考。

### 18.7 与 §16/§17 的关系（修正）

§16.4 的"求解 = DAG"、§17.5 的"参数化 DAG"、§17 的"skeleton_design 写 solve.py"——**均过度架构，由 §18 修正**：
- solve.py = 解题代码（非 DAG）
- 设计不写 solve.py（solver 写）
- 设计大胆不验证（纪律①），代码验证纠错（纪律②）
- 选择题第2遍选项设计归设计智能体（基于答案）；主观题直接填回终审

## 19. 题目设计合一 + solver 分支 + 三层边界（最终架构）

> 日期: 2026-06-14 | 状态: 定型，实施中

### 19.1 核心思想（修正 §18 的 agent 拆分）

§18 的 agent 拆分（skeleton_design 出题干 + distractor_assembly 出选项）造成**题意知识分裂**：两个 agent 都要理解题意，distractor 要重读题面，重复消耗。§19 修正：

- **题面合一**：一个 `design` 智能体拥有全部题面知识，跑两 pass（P1 出题 / P2 基于解定稿）。
- **solver 分支**：solve 是纯计算分支节点（算题→返回解），概念/不计算题直接跳过。
- **solve 不碰选项**：solve 只算解，选项设计是 design P2 的任务。

### 19.2 两纪律细化（修正 §18.2）

**① 设计纪律：经验值大胆给，不脑内算**
P1 **不设计/不推演参数**，而是给一个**符合要求的经验值**（如 AVL 题 n 取 7-8，给 8），交给 solve 验证。区别：

| | 设计参数（✗禁止） | 经验值（✓正确） |
|---|---|---|
| 心智 | "我要算出 n=7 让 AVL 平衡" | "AVL 题经验上 n 取 7-8，给 8" |
| 来源 | 脑内推演 | 骨架/经验缓存里的经验值表 |

**② 代码纪律：代码错误就地循环，不回退**
solve 的 exec 报错（语法/索引/类型）= **代码 bug，与逻辑/参数无关**，solver **内部循环 fix**，不冒泡、不回退。逻辑错误（exec 成功但算错值）solver 发现不了，由 design P2 / final 比对意图捕获。

### 19.3 三层边界（以 behavior/*.md 为铆钉，修正"流程塞进 agent md"）

```
behavior md ←→ 行为契约：模式、边界、禁止行为、工具优先级（与领域无关）
skill       ←→ 领域流程：具体步骤、模板、经验值表、触发条件（与领域强相关）
agent md    ←→ 角色身份 + 思考控制表 + 高层红线 + 指向 behavior/skill
```

**铁律：agent md 不含任何具体 Step / 模板 / 经验值表 / 触发条件（那些归 skill）。**

### 19.4 design 双模式加载（一个 agent，两套 skill）

`design` agent md 一个，但 orchestrator 按 pass 注入不同 skill：

```
_run_design_pass1():
  run_agent("design", task, skill_override="design_draft_skill", ...)
_run_design_pass2():
  run_agent("design", task, skill_override="design_finalize_skill", ...)
```

scheduler `run_agent` 加 `skill_override: str | None` 参数（默认用 `ROLE_SKILLS[role]`，传入则用指定 skill）。

### 19.5 失败处理（核心：solver 不回退）

| 问题 | 检测方 | 处理 | 路由 |
|------|--------|------|------|
| 代码错误（exec 报错） | solver exec | **内部循环 fix** | solve 内部，不冒泡 |
| 逻辑错误（exec 成功但算错） | design P2 / final | P2 改参数数值（仅数字）→ re-solve → P2 | P2 内部 |
| solver fix 超限 | solver | **清空 solver 上下文，重跑同一题** | solver 自重置 |
| 重跑仍超限 | solver | 升级失败（不回退 design） | 失败 |

**删掉 §18 的 `solve code_error → design` 回退边**。结构问题本应被 form_gate 拦截；漏到 solver 仍失败的，solver 不判断结构，直接升级失败。

### 19.6 流程图

```
design_card → exam_form → design(P1: 题干+设问+经验值参数)
                              │
                  conceptual/不计算│ 需计算
                              ▼        ▼
              ┌─ 直达 P2 ──┐    form_gate → solve(分支: brief→写py→exec→内部fix→解)
              │ (P1含答案) │              │ success
              │            │              ▼
              └────────────┴──► design(P2: 收到解)
                                     选择题 → 基于解设 3 干扰选项
                                     主观题 → 解填回题干
                                     │
                                     ▼
                                  final → done
```

- **P2 内部**：参数致答案不对 → 改参数数值 → re-solve → P2 再比对（cap=1）
- **form_gate needs_fix → design P1**：形式不合规，重设计（可动结构/题干）
- **conceptual**：design P1 含答案 → 跳 form_gate/solve → 直达 P2 填回

### 19.7 归档清单（实施前清场）

归档到 `agents/_archive/` 和 `skills/_archive/`：

**agent md**：`question_sc.md`、`question_comp.md`、`skeleton_design.md`、`distractor_assembly.md`、`creator.md`、`reviewer.md`

**skill 目录**：`skeleton_design_skill/`、`question_sc_draft/`、`question_comp_draft/`、`creator_solve/`、`checkpoint_review/`

**保留不动**：`question_design.md`（design_card 智能体）、`exam_form`、`review`、`final_review`、`outline`、`paper_outline`、`human_intake`、`interact` + 各自 skill + `behavior/CORE.md`、`artifact_writer.md`、`audit_gate.md`。

### 19.8 新建文件

**`agents/design.md`**（角色身份 + 思考控制 + 高层红线，**无流程**）：
- frontmatter: `name: design`, `phase: 2`, `behavior: artifact_writer`, `skills: []`（运行时注入）
- §1 角色身份：经验值出题者（P1）+ 解后定稿者（P2）
- §2 思考控制表（P1 快速给经验值 / P2 读解设选项 / 脑内算禁止）
- §3 两纪律（①经验值大胆给不脑内算；P2 只读解不重算）
- §4 高层红线（P1 不得脑内算/不得脑内验证；P2 不得改逻辑/不得重算解/不得碰 solve.py）

**`skills/design_draft_skill/SKILL.md`**（P1 流程）：
- Step1 读缓存（assembled/design_card/exam_form）
- Step2 复用骨架（去特化留结构，缓存优先，fallback grep 粗粒度一次）
- Step3 经验值参数（**经验值表**：按题型给友好值，如 AVL n∈{7,8}、页表 frames∈{3,4}）
- Step4 §17.6 条件融合（仅 K3-K4 高难度 + 单骨架不足；难度达标不额外融合）
- Step5 输出（题干+设问+经验值参数+设计说明）
- 题干模板（综合题/选择题）+ 设计说明必写项

**`skills/design_finalize_skill/SKILL.md`**（P2 流程）：
- Step1 读解（solve_output.txt / solution.md）
- Step2 质检比对（解 vs 预期解题意图，仅可机械判定：整数性/平凡值/越界）
  - 参数致答案不对 → 改参数数值（仅数字）→ re-solve（cap=1）→ 再比对
- Step3 选择题设选项（基于解派生 3 干扰，只设不求对）/ 主观题答案填回题干
- Step4 输出（含选项的 question.md / 填回的 question.md）

### 19.9 behavior 改动

**`behavior/evidence_solver.md`**：
- 删 line 55-61「code_error 回退让设计调参」整段
- 删「凑答案会陷入循环」（旧 fear，新架构 P2 改参数不是凑答案）
- 改为「代码错误内部循环 fix，不回退；超限清空上下文重试；重跑仍失败升级失败」

**`agent_loader.py` `_BEHAVIOR_VARIANT_TEXT["solve_create"]`**：删末句「反复修不好标记 code_error 回退」。

**`behavior/audit_gate.md`、`CORE.md`、`artifact_writer.md`**：不动。

### 19.10 实施断点清单（归档造成的引用，§19 实施接回）

| 文件 | 断点 | §19 改法 |
|------|------|---------|
| `agent_loader.py` `_BEHAVIOR_VARIANTS` | question_sc/question_comp/creator/reviewer 死映射 | 删死映射，加 `"design": "artifact_writer"` |
| `agent_loader.py` `_BEHAVIOR_VARIANT_TEXT` | creator_solve/checkpoint_review 死文本 | 删 |
| `pipeline_graph.py` `QuestionNode` | legacy graph question 节点 | 改用 design P1 |
| `pipeline_graph.py` `SkeletonDesignNode/DistractorNode` | split graph 死节点 | 合并为 DesignNode（P1/P2） |
| `pipeline_graph.py` edges | `code_error→question/skeleton_design` | 删（solver 不回退） |
| `orchestrator.py` `_resolve_question_role` | 返回 question_sc/question_comp | 删，统一 design |
| `orchestrator.py` `_run_skeleton_design/_run_distractor_assembly/_run_question_only` | 死方法 | 重写为 `_run_design_pass1/pass2` |
| `orchestrator.py` `_run_solve` | code_error 回退 | 加超限清空重试，删回退 |
| `scheduler.py` `run_agent` | 无 skill_override | 加参数 |

### 19.11 与 §18 的关系（修正）

- §18 的 skeleton_design + distractor_assembly 双 agent → §19 合并为 design 双 pass（题面知识合一）
- §18 的 code_error 回退 → §19 删除（代码错误内部循环，不回退）
- §18 的"solver 修不好→回设计调参" → §19 改为"清空上下文重试→仍失败则升级失败"
- §18 的纪律①"大胆给" → §19 细化为"给经验值，不设计/不推演参数"
- §17.6 考点融合 → §19 保留，迁入 design_draft_skill Step4

## 20. 思考记忆（preserve/retain thinking）— 后续任务

> 日期: 2026-06-14 | 状态: 待实施

### 20.1 发现

实测发现：开启思考记忆（保留 reasoning_content 传回下一轮）后，工具调用场景的模型**反而不过度思考**——模型能"接着想"而非从头重推，减少重复思考 + 减少 tool-call 循环次数；KV 缓存复用还省 token。

### 20.2 当前缺口

- **本地 vLLM**：`remote_api.py` 已发 `chat_template_kwargs.preserve_thinking=True`（codex 加），但 scheduler 构造 assistant_msg 时**丢弃 reasoning_content**（line 780 等 4 处），导致请求侧"保留"而回传侧"丢弃"——preserve_thinking 实际未生效。
- **线上 API**：未开 `clear_thinking=False`（线上保留思考开关），也未传回 reasoning_content。

### 20.3 方案（待实施）

**全局开**（所有 agent 保留思考记忆，A 方案）：
1. scheduler 构造 assistant_msg 时，原样塞回模型返回的 reasoning_content（4 处：line 780, 1078, 1306, 1845）。约束：**原样传回，不截断/不重排**（线上要求，否则降效 + 影响缓存命中）。
2. `remote_api.py` 加线上 `clear_thinking=False` 控制（对应线上保留思考），默认开。
3. A/B 测试：先跑 §19 基线（思考被丢），再开思考记忆跑第二轮，对比 token 消耗 + 过度思考程度。

### 20.4 与 §19 的关系

思考记忆对 design P1（经验值出题）和 solve（brief-think-then-code）的 token 消耗影响最大。**先验证 §19 审核干净 + 跑基线，再做思考记忆改造对比**，隔离独立收益。

## 21. 概念题独立分支

> 日期: 2026-06-15 | 状态: 定型，已验证

### 21.1 核心思想

概念题（complexity=conceptual）太简单，不需要计算题的重骨架（design_card 10 section / exam_form K-雷达窄判断 / solve 代码验证）。独立分支：两个轻量智能体直通。

### 21.2 流程

```
outline → concept_creator（基于考点+知识，直接出题干+选项+答案+解析）
       → concept_review（审格式合规+事实性正确+题型期望对齐）
       → done
```

- 跳过 design_card / exam_form / solve / design2 / final
- concept_creator：极简 agent（25行 md，2 工具 write/read），关思考
- concept_review：概念审核标准（不审 K-雷达/条件充分性/参数）

### 21.3 与计算题分支的隔离

complexity=conceptual → `_run_concept_pipeline`（独立，不走 graph）
complexity=standard → `_run_graph`（split graph，完整骨架）

## 22. 建议驱动的迭代架构（最终架构）

> 日期: 2026-06-15 | 状态: 定型，待实施

### 22.1 核心范式转变（vs §19）

§19 的审核是**否决驱动**（pass/needs_fix → 打回重做）。§22 改为**建议驱动**：

| 旧范式（§19） | 新范式（§22） |
|---------------|--------------|
| 审核做判断（pass/fail）→ 打回重做 | 审核给建议（差距+建议）→ 优化迭代 |
| design 必须一次做对 | 先给合理的，后续迭代优化 |
| 规定怎么做（checklist/步骤） | 给目标+边界，自主决策 |

### 22.2 核心矛盾的解法

**矛盾**：单次做完会深度思考（54k）；强行拆步+规则会抑制能力。

**解法**：拆步，但单步内**在边界内激活能力**——给目标、给边界、给心态（不用一次到位），不规定步骤。

每步 prompt 设计原则：
```
你的目标：[这步要达成什么]
你的边界：允许[...] 禁止[...]
你的心态：后面有审核者会给建议，先基于经验和知识给出合理的，不用一次到位。
```

### 22.3 信息持久化边界

| 信息类型 | 持久化方式 | 理由 |
|---------|-----------|------|
| 自己内部的（思考、记忆、自检结论） | 思考记忆（不写文件） | 同 agent 多轮靠 session |
| 跨 agent 的（设计理念、融合意图、K-雷达） | **必须写文件** | 其他 agent 读文件获取 |

### 22.4 考点融合（同知识点多考察项，仅高难度）

考点融合 = 同一知识点的不同考察项融合（如 AVL 既考旋转辨析又考平衡因子计算），提高考察深度。**不是跨考点融合**。

- 仅 K3-K4 高难度题可选启用
- 简单题不需要
- **不是强行要求**，而是高难度时可选的能力
- 融合意图属于跨 agent 信息 → 写入 design_card.md（design_rationale 段或 question_structure_plan 段），确保多轮迭代不丢失

### 22.5 流程

```
① design_card（规划层，已定型）
  产出 design_card.md：hard_constraints + should_be + design_rationale + 考点融合意图（如有）
  所有跨 agent 设计意图持久化在此文件
    ↓
② design_出题（查缓存→基于知识设计题干+经验参数）
  目标：基于设计卡+缓存+知识，给出合理的初步题干和参数
  边界：允许基于知识的轻量判断；禁止数值推演
  心态：后面有审核者给建议，先基于经验给出合理的，不用一次到位
  产出 question.md：题干+设问+经验参数+设计说明（含设计意图）
    ↓
③ review_建议（审考察形式/考点对齐，给建议而非判断）
  目标：指出题干设计与蓝图的差距 + 优化建议
  输出：差距分析 + 建议（"这里可以更好"，不是 pass/fail）
  输出格式：修改类型标注（改题干/改参数）+ 具体建议
    差距小→进④ | 差距大→回②（带建议优化）
    ↓
④ design_参数验证（代码验证参数满足约束）
  目标：用 gen.py 验证参数是否满足 hard_constraints
  边界：代码算（exec），不脑内算
  心态：exec 验证，不脑内验证
    满足→⑤ | 不满足→改参数重 exec（代码循环，不回②）
    ↓
⑤ solve（解题代码）
    ↓
⑥ review_一致性（题干设问与 solve 答案对齐，给建议）
  目标：指出题干设问与求解结果的差距 + 建议
    差距小→⑦ | 差距大→修（带建议优化）
    ↓
⑦ final（输出）
```

### 22.6 审核给建议的格式

review 不输出 pass/needs_fix，而是输出**建议报告**：

```markdown
## 审核建议

### 差距分析
- 差距1：[题干设计与蓝图的差距描述]
  修改类型：改题干 / 改参数
  建议：[具体怎么改更好]

### 总体评估
差距小（可进入下一步）/ 差距大（建议回退优化）
```

### 22.7 修改策略（先题干后参数）

design 收到建议后：
1. **先改题干**（设问/表述/结构）——轻量，不需验证参数
2. **硬性参数约束才改参数**——改后由代码验证，不脑内验证
3. 改问法能解决的不改参数

### 22.8 与 §19/§21 的关系

- §19 的 design 双 pass + form_gate 否决驱动 → §22 改为建议驱动 + 审核拆分（结构审 + 一致性审）
- §21 概念题独立分支不变（概念题太简单，不需要 §22 的多步流程）
- §20 思考记忆不变（agent 内部多轮靠思考记忆，跨 agent 靠文档）

### 22.9 实施优先级

1. **review 从"判断"到"建议"**（最小改动，最大效果）
2. **拆审核**（结构审核 + 一致性审核分开）
3. **加参数验证步**（gen.py 代码验证，替代脑内推演）
4. **修改策略落地**（design 收到建议后先改题干后改参数）

## 23. 三分支定型 + 信息流打通 + 前端连接（实施完成）

> 日期: 2026-06-16 | 状态: 已实施，已验证

### 23.1 三分支架构（全部定型 + 验证）

后端三个分支，由 slot 的 `complexity` + `question_type` 决定路由：

| complexity | question_type | 分支 | 流程 |
|-----------|--------------|------|------|
| conceptual | 任意 | 概念题 | concept_creator 批量出题 → concept_review → final |
| standard | single_choice | 选择题 | design(占位符题干) → form_gate → design_solve(gen.py参数+选项) → form_gate2 → final |
| standard | comprehensive | 综合题 | 同选择题流程，design_solve 不做选项构造 |

**关键设计决策**：
- 概念题：多个 conceptual slot 合并批量出题（一次 LLM 调用出 N 道题）
- 计算题：交错设计——design 先出占位符题干（$T$, $S$ 等变量），form_gate 审骨架（不审参数），design_solve 填参数+求解
- 选择题选项：骨架层（design_card）锚定 option_plan（选项考什么参数+干扰模式），design_solve 的 gen.py 打印选项正确值 → LLM 改错为干扰项

### 23.2 信息流打通（往年题参考 → design_card 锚定）

```
compose 前段 grep 检索往年题 → reference_questions 写入 CONTRACT yaml
→ SlotBlueprint 加 reference_questions 字段
→ assemble 读 reference_questions 自动拉取完整题干拼入 assembled.md
→ design_card 读往年真题参考锚定设问结构（不发明结构）
```

### 23.3 审核层优化

| 审核环节 | 定位 | 审什么 | 不审什么 |
|---------|------|--------|---------|
| **form_gate**（review agent） | 审题干骨架 | 设问形式/考察覆盖度/设计一致性/条件充分性 | 不推演数值、不审参数约束 |
| **form_gate2**（review2 agent） | 审解题一致性 | 解题流程方法/设问-答案对应 | 不推演数值 |
| **final**（整合交付） | 整合交付 | 组装 question+solution + 检查表述修改落实 | 不重新审核数值/结构/一致性 |

**suggestion 档位**：表述小问题 → suggestion（不回退），结构偏离 → needs_fix（回退）
**review2 独立**：form_gate2 用 review2 agent + review2.md（不覆盖 form_gate 的 review.md）

### 23.4 gen.py 架构（交错设计两轮）

```
design 第一轮：占位符题干（$T$, $S=[x_i]$）+ 设计说明（参数约束）
  ↓ form_gate 审骨架
design_solve 第二轮：
  建模约束 + 给初始值 → gen.py 模拟机制 → exec 验证
  → 替换占位符为实际参数值 → write solution.md（Markdown文档，非代码）
  → 选择题额外：gen.py 打印选项正确值 → LLM 改错为干扰项
```

**核心原则**：初始值大胆给（经验值），后续参数由 gen.py 约束建模派生。gen.py 是约束建模（不是完整求解器），solve.py 是独立求解代码。

### 23.5 complexity 路由打通

```
前端 interact agent → 交接 YAML（每个 slot 含 complexity）
→ pipeline_trigger 读 YAML → 分离概念题/计算题
  → 概念题：合并批量出 + 拆分到各 slot 目录
  → 计算题：独立出（本地 2 并发 / 线上线性）
→ DocPipeline 三分支路由
```

**complexity 判断规则**：
- 往年试卷模式（Entry D）：沿用往年卷标记
- 考研模拟（Entry A）：默认全部 standard
- 自由出题（Entry C）：低难度概念辨析 → 询问教师 → conceptual
- 知识点出题（Entry B）：教师说"概念题"/"辨析" → conceptual

### 23.6 前端交互（plan 模式 + 方案卡片）

**interact agent = 出题的 plan 模式协调者**：
- 固定流程：范围收敛 → 知识点排布（多方案）→ 考察形式 → 确认 → 交接
- 自由空间：追问什么/怎么呈现/推荐什么 → 模型自主判断

**Entry D 方案卡片交互**：
- 右侧边栏：方案概览卡片（方案A/B/C + 设计理念 + 题数）
- 点击卡片 → 浮动面板替换聊天区（渲染完整方案 MD，含细粒度考点 `[ ]` + 返回按钮）
- 下拉选择方案 → 确认 → 进入出题

**方案格式**：
```
## 方案A — 侧重线性表与树

**第1题（选择题·2分·难度：简单）**：链表操作时间复杂度
- [ ] 删除操作的时间复杂度分析
- [ ] 插入操作的时间复杂度分析
...
```

### 23.7 后端↔前端连接链路

```
教师输入 → POST /api/v2/interact/sessions/{id}/turn
→ scheduler.run_conversation_turn(role="interact")
  → 加载 interact agent md + interact_core skill
  → agent 写 compose/interact_draft.md（草案）
→ draft_parser 解析为 DraftData（方案卡片 → scheme_md）
→ 前端渲染方案卡片
→ 教师选定 → agent 写交接 YAML（paper_request.yaml）
→ pipeline_trigger 读 YAML → 三分支路由 → DocPipeline 出题
→ display_result 展示结果
→ 教师可单题重生成（regenerate_question）
```

### 23.8 关键文件清单

| 文件 | 改动 |
|------|------|
| contracts.py | SlotBlueprint 加 complexity + reference_questions |
| pipeline_graph.py | split graph 边定义（suggestion/formal final） |
| orchestrator.py | 三分支路由 + 交错设计 task + concept_pipeline |
| scheduler.py | write_file auto-path + intermediate_text 限制 + interact max_tokens |
| doc_parser.py | REVIEW_STATUSES + FINAL_REVIEW_STATUSES + status 解析 |
| pipeline.yaml | thinking_budget + role_bindings + context_providers |
| compose/free_compose.py | 多套知识点排布方案 + complexity |
| compose/artifact_store.py | reference_questions 拉取往年题 |
| compose/pipeline_trigger.py | 概念题合并 + 本地并发/线上线性 + 结果拆分 |
| interact_core/SKILL.md | plan 模式 + 方案卡片格式 + complexity 规则 |
| interact.md | plan 模式定位 |
| c_codegen/SKILL.md | 两轮交错设计 + gen.py 约束建模 |
| design_card_v1/SKILL.md | 往年题锚定 + option_plan |
| review.md / review2.md | 三项定性审核 + 独立 review2 agent |
| final_review.md / SKILL | 整合交付（不重新审核） |
| conceptual_batch_skill/SKILL.md | 批量出题 + 分题格式契约 |
| draft_parser.py | 方案卡片解析 + complexity 标题清理 |
| schemas_interact_v2.py | DraftSlot scheme_md/scheme_label + scenario D |
| teacher-interact-lite-v7.html | 方案卡片渲染 + 浮动面板 + 选定方案 |
