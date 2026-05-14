"""Re-run 6 failed/truncated subjective questions via local vLLM, score via GLM."""
import asyncio, json, os, re, sys, time
sys.stdout.reconfigure(line_buffering=True)
from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv()
from config import get_provider_config
from llm_providers_new import get_llm_provider

DATA_PATH = os.environ.get("SEED_QUESTIONS_FILE", "/home/dev/full_question.json")
MAIN_DST = "docs/subjective_reason_score.json"

RETRY_INDICES = [24, 51, 116, 167, 180, 193]
LOCAL_URL = "http://localhost:8000/v1"
LOCAL_MODEL = "qwen3.6"

REASON_PROMPT = """请解答以下考研408真题（主观题/综合题），给出完整的解答过程。

{question}

要求：
- 按小题逐一给出详细解答
- 写出计算过程和推导步骤
- 给出每小题的最终答案
- 将所有小题的最终答案汇总放在最后一行，格式：\\boxed{{小题1答案; 小题2答案; ...}}"""

SCORE_PROMPT = """你是考研408阅卷专家。请评分以下主观题作答。

## 题目
{question}

## 参考答案
{reference}

## 考生作答
{answer}

请自由评价该考生的作答质量。按小题逐一分析得分点覆盖情况，最后给出总分。
不需要严格XML格式，自由书写即可。最后单独一行用以下格式给出总分：

<score>得分/满分</score>"""

def parse_score(text):
    m = re.search(r'<score>\s*([\d.]+)\s*/\s*(\d+)\s*</score>', text)
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)

async def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    with open(MAIN_DST, encoding="utf-8") as f:
        main_data = json.load(f)

    main_by_idx = {e["_index"]: e for e in main_data}
    client = AsyncOpenAI(base_url=LOCAL_URL, api_key="EMPTY")

    print(f"Re-running {len(RETRY_INDICES)} failed questions\n")

    # Reason
    print("Phase 1: Reasoning")
    reason_results = {}
    for idx in RETRY_INDICES:
        q = questions[idx]
        prompt = REASON_PROMPT.format(question=q.get("prompt", ""))
        t0 = time.time()
        try:
            resp = await client.chat.completions.create(
                model=LOCAL_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=1.0, top_p=0.95, max_tokens=8192,
                extra_body={"chat_template_kwargs": {"enable_thinking": True}},
            )
            dt = time.time() - t0
            content = resp.choices[0].message.content or ""
            m = re.match(r'<think[^>]*>(.*?)</think[^>]*>(.*)', content, re.DOTALL)
            answer = m.group(2).strip() if m else content
            reason_results[idx] = {"answer": answer, "time": dt}
            print(f"  [{idx}] {len(answer)}字 ({dt:.0f}s)")
        except Exception as e:
            print(f"  [{idx}] FAILED: {e}")
            reason_results[idx] = {"answer": "", "time": 0}

    # Score
    print("\nPhase 2: Scoring (GLM thinking OFF)")
    glm_config = get_provider_config("glm5.1")
    provider = get_llm_provider(glm_config)

    for idx in RETRY_INDICES:
        rr = reason_results[idx]
        if not rr["answer"]:
            print(f"  [{idx}] SKIPPED (no answer)")
            continue
        q = questions[idx]
        msg = SCORE_PROMPT.format(
            question=q.get("prompt", "")[:3000],
            reference=q.get("answer", "")[:3000],
            answer=rr["answer"][:6000],
        )
        t0 = time.time()
        try:
            res = await provider.generate_with_think_and_parse_batch(
                [[{"role": "user", "content": msg}]],
                enable_thinking=False, max_token=4096,
            )
            dt = time.time() - t0
            scoring = res[0].get("answer", "") if res else ""
            got, mx = parse_score(scoring)
            tag = f"{got}/{mx}" if got is not None else "?/?"
            print(f"  [{idx}] {tag} ({dt:.0f}s)")

            # Update main data
            main_by_idx[idx].update({
                "model_answer": rr["answer"],
                "model_answer_len": len(rr["answer"]),
                "scoring_text": scoring,
                "score_got": got,
                "score_max": mx,
                "reason_time": rr["time"],
                "score_time": dt,
            })
        except Exception as e:
            print(f"  [{idx}] FAILED: {e}")

    # Save updated main data
    with open(MAIN_DST, "w", encoding="utf-8") as f:
        json.dump(main_data, f, ensure_ascii=False, indent=2)
    print(f"\nUpdated {MAIN_DST}")

if __name__ == "__main__":
    asyncio.run(main())
