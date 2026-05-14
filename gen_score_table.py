"""Generate year-by-year score table + build user profile for generation test.

Reads:
  - docs/batch_200_results_v2.json (MCQ results)
  - docs/subjective_reason_score.json (subjective results)
  - /home/dev/full_question.json (original questions)
  - docs/wrong_mcq_extractions.json (knowledge extractions)

Outputs:
  - docs/year_score_table.txt (year-by-year score table)
  - Uses extracted knowledge + profile for generation test
"""
import json
import re
import sys
import asyncio

sys.stdout.reconfigure(line_buffering=True)

from dotenv import load_dotenv
load_dotenv()
from config import get_provider_config
from llm_providers_new import get_llm_provider
from core_new.generation_team import GenerationPipeline

DATA_PATH = "/home/dev/full_question.json"
MCQ_RESULTS = "docs/batch_200_results_v2.json"
SUBJ_RESULTS = "docs/subjective_reason_score.json"
EXTRACTIONS = "docs/wrong_mcq_extractions.json"
DST_TABLE = "docs/year_score_table.txt"


def build_year_table():
    with open(DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    with open(MCQ_RESULTS, encoding="utf-8") as f:
        mcq_data = json.load(f)
    with open(SUBJ_RESULTS, encoding="utf-8") as f:
        subj_data = json.load(f)

    subj_by_idx = {e["_index"]: e for e in subj_data}
    mcq_by_idx = {r["_index"]: r for r in mcq_data}

    # Group by year
    years = {}
    for i, q in enumerate(questions):
        m = re.search(r'\[(\d{4})年', q.get("prompt", ""))
        year = m.group(1) if m else "?"
        if year not in years:
            years[year] = {"mcq_total": 0, "mcq_correct": 0,
                           "subj": [], "indices": []}
        qtype = q.get("type", "")
        if qtype == "单选题":
            years[year]["mcq_total"] += 1
            r = mcq_by_idx.get(i)
            if r and r.get("final", {}).get("correct"):
                years[year]["mcq_correct"] += 1
        elif qtype == "主观题":
            se = subj_by_idx.get(i)
            got = se.get("score_got") if se else None
            mx = se.get("score_max") if se else None
            ans_len = se.get("model_answer_len", 0) if se else 0
            years[year]["subj"].append({
                "idx": i, "got": got, "max": mx, "ans_len": ans_len
            })
        years[year]["indices"].append(i)

    # Build table
    lines = []
    lines.append("=" * 90)
    lines.append("年份分数表 — Qwen3.6-27B 408真题推理能力")
    lines.append("=" * 90)
    lines.append("")
    lines.append(f"{'年份':>6} | {'MCQ':>12} | {'MCQ率':>7} | {'主观总分':>10} | {'主观满分':>10} | {'主观率':>7} | {'备注'}")
    lines.append("-" * 90)

    total_mcq_ok = 0
    total_mcq_n = 0
    total_subj_got = 0
    total_subj_max = 0

    for y in sorted(years.keys()):
        d = years[y]
        mcq_n = d["mcq_total"]
        mcq_ok = d["mcq_correct"]
        mcq_pct = f"{100*mcq_ok/mcq_n:.0f}%" if mcq_n else "-"

        subj_got = sum(s["got"] for s in d["subj"] if s["got"] is not None)
        subj_max = sum(s["max"] for s in d["subj"] if s["max"] is not None)
        subj_pct = f"{100*subj_got/subj_max:.0f}%" if subj_max else "-"

        # Find weak areas (wrong MCQs)
        wrong_mcqs = [idx for idx in d["indices"]
                      if idx in mcq_by_idx and mcq_by_idx[idx].get("final", {}).get("correct") == False]
        notes = []
        if wrong_mcqs:
            notes.append(f"错题:{wrong_mcqs}")

        total_mcq_ok += mcq_ok
        total_mcq_n += mcq_n
        total_subj_got += subj_got
        total_subj_max += subj_max

        lines.append(f"{y:>6} | {mcq_ok:>3}/{mcq_n:<3}       | {mcq_pct:>6} | {subj_got:>8.0f} | {subj_max:>8.0f} | {subj_pct:>6} | {'; '.join(notes)}")

    lines.append("-" * 90)
    mcq_total_pct = f"{100*total_mcq_ok/total_mcq_n:.0f}%" if total_mcq_n else "-"
    subj_total_pct = f"{100*total_subj_got/total_subj_max:.0f}%" if total_subj_max else "-"
    lines.append(f"{'合计':>6} | {total_mcq_ok:>3}/{total_mcq_n:<3}       | {mcq_total_pct:>6} | {total_subj_got:>8.0f} | {total_subj_max:>8.0f} | {subj_total_pct:>6} |")
    lines.append("")

    # Per-subject breakdown (wrong MCQ knowledge areas)
    lines.append("=" * 90)
    lines.append("错题知识点分析")
    lines.append("=" * 90)

    extractions = {}
    try:
        with open(EXTRACTIONS, encoding="utf-8") as f:
            ext_list = json.load(f)
            extractions = {e["_index"]: e for e in ext_list}
    except FileNotFoundError:
        pass

    for y in sorted(years.keys()):
        d = years[y]
        wrong = [idx for idx in d["indices"]
                 if idx in mcq_by_idx and mcq_by_idx[idx].get("final", {}).get("correct") == False]
        if not wrong:
            continue
        lines.append(f"\n{y}年错题:")
        for idx in wrong:
            r = mcq_by_idx[idx]
            q = questions[idx]
            gt = r.get("gt_key", "?")
            got = r.get("final", {}).get("answer", "?")
            preview = q.get("prompt", "")[:60]
            ext = extractions.get(idx)
            units = []
            if ext and "knowledge_units" in ext:
                for ku in ext["knowledge_units"].get("knowledge_units", []):
                    units.append(ku.get("name", ""))
            lines.append(f"  [{idx}] gt={gt} got={got} | {preview}...")
            if units:
                lines.append(f"       知识点: {', '.join(units[:4])}")

    table = "\n".join(lines)
    with open(DST_TABLE, "w", encoding="utf-8") as f:
        f.write(table)
    print(table)
    print(f"\nSaved to {DST_TABLE}")

    # Build user profile from performance data
    print("\n" + "=" * 90)
    print("角色画像构造 (基于做题表现)")
    print("=" * 90)

    # Identify weak knowledge areas
    weak_areas = []
    for idx, ext in extractions.items():
        if "knowledge_units" not in ext:
            continue
        for ku in ext["knowledge_units"].get("knowledge_units", []):
            weak_areas.append(ku.get("name", ""))

    strong_areas = []
    # From correct MCQs, find knowledge areas
    correct_mcqs = [r for r in mcq_data if r.get("question_type") == "单选题"
                    and r.get("final", {}).get("correct")]
    # Just sample some concepts
    strong_areas = ["CPU性能计算", "Cache命中率", "基本指令系统"]

    profile = {
        "name": "考研408备考学生",
        "error_history": f"Cache地址映射题连续做错，浮点数IEEE754编码做错，流水线数据冒险识别失败",
        "mastery_info": f"已掌握：{', '.join(strong_areas)}；薄弱：{', '.join(weak_areas[:5])}",
        "training_goal": "针对Cache地址映射和浮点数编码的薄弱知识点，生成中等难度的选择题进行强化训练",
    }
    print(f"\n角色画像:")
    for k, v in profile.items():
        print(f"  {k}: {v}")

    return profile, list(extractions.values())[:3]  # Use first 3 extractions as knowledge base


async def test_generation(profile, knowledge_base):
    """Test end-to-end question generation with GLM 5.1."""
    print("\n" + "=" * 90)
    print("端到端生成测试: GLM 5.1 GenerationPipeline")
    print("=" * 90)

    config = get_provider_config("glm5.1")
    provider = get_llm_provider(config)
    pipeline = GenerationPipeline(provider, max_tokens=4096)

    print(f"\n知识库: {len(knowledge_base)} 条抽取结果")
    print(f"角色: {profile['name']}")
    print()

    t0 = __import__("time").time()
    result = await pipeline.generate(profile, knowledge_base)
    dt = __import__("time").time() - t0

    agg = result.get("aggregation", {})
    status = agg.get("decision", agg.get("status", "unknown"))
    print(f"Status: {status}, Time: {dt:.1f}s")

    q = result.get("question", {})
    if q and q.get("stem"):
        print(f"\n生成的题目:")
        print(f"  题干: {q['stem']}")
        opts = q.get("options", {})
        for opt in ["A", "B", "C", "D"]:
            if opts and opt in opts:
                print(f"  {opt}: {opts[opt]}")
            elif q.get(f"option_{opt}"):
                print(f"  {opt}: {q[f'option_{opt}']}")
        print(f"  答案: {q.get('answer', 'N/A')}")

    solver = result.get("solver_results", [])
    if solver:
        s = solver[0]
        print(f"\n求解器: answer={s.get('derived_answer', s.get('answer', '?'))} "
              f"solvable={s.get('solvable', '?')} unique={s.get('unique_answer', '?')}")

    sim = result.get("simulation_result", {})
    if sim:
        print(f"模拟: chose={sim.get('simulated_answer', '?')} "
              f"matched_failure={sim.get('matched_expected_failure', '?')}")

    if "error" in result:
        print(f"\nERROR: {result['error']}")

    # Save
    with open("docs/generation_e2e_test.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to docs/generation_e2e_test.json")

    return result


async def main():
    profile, kb = build_year_table()
    if kb:
        await test_generation(profile, kb)
    else:
        print("\nNo extractions available for generation test")


if __name__ == "__main__":
    asyncio.run(main())
