## 给教师的回复

收到您的需求，我来整理一下：

| 项目 | 您的要求 |
|------|---------|
| 类型 | 期末考试卷 |
| 科目 | 操作系统 |
| 范围 | 进程管理、内存管理 |
| 必考 | 银行家算法、页面置换算法 |
| 排除 | PV操作相关题目 |

**⚠️ 发现分数矛盾，需要您确认：**

当前题目分值加总：
- 5道选择题 × 2分 = **10分**
- 2道综合题（10分 + 20分）= **30分**
- **合计 = 40分**，与您要求的总分 **50分** 差了 **10分**

请选择如何处理：
1. **增加题目** — 补充一些题型来填满50分（推荐：再增加5道选择题/判断题，或1道简答题）
2. **调整分值** — 保持7道题不变，将某道综合题分值提高10分
3. **修改总分** — 将总分改为40分

另外，您对**难度偏好**有什么要求吗？默认推荐**中等难度为主**（Easy 30% / Medium 50% / Hard 20%）。

---

```yaml
schema_version: intake_result_v1

source:
  intake_type: human_input
  raw_input: "组一套操作系统期末卷，只考进程管理和内存管理这两章，必须包含银行家算法和页面置换算法，不能出现PV操作相关题目，总分50分，5道选择题每题2分，2道综合题分别10分20分"

task_type: paper
task_confidence: high

intake_status: needs_user_choice

confidence:
  level: blocked
  missing_fields:
    - difficulty.target
  contradictions:
    - "题目分值加总(5×2+10+20=40分)与声明的总分(50分)不一致，缺口10分"
  unverified_scope: false
  notes: "分数计算矛盾需教师确认，难度未指定可用默认中等"

routing:
  can_route: false
  next_action: ask_user
  next_input: null
  reason: "题目分数加总40分与总分50分矛盾，需要教师选择处理方式"

assessment:
  type: course_final
  subjects: ["操作系统"]
  total_score: 50
  duration_minutes: null

knowledge_scope:
  primary_chapters: ["进程管理", "内存管理"]
  focus_points: ["银行家算法", "页面置换算法"]
  excluded_points: ["PV操作"]
  coverage_strategy: focus_heavy

question_config:
  types:
    - type: single_choice
      count: 5
      score_per: 2
    - type: comprehensive
      count: 2
      scores: [10, 20]

difficulty:
  target: null
  distribution: null

target_subject: null
primary_target_name: null
keywords: null
```