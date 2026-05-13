# core_new/extraction_prompts.py

"""
Multi-pass extraction prompt templates for 408 question structuring.

Pipeline passes:
  P1: question_structure  - extract conditions, target, constraints, distractors
  P2: knowledge_units     - extract knowledge (merged concept+fact) and mechanisms
  P3: trigger_rules       - extract question signals as diagnostic/routing constraints
  P4: reasoning_pattern   - extract step-by-step reasoning procedure
  P5: link_and_validate   - cross-reference and consistency check
"""

PASS1_QUESTION_STRUCTURE = """你是一位408考研题目结构化分析专家。请对以下题目进行结构化分析。

## 题目
类型：{question_type}
题干：{stem}
答案：{answer}

## 要求
请严格按照以下JSON格式输出，不要输出其他内容：

```json
{{
  "question_id": "自动编号",
  "question_type": "{question_type}",
  "subject": "计算机组成原理 | 操作系统 | 数据结构 | 计算机网络",
  "year": "年份（如果题干中有年份信息）",
  "stem": "题干原文",
  "options": {{
    "A": "选项A内容",
    "B": "选项B内容",
    "C": "选项C内容",
    "D": "选项D内容"
  }},
  "correct_answer": "正确选项字母",
  "structure": {{
    "given_conditions": [
      "题目明确给出的条件1",
      "题目明确给出的条件2"
    ],
    "asked_target": "题目问的是什么",
    "hidden_constraints": [
      "隐含条件1（如：按字节编址、补码表示等）"
    ],
    "unit_constraints": [
      "单位或格式约束"
    ],
    "key_terms": [
      "题干中的关键术语"
    ]
  }},
  "distractor_analysis": [
    {{
      "option": "A",
      "content": "选项内容",
      "error_type": "该选项对应的错误类型",
      "targeted_misconception": "该选项诱发的误解"
    }}
  ]
}}
```"""

PASS2_KNOWLEDGE_UNITS = """你是一位408考研知识点分析专家。请根据以下题目的结构化信息，抽取题目涉及的知识单元。

## 题目信息
题干：{stem}
题目结构：{structure}
正确答案：{answer}

## 知识单元分类
只抽取两类：
- knowledge：基础知识（概念、定义、事实、公式、规则、数值约定等）
- mechanism：机制知识（系统机制如何影响推导和结果）

判断标准：
- knowledge 回答"需要知道什么"（定义、数值、公式、约定）
- mechanism 回答"为什么这个条件会改变推理路径或结果"

## 要求
请严格按照以下JSON格式输出：

```json
{{
  "knowledge_units": [
    {{
      "name": "知识名称",
      "description": "具体内容",
      "subtype": "definition | formula | rule | convention | term",
      "subject": "所属科目"
    }}
  ],
  "mechanisms": [
    {{
      "name": "机制名称",
      "description": "该机制如何影响推导",
      "affects_what": "影响哪些计算或判断",
      "common_misunderstanding": "常见误解",
      "subject": "所属科目"
    }}
  ]
}}
```

注意：
1. 只抽取本题直接涉及的知识，不要泛化
2. knowledge 统一归入 knowledge_units，不区分 concept/fact，subtype 只是弱标签
3. mechanism 重点关注那些"如果不知道就会做错"的机制
4. 每个知识单元应该是原子性的，不要把多个知识混在一起"""

PASS3_TRIGGER_RULES = """你是一位408考研题目信号分析专家。请分析以下题目中，题干的哪些信号决定了应该调用哪些机制或推理路径。

## 题目信息
题干：{stem}
题目结构：{structure}
涉及的知识单元：{knowledge_units}
正确答案：{answer}

## 触发规则定义
触发规则是系统内部的诊断和路由约束，用于识别题干信号如何影响解题路径。
触发规则不作为用户训练目标，而是服务于选题、诊断、出题约束和错因解释。

重点分析：
- 哪些题干关键词改变了推理路径？
- 如果忽略某个信号，会导致什么错误？
- 哪些信号容易被忽略？

## 要求
请严格按照以下JSON格式输出：

```json
{{
  "trigger_rules": [
    {{
      "name": "触发规则名称",
      "source_signals": [
        {{
          "signal_type": "keyword | asked_target | given_condition | qualifier",
          "value": "具体信号内容"
        }}
      ],
      "activation_condition": {{
        "logic": "AND | OR",
        "conditions": [
          "条件1",
          "条件2"
        ]
      }},
      "activates": {{
        "mechanism_names": ["被激活的机制名称"],
        "action": "activate | modify | block"
      }},
      "wrong_if_missing": [
        "如果漏掉这个触发会犯什么错误"
      ],
      "diagnostic_role": "missed_condition | wrong_route | mechanism_selection | blocks_wrong_pattern",
      "generation_constraints": {{
        "must_include_signals": ["出题时必须包含的题干信号"],
        "must_expose_failure_mode": "出题时必须能测试的错误模式",
        "expected_wrong_reason_if_missed": "用户漏掉此触发时的典型错误原因"
      }},
      "diagnostic_value": 0.0到1.0的数值,
      "difficulty": "easy | medium | hard"
    }}
  ],
  "negative_triggers": [
    {{
      "signal": "题干中的信号",
      "blocks_pattern": "被阻断的常见错误解法",
      "reason": "为什么这个信号使得该解法不适用"
    }}
  ]
}}
```

注意：
1. 重点关注"容易被忽略"的触发信号
2. 每个触发规则必须对应至少一种可能的错误
3. diagnostic_value 反映该触发规则对诊断用户能力的价值
4. diagnostic_role 说明该触发在诊断中的具体作用
5. generation_constraints 直接服务于后续出题蓝图生成"""

PASS4_REASONING_PATTERN = """你是一位408考研解题方法分析专家。请根据以下题目的完整信息，抽取出本题使用的推理模式。

## 题目信息
题干：{stem}
题目结构：{structure}
涉及的知识单元：{knowledge_units}
触发规则：{trigger_rules}
正确答案及解析：{answer}

## 推理模式定义
推理模式是一类题的可复用解题程序，由有序的推理步骤组成。每个步骤是一个原子操作。

## 要求
请严格按照以下JSON格式输出：

```json
{{
  "pattern_name": "推理模式名称",
  "subject": "所属科目",
  "applicable_conditions": [
    "适用条件1",
    "适用条件2"
  ],
  "steps": [
    {{
      "order": 1,
      "name": "步骤名称（原子操作）",
      "description": "这一步做什么",
      "input": "需要什么输入",
      "output": "产生什么输出",
      "required_knowledge": ["依赖的概念/公式/机制名称"],
      "common_error_at_this_step": "这一步容易犯什么错"
    }}
  ],
  "common_breakpoints": [
    {{
      "step": 在第几步容易断,
      "reason": "为什么容易断",
      "error_manifestation": "错了会表现出什么"
    }}
  ],
  "can_verify_with_code": true或false,
  "verification_approach": "如何用代码验证（如适用）"
}}
```

注意：
1. 步骤应该足够细粒度，每一步是一个明确的原子操作
2. 每一步都要标注依赖的知识
3. common_breakpoints 是最重要的字段——它直接服务于用户诊断"""

PASS5_LINK_AND_VALIDATE = """你是一位数据质量审核专家。请检查以下从题目中抽取的结构化数据的一致性。

## 原始题目
题干：{stem}
答案：{answer}

## 抽取结果
题目结构：{structure}
知识单元：{knowledge_units}
触发规则：{trigger_rules}
推理模式：{reasoning_pattern}

## 要求
请检查以下一致性要求，并输出审核结果：

```json
{{
  "validation_result": "pass | needs_revision",
  "checks": {{
    "structure_complete": true或false,
    "structure_notes": "说明",
    "knowledge_units_complete": true或false,
    "knowledge_notes": "说明",
    "triggers_accurate": true或false,
    "trigger_notes": "说明",
    "pattern_consistent": true或false,
    "pattern_notes": "说明",
    "distractors_aligned_with_errors": true或false,
    "distractor_notes": "说明"
  }},
  "missing_items": [
    "发现遗漏的内容"
  ],
  "inconsistencies": [
    "发现的不一致"
  ],
  "suggested_fixes": [
    {{
      "target": "需要修改的部分",
      "issue": "问题描述",
      "fix": "建议修改"
    }}
  ],
  "overall_quality_score": 0.0到1.0,
  "is_ready_for_db": true或false
}}
```"""
