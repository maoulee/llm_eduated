# 408 出题系统升级 Spec

> 综合 data-analyst / review-auditor / flow-architect 三方分析，2026-06-05

---

## 一、数据现状（questions.jsonl）

| 指标 | 值 |
|------|---|
| 总题目 | 2047 |
| 真题 (real_exam) | 671 (32.8%) |
| 模拟 (simulation) | 340 (16.6%) |
| 练习 (exercise) | 1036 (50.6%) |
| 有 knowledge_tags | 1668 (81.5%) |
| 有 subject | 671 (32.8%) — 仅真题 |
| 年份覆盖 | 2009-2026（18年） |

### 必须修复的问题

| # | 问题 | 影响 | 修复方案 |
|---|------|------|----------|
| 1 | exercise 的 question_type 全为 `unknown` | 1036题无法区分题型 | 有 options → `choice`，无 → `open` |
| 2 | 标签命名空间重叠（"CPU" vs "组成原理>CPU"） | 知识点检索召回不完整 | 建立扁平→层级映射表 |
| 3 | 2013年 subject 编码乱码（35条） | subject 字段不可用 | 从 knowledge_tags 反推 |
| 4 | simulation 几乎无 knowledge_tags（0.3%） | 340题无法按知识点检索 | LLM 标注或从题干推断 |
| 5 | real_exam 35条 unknown 类型 | 题型缺失 | 根据 options 判定 choice/open |

---

## 二、审核流程审计发现

### 2.1 K 值规则注入现状

| 角色 | K_RADAR_DEFINITIONS | K 值评估要求 |
|------|---------------------|-------------|
| analysis (L2) | 通过 blueprint 间接获取 k_target | 粗检（不逐维度打分） |
| review (L4) | 通过 blueprint 间接获取 k_target | **缺失** actual K1-K5 评估 |
| agents.py 旧版 | 无 | 有 quality_score 但已弃用 |
| AgentMD 新版 | 无 | **缺失** quality_score + improvement_suggestions |

### 2.2 三套 Prompt 并存问题

```
agents.py (AGENT_PROMPTS)  ← 旧版，实际已不使用
  ↓ 不一致 ↓
agents/*.md (AgentMD)       ← 新版，实际生效
  ↓ 不一致 ↓
scheduler.py (_GPT_SYSTEM_PROMPTS) ← Hybrid/WebGPT 模式使用
```

### 2.3 修复优先级

| P | 修复 | 文件 |
|---|------|------|
| 0 | AgentMD review 合约补 quality_score + improvement_suggestions | agents/review.md |
| 0 | AgentMD review skill 注入 K_RADAR_DEFINITIONS | skills/audit_fix/review_skill.md |
| 1 | review prompt 增加 actual K1-K5 评估要求 | agents/review.md |
| 1 | 统一三套 prompt 以 AgentMD 为权威源 | agents.py, scheduler.py |
| 2 | review 输出要求给出具体修正内容（非模糊建议） | agents/review.md |

---

## 三、题目数据抽取优化

### 3.1 真题数据结构化

从 questions.jsonl 的 real_exam 数据重建：

```
408_export/questions.jsonl
  ↓ 解析 + 清洗 ↓
data/structured_questions/
  real_exam/
    {year}/
      Q12.json  ← 结构化题目
      Q22.json
      ...
  simulation/
    {source_title}/
      {question_no}.json
  exercise/
    {knowledge_tag}/
      {question_no}.json
```

每条结构化记录包含：
```json
{
  "id": "2009_Q12",
  "source_type": "real_exam",
  "year": 2009,
  "slot_id": "Q12",
  "subject": "组成原理",
  "question_type": "single_choice",
  "knowledge_tags": ["组成原理>CPU>性能指标"],
  "knowledge_domain": "CO-4",
  "knowledge_family": "CO-4 > CPU > 性能指标",
  "stem": "...",
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "correct_answer": "C",
  "explanation": "...",
  "difficulty_level": null,  // 需 LLM 评估
  "examination_mode": null   // 需从经验卡匹配或 LLM 标注
}
```

### 3.2 知识点挂靠流程

```
真题题目
  ↓ knowledge_tags + 题干分析
  ↓ 匹配 computer_organization.md 知识点图谱
  ↓
挂靠到图谱节点
  ↓
确定 knowledge_domain (CO-1~CO-7)
  ↓
确定 knowledge_family (层级路径)
  ↓
基于 domain + family + question_type 匹配题位模板
```

对于缺少 knowledge_tags 的题目（simulation 340题），使用 LLM 从题干推断知识点。

### 3.3 题位信息重建

基于真题数据，统计每个题位的：
- 知识点分布频率 → 更新 `subject_distribution`
- 难度分布 → 更新 `difficulty_anchor`
- 考察模式频率 → 更新经验卡的 mode 分布
- 常见陷阱模式 → 更新经验卡的陷阱分析

---

## 四、单题生成流程（Practice Mode）

### 4.1 架构概览

```
用户需求（自然语言或结构化）
  ↓ Stage 0: Request Parser
PracticeRequest
  ↓ Stage 1: Knowledge Matcher
list[PracticeSlotAssignment]
  ↓ Stage 2: 确定性大纲构造（无 LLM）
list[SlotBlueprint]
  ↓ Stage 3: 组装经验文档 + 4层 Pipeline（100% 复用）
list[PipelineResult]
  ↓ Stage 4: 收集 + 统计
PracticeResult
```

### 4.2 关键设计决策

1. **Stage 2 确定性** — 知识点、难度、考察模式已确定，直接构造 SlotBlueprint，省 LLM 调用
2. **同题位多题隔离** — `Q15_p01`, `Q15_p02` 后缀 + 独立 workspace
3. **examination_mode 三级回退**：
   - 用户指定 → 使用
   - 匹配题位经验卡 → 按频率选取
   - 无匹配 → 通用模式兜底
4. **100% 复用现有 Pipeline** — `artifact_store`, `DocPipelineOrchestrator`, `DocScheduler`

### 4.3 新增模块

```
core_new/practice/
  request_parser.py      # Stage 0: 自然语言 → PracticeRequest
  knowledge_matcher.py   # Stage 1: 知识点检索 + 题位匹配
  practice_runner.py     # 主编排器
  practice_defaults.py   # 通用考察模式兜底数据
compose/cli.py           # 扩展 practice 子命令
```

### 4.4 CLI

```bash
# 结构化
compose practice --knowledge-points "Cache映射" --type single_choice --count 10 --difficulty 3 4

# 自然语言
compose practice --prompt "出10道关于Cache的选择题，难度3-4"
```

---

## 五、实施路线图

### Phase 1: 数据清洗（P0，本次可做）

1. 清洗 questions.jsonl — 修复 unknown 类型、编码乱码
2. 建立标签规范化映射表（扁平 → 层级）
3. 补充 simulation 的 subject 字段
4. 输出结构化 JSON 到 data/structured_questions/

### Phase 2: 审核修复（P0，已部分完成）

1. ✅ quality_score + improvement_suggestions 已加入 agents.py + scheduler.py
2. 🔲 AgentMD (agents/review.md) 补齐输出格式
3. 🔲 review skill 注入 K_RADAR_DEFINITIONS
4. 🔲 review 输出要求给出具体修正内容

### Phase 3: 真题数据抽取 + 题位重建（P1）

1. 真题知识点挂靠到图谱
2. 统计每个题位的知识点/难度/模式分布
3. 重建 slot_templates.json 和经验卡
4. 补充 OS/DS/CN 知识点图谱

### Phase 4: 单题生成 MVP（P1）

1. knowledge_matcher.py — 知识点检索 + 题位匹配
2. practice_runner.py — 确定性路径
3. CLI practice 子命令
4. 测试：出 5 道 Cache 选择题

### Phase 5: 增强功能（P2）

1. 自然语言需求解析（request_parser）
2. simulation/exercise 的 LLM 标签标注
3. 练习结果格式化输出
4. 无经验卡时的通用出题模式
