## 给教师的回复

收到！我来确认一下您的需求：

✅ **已明确的信息：**
- **任务类型：** 出试卷（"搞几张卷子"）
- **科目：** 计算机网络 + 计算机组成原理
- **难度：** 偏简单（基础薄弱、目标是及格）
- **数量：** 多套

❓ **还需要确认几个关键点：**

**1. 考试类型是什么？**（影响出题风格和题型分布）
- A. 课程期末考试 → 默认推荐
- B. 期末模拟卷（练习用）
- C. 考研408真题风格
- D. 其他

**2. 每套卷子多少分？多长时间？**
- 默认推荐：**100分 / 120分钟**，如需调整请告知

**3. 知识范围？**
- A. 两门课全部内容都覆盖 → 默认推荐
- B. 有指定的重点章节（请告诉我哪些）
- C. 排除某些章节（请告诉我哪些不考）

> 💡 您可以直接说"按默认"，我就按 **期末考试 / 100分120分钟 / 全覆盖** 来准备。

---

```yaml
# intake_result.yaml
schema_version: intake_result_v1

source:
  intake_type: human_input
  raw_input: "搞几张卷子，学生基础不太好，考及格就行，别太难，计算机网络和那个什么组成原理都要有"

task_type: paper
task_confidence: high

intake_status: collecting

confidence:
  level: low
  missing_fields:
    - assessment.type
    - assessment.total_score
    - assessment.duration_minutes
    - knowledge_scope.primary_chapters
    - knowledge_scope.focus_points
  contradictions: []
  unverified_scope: false
  notes: "教师明确了多套卷子，当前先收集第一套的需求。难度倾向easy，目标及格率。"

routing:
  can_route: false
  next_action: ask_user
  next_input: null
  reason: "缺少考试类型、分数/时长、知识范围等关键信息，paper_route_gate未通过"

assessment:
  type: null
  subjects: ["计算机网络", "计算机组成原理"]
  total_score: null
  duration_minutes: null

knowledge_scope:
  primary_chapters: []
  focus_points: []
  excluded_points: []
  coverage_strategy: null

question_config: null

difficulty:
  target: easy
  distribution: null
  anchor_source: null

teacher_preferences:
  require: []
  avoid: []
  style_notes: "学生基础薄弱，目标是及格，难度要偏低"
```