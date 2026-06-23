## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 线性表 > 顺序表
- primary_target_name: 顺序表与链表的随机访问特性对比
- question_type: single_choice
- examination_mode: 概念辨析型——存储结构与随机访问特性

### 难度目标
- k_target: K1=4,K2=1,K3=1,K4=3,K5=1
- difficulty_level: 2
- difficulty_rationale: 概念辨析题，考查对顺序表与链表存储特性的精准理解，无需计算推演，但需辨析易混淆概念

### 结构要求
- option_count: 4
- distractor_strategy: 3个干扰项分别对应：①混淆顺序表/链表特性 ②引入无关数据结构特性 ③部分正确但表述不严谨
- condition_count: 1-2

### 参数约束
- 本题为纯概念辨析题，无数值参数
- 概念对比维度: 必须围绕"随机访问能力"核心差异
- 干扰项设计: 各干扰项对应不同错误认知路径，确保区分度

### 参考经验摘要
- 历史模式: Q1题位为概念辨析型选择题，考查基础概念精准理解
- 难度锚点: K1=4为该题位典型特征，要求高精度概念辨析
- 典型陷阱: 混淆O(1)随机访问与O(n)顺序访问、忽略指针域开销、按值查找与按位查找混为一谈
