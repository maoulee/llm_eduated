## 给教师的回复

老师您好！您的需求我已完整记录，信息非常清晰，可以直接进入组卷流程。以下是我对需求的理解：

| 项目 | 您的要求 | 我的理解 |
|------|---------|---------|
| **试卷类型** | 408考研模拟卷 | 四科目全覆盖，按考研标准分值分布 |
| **总分 / 时长** | 150分 / 180分钟 | 标准考研配置 |
| **整体难度** | 偏难 | hard 档，难题占比约50% |
| **数据结构** | 简单点 | 该科降为 easy-medium，以基础题和中等题为主 |
| **操作系统** | 出些冷门考点 | 在OS部分纳入非常规/低频考点 |
| **排除项** | 不出 Cache、虚拟内存 | 从组卷范围中明确排除 |

**关于题型配置的默认方案**（按408考研标准）：
- 单选题：40题 × 2分 = 80分
- 综合应用题：7题 = 70分
- 各科分值：数据结构 ~45分 / 组成原理 ~45分 / 操作系统 ~35分 / 计算机网络 ~25分

如果没有调整，我将按此方案提交组卷。请问需要修改吗？

---

## 结构化输出：intake_result

```yaml
schema_version: intake_result_v1

source:
  intake_type: human_input
  raw_input: "一套完整的408考研模拟卷，难度整体偏难，数据结构部分简单点，操作系统部分要出些冷门考点，不要出Cache和虚拟内存的题，总分150分，180分钟"

# 意图识别
task_type: paper
task_confidence: high

# 状态
intake_status: ready

# 置信度
confidence:
  level: high
  missing_fields: []
  contradictions: []
  unverified_scope: false
  notes: >-
    教师需求清晰完整。408四科全覆盖，难度偏难但数据结构降档，
    操作系统要求冷门考点，明确排除Cache和虚拟内存。
    题型配置按408考研标准默认值，未检测到矛盾。

# 路由
routing:
  can_route: true
  next_action: run_compose
  next_input: paper_request.yaml
  reason: "paper_route_gate 通过：全部必需字段已填充，无矛盾，可路由至组卷团队"

# 核心字段
assessment:
  type: kaoyan_408
  subjects: ["数据结构", "计算机组成原理", "操作系统", "计算机网络"]
  total_score: 150
  duration_minutes: 180

knowledge_scope:
  primary_chapters: ["408全部章节"]
  focus_points: []
  excluded_points: ["Cache", "虚拟内存"]
  coverage_strategy: exam_weighted
  subject_difficulty_override:
    数据结构: easy_medium
    操作系统: cold_topics_required

question_config:
  types:
    - type: single_choice
      count_range: [40, 40]
      score_per: 2
    - type: comprehensive
      count_range: [7, 7]
      score_range: [70, 70]

difficulty:
  target: hard
  distribution:
    easy: 15
    medium: 35
    hard: 50
  anchor_source: kaoyan_408

teacher_preferences:
  require: ["操作系统冷门考点"]
  avoid: ["Cache", "虚拟内存"]
  style_notes: >-
    整体偏难。数据结构部分难度降低至基础-中等水平。
    操作系统部分需纳入冷门/低频考点。
```

---

## 结构化输出：paper_request.yaml（下游文件）

```yaml
schema_version: paper_request_v1

source:
  intake_type: human_input
  pre_extracted_data: null

assessment:
  type: kaoyan_408
  subjects:
    - 数据结构
    - 计算机组成原理
    - 操作系统
    - 计算机网络
  total_score: 150
  duration_minutes: 180

knowledge_scope:
  primary_chapters:
    - "数据结构 > 全部章节"
    - "计算机组成原理 > 全部章节"
    - "操作系统 > 全部章节"
    - "计算机网络 > 全部章节"
  focus_points: []
  excluded_points:
    - Cache
    - 虚拟内存
  coverage_strategy: exam_weighted
  subject_difficulty_override:
    数据结构:
      target: easy_medium
      distribution:
        easy: 40
        medium: 50
        hard: 10
    操作系统:
      cold_topics_required: true
      notes: "需纳入冷门/低频考点，避免常见高频题"

question_config:
  types:
    - type: single_choice
      count_range: [40, 40]
      score_per: 2
      subject_allocation:
        数据结构: 10
        计算机组成原理: 11
        操作系统: 11
        计算机网络: 8
    - type: comprehensive
      count_range: [7, 7]
      score_range: [70, 70]
      subject_allocation:
        数据结构: 2
        计算机组成原理: 2
        操作系统: 2
        计算机网络: 1

difficulty:
  target: hard
  distribution:
    easy: 15
    medium: 35
    hard: 50
  anchor_source: kaoyan_408

retrieval_policy:
  prefer_existing: true
  generate_gap: true
  max_scan: 2000
  top_k_per_slot: 3

teacher_preferences:
  require:
    - "操作系统冷门考点"
  avoid:
    - "Cache"
    - "虚拟内存"
  style_notes: >-
    整体难度偏难，接近考研真题上限。
    数据结构部分降档为基础-中等难度，不出偏难怪题。
    操作系统部分需要覆盖冷门考点，如：进程通信细节、磁盘调度高级算法、
    文件系统实现细节等低频但大纲范围内知识点。
    组成原理和计算机网络按正常偏难标准出题。

constraints:
  allow_similar_to_past: false
  min_knowledge_diversity: 4
  subject_balance_notes: >-
    各科分值参考408标准：数据结构~45分，组成原理~45分，
    操作系统~35分，计算机网络~25分。综合题大题分数允许微调。
```