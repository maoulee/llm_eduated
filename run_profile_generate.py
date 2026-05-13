"""
Simulate user profiles and generate questions using local vLLM.

Each profile represents a different student type with specific weaknesses.
The model generates targeted questions based on the profile.

Uses local vLLM (Qwen3.6-27B) for inference.
"""

import asyncio
import json
import os
import time
from typing import Any, Dict

from dotenv import load_dotenv
load_dotenv()

from config import get_provider_config
from llm_providers_new import get_llm_provider


PROFILES = [
    {
        "profile_id": "weak-crc",
        "name": "小王",
        "weakness": "数据链路层 CRC 校验",
        "description": "计算机组成原理基础较好，但对数据链路层的差错检测机制（尤其是CRC循环冗余校验）理解薄弱。经常混淆模2除法和普通除法，搞不清生成多项式和校验码的关系。",
        "target_subject": "计算机网络",
        "knowledge_gaps": ["CRC校验原理", "模2除法", "生成多项式"],
    },
    {
        "profile_id": "weak-complement",
        "name": "小李",
        "weakness": "补码运算与溢出判断",
        "description": "对补码的加减法运算理解不够深入，尤其对溢出判断条件（双符号位法、进位法）掌握不牢。容易混淆正溢出和负溢出的条件。",
        "target_subject": "计算机组成原理",
        "knowledge_gaps": ["补码加减法", "溢出判断", "符号位扩展"],
    },
    {
        "profile_id": "weak-binary-tree",
        "name": "小张",
        "weakness": "二叉树性质与遍历",
        "description": "数据结构整体尚可，但完全二叉树的性质推导（叶子节点数、深度计算）经常出错。对层次遍历和序列重建二叉树也不熟练。",
        "target_subject": "数据结构",
        "knowledge_gaps": ["完全二叉树性质", "二叉树遍历", "线索二叉树"],
    },
    {
        "profile_id": "strong-all",
        "name": "小陈",
        "weakness": "无显著弱点",
        "description": "各科基础扎实，但缺乏综合题的解题策略。面对跨知识点的综合题时，不知道如何拆分问题。",
        "target_subject": "综合",
        "knowledge_gaps": ["跨科目综合分析", "复杂问题拆解"],
    },
]

GENERATE_PROMPT = """你是一位408考研出题专家。请根据以下学生画像，出一道针对性的考研真题风格题目。

## 学生画像
- 姓名：{name}
- 薄弱点：{weakness}
- 详细描述：{description}
- 目标科目：{target_subject}
- 知识缺口：{knowledge_gaps}

## 出题要求
1. 题目难度：中等偏难（适合针对性训练）
2. 题型：根据知识特点选择最合适的题型（单选题/计算题/综合题）
3. 针对性：题目必须直击该学生的知识缺口
4. 格式：严格按照考研真题格式

请输出JSON：

```json
{{
  "profile_id": "{profile_id}",
  "question_type": "单选题|计算题|综合题",
  "subject": "所属科目",
  "prompt": "完整题目文本",
  "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
  "answer": "正确答案",
  "explanation": "详细解析",
  "targeted_weakness": "针对的具体弱点",
  "difficulty": "medium|hard"
}}
```"""


async def generate_for_profile(provider, profile: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a question targeted at a specific student profile."""
    prompt = GENERATE_PROMPT.format(
        profile_id=profile["profile_id"],
        name=profile["name"],
        weakness=profile["weakness"],
        description=profile["description"],
        target_subject=profile["target_subject"],
        knowledge_gaps=", ".join(profile["knowledge_gaps"]),
    )

    messages = [[{"role": "user", "content": prompt}]]
    results = await provider.generate_json_batch(
        messages, max_tokens=4096, enable_thinking=True,
    )

    raw = results[0] if results else {}
    return {
        "profile_id": profile["profile_id"],
        "profile_name": profile["name"],
        "weakness": profile["weakness"],
        "generated": raw,
    }


async def main():
    config = get_provider_config("api_vllm")
    served_model = os.environ.get("VLLM_SERVED_MODEL")
    if served_model:
        config["model_path"] = served_model
    provider = get_llm_provider(config)
    print(f"Provider: {config.get('model_path', 'api_vllm')}")

    all_results = []
    total_start = time.time()

    for i, profile in enumerate(PROFILES):
        pid = profile["profile_id"]
        name = profile["name"]
        print(f"\n[{i+1}/{len(PROFILES)}] Generating for {name} (weakness: {profile['weakness'][:30]}...)")
        start = time.time()

        result = await generate_for_profile(provider, profile)
        elapsed = time.time() - start
        result["elapsed"] = elapsed
        all_results.append(result)

        gen = result.get("generated") or {}
        q_type = gen.get("question_type", "?") if isinstance(gen, dict) else "?"
        prompt_preview = (gen.get("prompt", "")[:80] if isinstance(gen, dict) else str(gen)[:80])
        answer = gen.get("answer", "?") if isinstance(gen, dict) else "?"
        print(f"  {elapsed:.1f}s | {q_type} | answer={answer}")
        print(f"  {prompt_preview}...")

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"Total: {len(PROFILES)} profiles in {total_elapsed:.1f}s")

    output_path = os.path.join(os.path.dirname(__file__), "docs", "profile_generate_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
