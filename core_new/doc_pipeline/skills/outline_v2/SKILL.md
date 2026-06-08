# outline_v2 技能

## 目标

生成符合 outline v2 格式的组卷大纲，包含教师可读层和机器契约层。

## outline v2 格式规范

### 整体结构

```markdown
# 试卷大纲

## 整体规划
- **difficulty_target**: 整体难度目标（1-5整数）
- **composition_rationale**: 整卷组卷思路（2-3句话）

## 1. 教师阅读版总览
（2-3段自然语言描述 + 题位总览表格）

## Q12（选择题）
### 当前推荐
（人读说明：为什么选这个模式、这个知识点）

### 候选替换池
- 模式A: 模式名称（简略信息）
- 模式B: 模式名称
...

### 教师可编辑说明
（教师可直接修改的命题说明区。教师可以删除、改写、保留内容。系统通过 gitdiff 识别变化。）

### 机器选择契约
```yaml
（机器可解析的契约字段）
```

## Q13（选择题）
...
（每个题位重复上述结构）
```

### 每题必须包含 4 个 section

1. **当前推荐**：人读说明，解释为什么选择这个模式和知识点
2. **候选替换池**：列出该题位所有可选考察模式的简略信息
3. **教师可编辑说明**：教师可直接修改的命题说明区，可删除、改写、保留内容
4. **机器选择契约**：YAML 格式的机器可解析契约

### 机器契约字段（完整列表）

```yaml
slot_id: Q12
question_type: single_choice
score: 2
target_subject: 计算机组成原理
target_family: CO-4 > CPU > 性能指标
primary_target_name: CPU执行时间公式
target_difficulty: 3
k_target: K1-K2平衡型
examination_mode: 计算型——公式应用与单位换算
active_selection:
  mode_id: 模式A
  mode_name: 计算型——公式应用与单位换算
  selected_knowledge:
    - CPU执行时间公式
    - CPI与MIPS计算
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
excluded:
  modes: []
  knowledge: []
```

### examination_mode 枚举值约束

- **必须精确复制自题位的"可选考察模式"标题**
- **禁止变形**：不允许添加英文翻译、简化名称或自创模式名
- 正确示例：`计算型——公式应用与单位换算`
- 错误示例：`计算型`、`Calculation - Formula Application`、`计算模式`

## 首轮模式行为规则

### 题位规划原则

1. **每个题位必须选择一个 active_selection**：从候选池中选择一个作为当前推荐
2. **候选池展示**：列出该题位所有可选考察模式的简略信息
3. **当前推荐详细说明**：解释为什么选择这个模式和知识点
4. **知识点覆盖**：确保整卷覆盖主要知识域，避免连续多题考同一知识点
5. **难度曲线**：前段基础稳定，中段适度区分，后段拉开差距

### 首轮模式输出检查清单

- [ ] 每个题位都有 active_selection
- [ ] 每个题位的候选池已列出
- [ ] examination_mode 精确复制自题位可选模式
- [ ] primary_target_name 是该模式适用知识点中的一个
- [ ] 整卷难度合理分布
- [ ] 知识点覆盖主要知识域
- [ ] 避免连续多题考同一知识点

## 修订模式行为规则

### 修订原则

1. **根据 gitdiff 识别老师删改**：只修改受影响的题位
2. **尊重老师删除和改写**：保持删除内容不恢复
3. **不恢复老师删除的内容**：如果老师删除了某个模式或知识点，不要恢复
4. **人读说明和机器选择契约必须保持一致**：两者必须同步更新
5. **如果老师删除了 active 模式，必须更换 active_selection**

### 修订模式处理流程

1. **读取 outline_approved.md**
2. **分析 gitdiff**：识别教师修改了哪些题位、哪些字段
3. **验证修改合法性**：
   - examination_mode 是否仍在候选池中
   - difficulty_level 是否在 1-5 范围内
   - 如果老师删除了 active 模式，选择新的 active_selection
4. **同步更新两个层次**：
   - `### 当前推荐`：反映修订后的意图
   - `### 机器选择契约`：YAML 字段同步更新
5. **保留教师可编辑说明**：不清空 `### 教师可编辑说明`，保留教师最终确认后的自然语言说明
6. **连带更新**：如果修订影响整卷难度分布，也更新 `## 整体规划` 和 `## 1. 教师阅读版总览`

### 修订模式输出检查清单

- [ ] 只修改受影响的题位
- [ ] 未修改的题位完整输出（不省略）
- [ ] examination_mode 仍在候选池中
- [ ] 人读说明和机器契约一致
- [ ] 如果老师删除了 active 模式，已更换新的 active_selection
- [ ] 整体规划和总览已同步更新（如需要）

## 格式约束

### YAML 代码块

- 必须使用 ```yaml ... ``` 格式
- 字段名和值之间用冒号加空格分隔
- 列表使用 `- ` 开头

### candidate_pool_visible 和 excluded

- 使用列表格式：`- 模式A: 模式名称`
- 如果为空列表：`[]`

### active_selection.selected_knowledge

- 使用列表格式：`- 知识点1`、`- 知识点2`
- 即使只有一个知识点也使用列表格式

## 错误示例

```yaml
# 错误：examination_mode 变形
examination_mode: 计算型

# 错误：selected_knowledge 不是列表
active_selection:
  selected_knowledge: CPU执行时间公式

# 错误：candidate_pool_visible 格式错误
candidate_pool_visible:
  - 计算型
  - 概念辨析型
```

## 正确示例

```yaml
# 正确：examination_mode 精确复制
examination_mode: 计算型——公式应用与单位换算

# 正确：active_selection 包含 mode_id + mode_name + selected_knowledge
active_selection:
  mode_id: 模式A
  mode_name: 计算型——公式应用与单位换算
  selected_knowledge:
    - CPU执行时间公式
    - CPI与MIPS计算

# 正确：candidate_pool_visible 使用模式 ID 扁平列表
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
```
