## 给教师的回复

您的需求已完整接收，分析如下：

| 项目 | 内容 |
|------|------|
| **任务类型** | 单题生成（single_question） |
| **科目** | 数据结构（由 AVL 树知识点安全推断） |
| **目标考点** | AVL 树旋转，重点考察 **LR 型**和 **RL 型**旋转的判断 |
| **题型** | 综合题 |
| **分值** | 10 分 |
| **难度** | 中等偏上（Level 4/5） |

> 📌 说明：科目"数据结构"为系统根据 AVL 树知识点自动推断。AVL 树属于数据结构 KG 中「树与二叉树 > 平衡二叉树」子树，安全无歧义。

需求信息完整，`single_question_route_gate` 已通过，正在为您生成单题蓝图并路由至出题流水线。

---

### intake_result.yaml

```yaml
schema_version: intake_result_v1

source:
  intake_type: human_input
  raw_input: "出一道关于AVL树旋转的综合题，要包含LR型和RL型的判断，难度中等偏上，10分"

task_type: single_question
task_confidence: high

intake_status: ready

confidence:
  level: medium
  missing_fields: []
  contradictions: []
  unverified_scope: false
  notes: "科目'数据结构'为安全推断（AVL树仅属于数据结构）；difficulty_level=4 对应'中等偏上'；score=10 明确指定"

routing:
  can_route: true
  next_action: run_single_pipeline
  next_input: slot_blueprint.yaml
  reason: "single_question_route_gate 通过：task_type/subject/知识点/题型/难度/分值均已明确"

assessment: null
knowledge_scope: null
question_config: null
difficulty:
  target: medium_hard
  level_numeric: 4
target_subject: 数据结构
primary_target_name: "AVL树旋转（LR型和RL型判断）"
keywords: ["AVL树", "旋转", "LR型", "RL型"]
```

---

### slot_blueprint.yaml

```yaml
schema_version: slot_blueprint_v1
slot_id: AVL_ROT_001

question_type: comprehensive
score: 10

target_subject: 数据结构
target_family: "数据结构 > 树与二叉树 > 平衡二叉树（AVL树）"
primary_target_name: "AVL树旋转（LR型和RL型判断）"
kg_node_path: "数据结构 > 树与二叉树 > 平衡二叉树 > 旋转操作"

difficulty_level: 4

k_target: ""
examination_mode: ""
teacher_annotation: "要求同时包含LR型和RL型旋转的判断，考察学生对不同失衡类型的识别与处理能力"

active_selection:
  mode_id: topic_selected
  mode_name: "教师指定知识点"
  selected_knowledge:
    - "AVL树旋转操作"
    - "LR型旋转（先左旋后右旋）"
    - "RL型旋转（先右旋后左旋）"
    - "平衡因子计算"
    - "失衡类型判断"
  candidate_pool_visible: []

excluded:
  modes: []
  knowledge:
    - "红黑树"
    - "B树"

constraints:
  must_include:
    - "LR型旋转场景"
    - "RL型旋转场景"
  avoid_repetition: true

confidence:
  level: medium

routing:
  can_route: true
  next_action: run_single_pipeline
```