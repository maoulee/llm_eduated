# 试卷大纲

## 整体规划

- **difficulty_target**: 中等偏难 (3.2/5)
- **composition_rationale**: 本次组卷覆盖计算机组成原理与数据结构两大领域。选择题侧重基础概念与计算，综合题考察跨子系统分析能力。知识点不重复覆盖。

## 1. 教师阅读版总览

本卷共3道试题，其中选择题2道（Q12、Q6），综合应用题1道（Q43）。
Q12考察CPU性能公式计算，Q6考察树与二叉树的概念辨析，Q43考察存储层次与Cache性能的综合分析。

| 题位 | 题型 | 分值 | 考察模式 | 核心知识点 |
|------|------|------|----------|------------|
| Q12  | 选择题 | 2   | 计算型——公式应用与单位换算 | CPU执行时间公式 |
| Q43  | 综合应用题 | 10 | 多子系统耦合性能评估 | Cache缺失分析与平均访存时间 |
| Q6   | 选择题 | 2   | 概念辨析型——性质与边界判定 | 哈夫曼树性质与前缀编码 |

## Q12（选择题）

### 当前推荐

**考察模式**: 计算型——公式应用与单位换算
**核心知识点**: CPU执行时间公式 ($T = IC \\times CPI / f$)
**推荐理由**: Q12历史上53.8%为计算型，此模式频率最高且能考察公式理解与单位换算的准确性。

### 候选替换池

- **模式A**: 计算型——公式应用与单位换算（推荐，频率7/13）
- **模式B**: 概念辨析型——核心定义与本质区分（频率3/13）
- **模式C**: 组合判断型——多维度特征匹配（频率3/13）

### 教师可编辑说明

本题考察CPU性能指标的综合计算，重点在于执行时间公式中各变量的物理意义及单位换算。
要求学生能区分主频、CPI、指令数之间的正比/反比关系，并能处理GHz到秒的单位转换。
难度定位K2-K3，适合中等偏上学生。

### 机器选择契约

```yaml
slot_id: Q12
question_type: single_choice
score: 2
target_subject: 计算机组成原理
target_family: CO-1 > 计算机系统概述
primary_target_name: CPU执行时间公式
target_difficulty: 3
k_target: K2K3
examination_mode: 计算型——公式应用与单位换算
active_selection:
  mode_id: 模式A
  mode_name: 计算型——公式应用与单位换算
  selected_knowledge:
    - CPU执行时间公式
    - 主频与时钟周期换算
    - CPI概念与计算
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
excluded:
  modes: []
  knowledge: []
```

## Q43（综合应用题）

### 当前推荐

**考察模式**: 多子系统耦合性能评估
**核心知识点**: Cache缺失分析与平均访存时间（AMAT）计算
**推荐理由**: 综合题需要考察跨子系统耦合分析能力，Cache与主存交互是最典型的场景，能综合考察地址映射、缺失率计算、时序分析。

### 候选替换池

- **模式A**: 多子系统耦合性能评估（推荐，4次出现）
- **模式B**: 底层机制语义推演（3次出现）
- **模式C**: 架构约束下的协同设计（3次出现）

### 教师可编辑说明

本题以Cache-主存层次为场景，要求考生分析地址映射机制、计算缺失率与平均访存时间，
并结合总线传输时序进行综合性能评估。设3-4个子问，从基础参数提取到宏观性能合成，
层层递进。难度定位K3-K4，需要有较强的系统级思维能力。

### 机器选择契约

```yaml
slot_id: Q43
question_type: comprehensive
score: 10
target_subject: 计算机组成原理
target_family: CO-3 > 存储器层次结构
primary_target_name: Cache缺失分析与AMAT计算
target_difficulty: 4
k_target: K3K4K5
examination_mode: 多子系统耦合性能评估
active_selection:
  mode_id: 模式A
  mode_name: 多子系统耦合性能评估
  selected_knowledge:
    - Cache直接映射与组相联映射
    - 平均访存时间AMAT计算
    - 总线传输时序分析
    - CPU利用率计算
    - DMA传输开销计算
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
excluded:
  modes: []
  knowledge: []
```

## Q6（选择题）

### 当前推荐

**考察模式**: 概念辨析型——性质与边界判定
**核心知识点**: 哈夫曼树性质与前缀编码
**推荐理由**: Q6历史40%为概念辨析型，哈夫曼树是高频考点，适合考察学生对树结构性质的精确理解。

### 候选替换池

- **模式A**: 概念辨析型——性质与边界判定（推荐，频率4/10）
- **模式B**: 逻辑推理型——过程映射与逆向分析（频率3/10）
- **模式C**: 机制/数值分析型——特定结构下的极值/状态计算（频率2/10）
- **模式D**: 组合判断型——多选合一（频率1/10）

### 教师可编辑说明

本题考察哈夫曼树的基本性质（非完全二叉树、WPL最小性）和前缀编码的定义。
要求学生能区分哈夫曼树与完全二叉树、最优二叉树的概念边界。
难度定位K1-K2，侧重概念清晰度。

### 机器选择契约

```yaml
slot_id: Q6
question_type: single_choice
score: 2
target_subject: 数据结构
target_family: DS-5 > 树与二叉树
primary_target_name: 哈夫曼树性质与前缀编码
target_difficulty: 2
k_target: K1K4
examination_mode: 概念辨析型——性质与边界判定
active_selection:
  mode_id: 模式A
  mode_name: 概念辨析型——性质与边界判定
  selected_knowledge:
    - 哈夫曼树性质
    - 前缀编码定义
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
  - 模式D
excluded:
  modes: []
  knowledge: []
```
