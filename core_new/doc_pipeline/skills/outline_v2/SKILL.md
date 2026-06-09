# outline_v2 技能

## 目标

组卷大纲的交互式提案技能，负责根据 intake 输出选择正确的 compose 路线，生成 outline_draft.md 供教师选择和批注。

**核心原则**：
- 交互层是信息拆分器和选择界面生成器，不承担深度推理
- 先卡片，后 YAML：LLM 输出卡片让教师选择，确认后才转正式机器文档
- KG 预加载（约束条件常驻），经验卡按需加载
- 检索由 LLM 驱动，grep 关键词由 LLM 生成
- 决策权在教师，每个关键节点由教师选择
- proposal 阶段禁止生成 CONTRACT/paper_selection/question/solution

## 路由规则

| 条件 | 路线 | 说明 |
|------|------|------|
| paper_request + 有经验卡 | 1 | 真题组卷 |
| slot_blueprint（有 primary_target_name） | 2 | 单知识点 |
| paper_request + 无经验卡 | 3 | 自由组卷 |

## 路线1：真题组卷

### 触发条件

- intake 输出为 `paper_request`
- 目标科目在 `data/question_experiences/` 目录有对应的经验卡

### 流程

**Step 1 [Python]：加载经验卡**
- 读取 `paper_request.yaml` 确定科目和 slot 范围
- 按需加载仅相关科目、相关 slot 的经验卡
- 输入：paper_request + 经验卡文件路径
- 输出：经验卡数据结构

**Step 2 [LLM]：渲染为 slot_cards**
- 模型：`config:interaction`（默认 api_vllm）
- 上下文：~2K/slot
- 任务：将 slot data 格式化为选择卡片
- Prompt 精髓："将以下 slot data 格式化为选择卡片。不要修改、重排或选择。只格式化。"
- 输出：slot_card 格式（每个 slot 一张卡片）

**Step 3 [教师]：确认/改选**
- 教师操作：confirm（确认推荐）| change_mode（改选模式）| exclude_knowledge（排除知识点）| remove（移除题位）
- 输入：slot_card 集合
- 输出：教师选择结果 + diff（如有）

**Step 4 [Python]：生成 outline_draft.md**
- 基于教师选择，生成 outline_draft.md
- 不包含 CONTRACT（proposal 阶段）
- 输出：outline_draft.md

### slot_card 输出格式

```yaml
slot_card:
  slot_id: Q12
  type: single_choice
  score: 2
  recommended_mode: 计算型——公式应用与单位换算
  recommended_frequency: 53.8%
  recommended_reason: 该模式在Q12题位出现频率最高，适合考察计算能力
  alternatives:
    - mode: 概念辨析型——核心定义与本质区分
      frequency: 23.1%
    - mode: 组合判断型——多维度特征匹配
      frequency: 23.1%
  applicable_knowledge:
    - CPU执行时间公式
    - 单位换算
    - 性能公式
  teacher_actions: [confirm | change_mode | exclude_knowledge | remove]
```

## 路线2：单知识点

### 触发条件

- intake 输出为 `slot_blueprint`
- 指定了 `primary_target_name`（具体知识点）

### 流程

**Step 1 [LLM]：生成 grep 关键词**
- 模型：`config:interaction`
- 上下文：~500 chars
- 输入：KG（仅相关科目）+ 知识点名称
- Prompt 精髓："给定知识点'{name}'，生成3-5个grep关键词搜索相关题目"
- 输出：关键词列表

**Step 2 [Python]：grep 检索**
- 检索 `data/question_experiences/*.md`
- 加权搜索：knowledge(+5), title(+3), body(+1)
- 输出：匹配题目列表

**Step 3 [LLM]：按模式分类归纳为 topic_mode_cards**
- 模型：`config:interaction`
- 上下文：~3-5K
- 任务：将检索结果按考察模式分类归纳
- Prompt 精髓："将以下N道关于{topic}的题目按考察模式分类。每个模式给：名称、数量、1句话描述、1-2个代表题。"
- 输出：topic_mode_card 集合

**Step 4 [教师]：选择模式**
- 教师操作：select_mode | combine_modes | change_knowledge
- 输入：topic_mode_card 集合
- 输出：教师选择结果

**Step 5 [Python]：生成 outline_draft.md**
- 基于教师选择，生成 outline_draft.md
- 输出：outline_draft.md

### topic_mode_card 输出格式

```yaml
topic_mode_card:
  id: avl_rotation_judgment
  title: 旋转类型判断
  knowledge: AVL树旋转操作
  sources:
    - kg_node: 数据结构 > 树与二叉树 > 平衡二叉树 > 旋转操作
    - question_bank_matches: 12
    - experience_references: 3
  modes:
    - name: 旋转类型判断型
      count: 7
      description: 给定插入序列或局部结构，判断 LL/LR/RL/RR 旋转类型
      suitable_types: [single_choice, comprehensive]
      difficulty: medium
      examples: [2018年408第5题, 2020年408第4题]
    - name: 平衡因子计算型
      count: 3
      description: 计算各节点平衡因子，判断是否失衡
      suitable_types: [single_choice]
      difficulty: easy
  teacher_actions: [select_mode | combine_modes | change_knowledge]
```

## 路线3：自由组卷

### 触发条件

- intake 输出为 `paper_request`
- 目标科目无经验卡，或教师选择自由组卷

### 流程（多轮交互）

**Step 1 [LLM]：基于 KG 生成知识点初稿**
- 模型：`config:free_compose`（默认 glm5.1）
- 上下文：KG（~5K）+ slot templates（~1K）
- 任务：为每个 slot 分配知识点和考察方向
- Prompt 特点：短（~500 chars），只要求输出 markdown 表格
- 输出：markdown 表格（题号 | 题型 | 知识点 | 考察方向 | 难度）

**Step 2 [Python]：KG 自动补全**
- 对每个知识点，从 KG 查询并补充考点详情
- 补充内容：父章节、兄弟知识点、子主题
- 输出：补全后的知识点列表

**Step 3 [教师]：批注/移除 → diff**
- 教师操作：批注、移除不想考的知识点
- 系统生成 diff 记录变更
- 输出：diff + 保留的知识点列表

**Step 4 [LLM]：对保留知识点执行路线2流程**
- 对每个保留的知识点，执行路线2的 grep + 归纳流程
- 模型：`config:interaction`
- 上下文：~5K/知识点
- 输出：每个知识点的 topic_mode_card

**Step 5 [教师]：选择 → Python YAML**
- 教师选择考察模式
- Python 生成 outline_draft.md
- 输出：outline_draft.md

### Step 1 Prompt 示例

```
基于以下知识点图谱，为一套计算机组成原理期末考试（10选择+4简答+2计算+1综合）
规划每个题位的考点。只输出知识点和考察方向，不需要详细内容。

知识点图谱:
{仅相关科目的KG}

输出格式:
| 题号 | 题型 | 知识点 | 考察方向 | 难度 |
```

## 模型路由（配置驱动）

所有模型选择通过 `config/pipeline.yaml` 中的 `model_routing` 配置决定，代码不硬编码。

```yaml
model_routing:
  # 交互层（渲染 + grep + 归纳）
  interaction: api_vllm

  # 自由组卷初稿（路线3 Step1）
  free_compose: glm5.1
```

## 权限边界

### proposal 阶段禁止

- 不生成 CONTRACT
- 不生成 paper_selection
- 不生成 question/solution

### 交互层不承担

- 不做全局优化
- 不做设计决策
- 不替教师做最终选择

## 上下文预算

| 任务 | 典型上下文 | 典型耗时 | 备注 |
|------|-----------|---------|------|
| 渲染经验卡（路线1） | ~2K/slot | <5s | 纯格式化 |
| grep 关键词生成 | ~200 chars | <2s | 简单生成 |
| 检索结果归纳 | ~3-5K | <10s | 分类任务 |
| 自由组卷初稿（路线3 Step1） | ~5-8K | 视模型 | 唯一可能需要推理的任务 |
| diff 后检索归纳（路线3 Step4-5） | ~3-5K/知识点 | <10s | 检索+分类 |
| YAML 生成 | N/A | <1s | Python，不经过LLM |

## 输出格式

### outline_draft.md（proposal 阶段）

- 包含教师可读层（当前推荐、候选替换池、教师可编辑说明）
- **不包含**机器选择契约（CONTRACT marker）
- 供教师批注、选择后，才转为 outline_approved.md（包含 CONTRACT）

### outline_approved.md（批准后）

- 包含完整的 outline v2 格式（4个 section）
- 包含 CONTRACT marker
- 可被 question_design layer 读取

## 禁止事项

- 不写具体题目
- 不设计选项/干扰项
- 不在单次 LLM 调用中把整张试卷作为一个 prompt
- 不在教师批准前生成 CONTRACT
- 不替教师做设计决策

## Phase 范围

本技能在 Phase 1 实现路线1（真题组卷），Phase 2 实现路线2（单知识点），Phase 3 实现路线3（自由组卷）。

当前版本仅定义路由规则和格式规范，具体实现分阶段推进。
