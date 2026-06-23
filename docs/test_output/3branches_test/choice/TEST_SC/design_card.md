# TEST_SC 骨架设计文档

## status
draft

## blueprint_contract

```yaml
slot_id: TEST_SC
question_type: single_choice
score: 2
target_subject: 数据结构
primary_target_name: 二叉树带权路径长度
examination_mode: 计算型——WPL公式计算与树结构分析
k_target: 3
difficulty_level: 3
should_be:
  - 需理解WPL定义并代入计算
  - 考察哈夫曼树构造与WPL计算
should_not_be:
  - 不涉及跨知识点联动
  - 不要求计算哈夫曼编码本身
hard_constraints:
  - 单选题，4个选项
  - 分值2分
  - 难度3（中等）
```

## core_knowledge_intent

```
must_test:
  - WPL定义理解：WPL = Σ(叶子权值 × 该叶子到根的路径长度)
  - 哈夫曼树构造流程：贪心策略，每次合并权值最小的两棵子树
  - WPL公式代入计算能力

must_not_shift_to:
  - 不偏移到哈夫曼编码生成
  - 不偏移到BST/AVL等其他二叉树变体
  - 不偏移到树的其他性质（如高度、节点数关系）

coverage_success_criteria:
  - 学生能正确构造给定权值集合的哈夫曼树
  - 学生能准确计算WPL值
  - 干扰项能区分"理解WPL定义"与"仅会机械计算"的学生
```

## design_rationale

```
考察意图：
本题考察哈夫曼树的带权路径长度计算，这是数据结构中树与二叉树应用的核心考点。选择此考点组合的原因：
1. WPL计算是哈夫曼树最基础的定量考察方式，符合难度3的定位
2. 需要学生同时掌握"构造"和"计算"两个环节，区分度良好
3. 单选题形式适合考察计算结果，避免综合题的篇幅问题

区分学生掌握程度：
- 掌握良好的学生：能正确构造哈夫曼树并计算WPL
- 掌握一般的学生：可能构造错误但计算正确，或构造正确但计算错误
- 掌握较差的学生：概念混淆，如将WPL理解为路径长度之和

难度合理性：
- K1=3：需准确记忆WPL定义和哈夫曼构造规则
- K2=3：多步乘法加法计算，权值适中
- K3=3：哈夫曼构造3-5步流程
- K4=2：常规注意点，无深层陷阱
- K5=1：单知识点内部解决

考点融合意图：
本题为K3难度，不涉及高难度考点融合。聚焦单一知识点（WPL计算）的深度考察，通过干扰项设计覆盖"构造错误"和"概念混淆"两类常见错误模式。
```

## question_structure_plan

```
复用骨架来源：
- 往年二叉树题目多为概念辨析型（如练习题Q1考察高度与节点数关系、严格二叉树节点数性质）
- 本次为计算型单选题，参考往年单选题的设问结构：给定条件→求解特定量

子问设计（单问）：
- 子问1：考WPL计算（基础层+进阶层合并）
  - 给定一组叶子节点权值
  - 要求学生构造哈夫曼树并计算WPL
  - 参考往年单选题问法："具有X个叶子节点的此类树（ ）"→改为"给定权值集合{...}，其哈夫曼树的WPL为（ ）"

dependency_pattern：
- 单问结构，无子问间依赖
- 学生需先构造哈夫曼树（隐含步骤），再计算WPL（显式要求）
```

## option_plan（仅选择题）

```
考察的量：给定一组叶子权值，构造哈夫曼树后的WPL值

选项A（正确）：正确构造哈夫曼树后按WPL公式计算得到的值

选项B（干扰）：off-by-one深度计数错误
  - 错误模式：将根节点深度计为1而非0，导致所有叶子深度+1，WPL偏大
  - 对应错误：对正确值做"每个叶子深度+1"的变换

选项C（干扰）：哈夫曼构造策略错误
  - 错误模式：未按贪心策略（未始终合并最小两个权值），得到非最优树的WPL
  - 对应错误：构造过程错误导致的WPL偏大

选项D（干扰）：概念混淆
  - 错误模式：计算的是路径长度之和（Σ深度）而非带权路径长度（Σ权值×深度）
  - 对应错误：忽略权值权重，仅累加深度
```

## terminology_and_expression_constraints

```
必须用词：
- "带权路径长度"或"WPL"
- "哈夫曼树"或"Huffman树"
- "叶子节点"或"叶结点"
- "权值"或"权重"

限定语：
- 明确说明"路径长度"定义为"从根节点到该节点的边数"（根节点深度为0）
- 明确说明给定的是"叶子节点的权值集合"

禁止表述：
- 不使用"严格二叉树"等易混淆术语
- 不出现"哈夫曼编码"相关表述（避免偏移到编码生成）
- 不使用模糊的"最优二叉树"而不明确是哈夫曼树
```

## audit_focus

```
审核重点：

1. blueprint_contract 一致性：
   - 确认 examination_mode 为"计算型——WPL公式计算与树结构分析"
   - 确认 difficulty_level 为3
   - 确认 question_type 为 single_choice

2. core_knowledge_intent 覆盖：
   - must_test 三项是否都在题目中体现
   - must_not_shift_to 的偏移是否被干扰项设计避免

3. option_plan 合理性：
   - 四个选项是否覆盖"正确值"和三类典型错误模式
   - 干扰项数值是否与正确值有合理差异（避免靠猜测排除）

4. 参数设计约束（下游 gen.py 需满足）：
   - 权值数量：4-6个叶子节点
   - 权值大小：适中，避免过大数字
   - 权值不重复：避免合并顺序歧义
   - 计算结果：在合理范围内

5. teacher_annotation 体现：
   - "需理解WPL定义并代入计算"→体现在must_test和option_plan中
   - 考察模式→体现在干扰项设计中，覆盖计算错误和结构分析错误两类
```

## final_machine_contract

```yaml
slot_id: TEST_SC
question_type: single_choice
score: 2
examination_mode: 计算型——WPL公式计算与树结构分析
knowledge_point: 二叉树带权路径长度
knowledge_domain: 数据结构-5 > 树与二叉树
difficulty: 3
sub_questions: 1
dependency_pattern: 无（单问）
option_count: 4
correct_option_pattern: 正确WPL计算值
distractor_patterns:
  - off-by-one深度计数错误
  - 哈夫曼构造策略错误
  - 概念混淆（路径长度和 vs 带权路径长度）
```
