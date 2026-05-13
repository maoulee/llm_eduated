"""Test adversarial DomainCritic prompt with thinking ON vs OFF on 2009-12."""

import asyncio
import json
import time
import os
from dotenv import load_dotenv
load_dotenv()

from config import get_provider_config
from llm_providers_new import get_llm_provider

# Load the 2009-12 extraction result
with open("docs/extraction_sample_results.json") as f:
    results = json.load(f)
r = results[0]  # 2009-12

stem = r["raw_question"]["prompt"]
answer = r["raw_question"]["answer"]
structure = json.dumps(r["question_structure"], ensure_ascii=False)
knowledge_units = json.dumps(r["knowledge_units"], ensure_ascii=False)
trigger_rules = json.dumps(r["trigger_rules"], ensure_ascii=False)
reasoning_pattern = json.dumps(r["reasoning_pattern"], ensure_ascii=False)

# --- Old P5 prompt (current) ---
OLD_P5 = """你是一位数据质量审核专家。请检查以下从题目中抽取的结构化数据的一致性。

## 原始题目
题干：{stem}
答案：{answer}

## 抽取结果
题目结构：{structure}
知识单元：{knowledge_units}
触发规则：{trigger_rules}
推理模式：{reasoning_pattern}

## 要求
请检查以下一致性要求，并输出审核结果。注意：overall_quality_score是模型自评，仅表示model_validation_passed，不能作为正式入库标准。正式入库需要db_readiness.status为verified。

```json
{{{{
  "model_validation": {{{{
    "overall_quality_score": 0.0到1.0,
    "is_ready_for_review": true或false
  }}}},
  "db_readiness": {{{{
    "status": "candidate | verified | rejected",
    "requires_human_or_rule_check": true或false,
    "notes": "说明还需要什么检查才能入库"
  }}}},
  "checks": {{{{
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
  }}}},
  "missing_items": [
    "发现遗漏的内容"
  ],
  "inconsistencies": [
    "发现的不一致"
  ],
  "suggested_fixes": [
    {{{{
      "target": "需要修改的部分",
      "issue": "问题描述",
      "fix": "建议修改"
    }}}}
  ]
}}}}
```"""

# --- New adversarial DomainCritic prompt ---
NEW_CRITIC = """你是独立的408题库审稿人。以下候选条目来自一个不可靠的自动抽取系统，可能包含错误。

你不能假设它是正确的，也不能根据语言流畅度给高分。你的任务是找问题，不是维护原输出。

重要限制：
- 不要重写整份抽取结果
- 不要因为文本流畅就判定正确
- 每个问题必须给 evidence_path（具体字段路径）
- 如果无法判断，标记 uncertain，不要编造
- model_validation.overall_quality_score 不是证据
- db_readiness.status 只能由聚合器决定，你不能直接判 verified
- 如果 rule-based answer_consistency_check 已经判定答案一致，你不能声称答案矛盾，除非你指出具体反证

## 原始题目
题干：{stem}
答案：{answer}

## 候选抽取数据
题目结构：{structure}
知识单元：{knowledge_units}
触发规则：{trigger_rules}
推理模式：{reasoning_pattern}

请输出JSON：

```json
{{{{
  "answer_consistency_check": {{{{
    "raw_answer": "正确答案",
    "option_content": "对应选项内容",
    "derived_value": "推理模式推导出的结果",
    "is_consistent": true或false,
    "notes": "具体说明"
  }}}},
  "major_issues": [
    {{{{
      "issue_type": "answer_inconsistency | unsupported_trigger | overgeneralized_knowledge | weak_distractor_alignment | pattern_overfit | hallucination | other",
      "evidence_path": "具体字段路径",
      "evidence_text": "原文摘录",
      "reason": "为什么是问题",
      "severity": "high | medium | low",
      "suggested_action": "candidate | reject | needs_human_check"
    }}}}
  ],
  "minor_issues": [],
  "uncertain_items": [],
  "review_summary": "总结",
  "recommended_status": "candidate | rejected | needs_human_check"
}}}}
```"""


async def run_test(label, prompt_template, enable_thinking):
    print(f"\n{'='*60}")
    print(f"Test: {label}")
    print(f"Thinking: {enable_thinking}")
    print(f"{'='*60}")

    config = get_provider_config("glm5.1")
    if enable_thinking:
        config["request_timeout"] = 300.0
    provider = get_llm_provider(config)

    prompt = prompt_template.format(
        stem=stem,
        answer=answer,
        structure=structure,
        knowledge_units=knowledge_units,
        trigger_rules=trigger_rules,
        reasoning_pattern=reasoning_pattern,
    )

    start = time.time()
    messages = [[{"role": "user", "content": prompt}]]

    if enable_thinking:
        # Use generate_with_think_and_parse_batch to capture thinking
        results = await provider.generate_with_think_and_parse_batch(
            messages,
            enable_thinking=True,
            max_token=16384,
        )
        elapsed = time.time() - start
        think = results[0].get("think", "")
        answer_text = results[0].get("answer", "")
        think_len = len(think)
        print(f"Time: {elapsed:.1f}s")
        print(f"Thinking length: {think_len} chars")
        if think:
            print(f"Thinking excerpt: {think[:300]}...")
        print(f"\nAnswer JSON:")
        parsed = provider._parse_json(answer_text)
        if parsed:
            print(json.dumps(parsed, ensure_ascii=False, indent=2)[:2000])
        else:
            print(f"PARSE FAILED. Raw: {answer_text[:500]}")
    else:
        results = await provider.generate_json_batch(
            messages,
            max_tokens=8192,
            enable_thinking=False,
        )
        elapsed = time.time() - start
        print(f"Time: {elapsed:.1f}s")
        result = results[0]
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
        else:
            print("PARSE FAILED")

    return elapsed


async def main():
    print("Testing DomainCritic on 2009-12 (the 'answer contradiction' hallucination case)")
    print(f"Question: {stem[:80]}...")

    # await run_test("V0: Old P5 prompt, thinking OFF", OLD_P5, enable_thinking=False)
    # await run_test("V1: New adversarial prompt, thinking OFF", NEW_CRITIC, enable_thinking=False)
    await run_test("V2: New adversarial prompt, thinking ON", NEW_CRITIC, enable_thinking=True)


if __name__ == "__main__":
    asyncio.run(main())
