### 1. 给教师的回复

老师您好，我收到了您的出题需求，但在进入生成之前，发现两处需要您确认的矛盾：

---

**🔴 矛盾一：科目与考点不匹配**
- 您指定科目为 **"数据结构"**
- 但 **"Cache地址映射"** 属于 **"计算机组成原理"** 的核心考点，不在数据结构知识范围内

**📌 请确认：**
- A. 科目应为 **计算机组成原理**（推荐）
- B. 坚持数据结构，由我为您推荐数据结构中相近的考点

---

**🔴 矛盾二：难度要求自相矛盾**
- 您要求 **"难度5星"**
- 同时要求 **"必须简单"**

**📌 请确认：**
- A. 难度5星（困难），不限制题目风格
- B. 题目要简单，改为 **难度2-3星**（推荐，与2分综合题匹配）
- C. 题目要简单，但保持5星标签（标签与实际难度不一致）

---

请回复您的选择，例如 **"A、B"**，我立即为您整理并生成。

---

### 2. 结构化输出

```yaml
schema_version: intake_result_v1

source:
  intake_type: human_input
  raw_input: "出一道数据结构的Cache地址映射题，要综合题但只要2分，难度5星但必须简单"

# 意图识别
task_type: single_question
task_confidence: high

# 状态
intake_status: needs_user_choice

# 置信度
confidence:
  level: blocked
  missing_fields:
    - target_family
    - kg_node_path
    - target_subject  # 待确认
    - difficulty_level  # 待确认
  contradictions:
    - "科目为数据结构，但Cache地址映射属于计算机组成原理"
    - "难度要求5星但必须简单，相互矛盾"
  unverified_scope: false
  notes: "需教师确认科目和难度后方可继续"

# 路由
routing:
  can_route: false
  next_action: ask_user
  next_input: null
  reason: "存在两处矛盾，需教师选择后才能确定target_subject和difficulty_level"

# 已提取的核心字段
target_subject: "数据结构"  # 待确认，可能应为计算机组成原理
primary_target_name: "Cache地址映射"
question_type: "comprehensive"
score: 2
difficulty_level: null  # 矛盾待解决
```