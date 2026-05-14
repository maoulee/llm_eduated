"""Build 6 nuanced user profiles from actual error patterns, generate targeted questions,
and test them with local vLLM.

Profiles are based on:
  - 14 wrong MCQs with extraction data (knowledge units, trigger rules, reasoning patterns)
  - 31 subjective question scores with specific error annotations
  - Year-by-year performance breakdown
"""
import asyncio
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(line_buffering=True)

from dotenv import load_dotenv
load_dotenv()
from config import get_provider_config
from llm_providers_new import get_llm_provider
from core_new.generation_team import GenerationPipeline
from openai import AsyncOpenAI

LOCAL_URL = "http://localhost:8000/v1"
LOCAL_MODEL = "qwen3.6"
DST = "docs/profile_generation_results.json"

# ── 6 User Profiles based on actual error patterns ──

PROFILES = [
    {
        "name": "P1-浮点数运算混淆型",
        "error_history": (
            "做2009年第13题(浮点数加减法)时选了错误答案，混淆了规格化后的溢出判定。"
            "做2011年第13题(IEEE754编码)时无法正确将-8.25转换为机器码。"
            "做主观题[51]时，正确求出了-513的补码FDFFH，但执行右移时用了逻辑右移(高位补0)得到7EFFH，"
            "应该用算术右移(高位补符号位)。"
            "做[116]主观题时，能推导出浮点数的阶码和尾数，但最后结果截断未完成。"
        ),
        "mastery_info": (
            "已掌握：补码表示、浮点数基本格式（阶码+尾数）；"
            "薄弱：①双符号位溢出判定（01=正溢出，10=负溢出容易混淆）；"
            "②算术右移vs逻辑右移的区别（算术右移保持符号位，逻辑右移高位补0）；"
            "③IEEE754偏置值计算（127而非128）；"
            "④规格化过程中阶码溢出的判断时机"
        ),
        "training_goal": "针对浮点数运算中的算术/逻辑右移混淆和双符号位溢出判定，生成一道选择题和一道主观题",
        "target_knowledge": ["浮点数", "右移", "溢出", "IEEE754"],
    },
    {
        "name": "P2-Cache映射混淆型",
        "error_history": (
            "做2012年第17题(2路组相联+LRU)时选错，混淆了组相联映射的地址划分方式。"
            "做主观题[25](2010年第44题Cache容量+命中率)时："
            "①只算了数据区容量512B，漏算了Tag+有效位（正确532B）；"
            "②计算a[1][1]的Cache行号时错误假设数组为32×32（实际256×256），得到行号7而非正确答案5。"
            "做主观题[130](2018年第44题虚拟存储+TLB+Cache)时，完全用了不同年份的参数来答题，"
            "张冠李戴式错误——用了36位地址而非原题的地址位数。"
        ),
        "mastery_info": (
            "已掌握：Cache基本原理、命中率的计算思路、直接映射；"
            "薄弱：①组相联映射中组号计算（block_number mod 组数）容易算错；"
            "②Cache行总容量必须包含Tag位+有效位+脏位等额外开销；"
            "③审题不仔细——容易用记忆中的旧题参数代替当前题目参数"
        ),
        "training_goal": "针对Cache组相联映射的行号计算和容量计算（含Tag开销），生成一道易混淆参数的选择题",
        "target_knowledge": ["Cache", "组相联", "容量", "Tag"],
    },
    {
        "name": "P3-流水线冒险识别失败型",
        "error_history": (
            "做2023年第19题(5段流水线数据冒险)时选错答案。"
            "做主观题[51]第2问(流水线时空图)时完全未作答，无法画出正确的指令调度时空图。"
            "做[12]主观题(数据通路微操作)时，在单总线结构中将R0和MDR同时输出到总线，"
            "违反了单总线同一时刻只能有一个组件输出的约束，导致后续微操作全部错误。"
        ),
        "mastery_info": (
            "已掌握：流水线5段基本概念（取指、译码、执行、访存、写回）；"
            "薄弱：①RAW数据冒险的具体阻塞周期计算——特别是需要几个气泡；"
            "②单总线结构的硬件约束（同一节拍不能有两个组件同时输出到总线）；"
            "③指令调度和时空图绘制能力"
        ),
        "training_goal": "针对流水线数据冒险阻塞周期计算，生成一道需要逐步分析的选择题",
        "target_knowledge": ["流水线", "数据冒险", "RAW", "阻塞"],
    },
    {
        "name": "P4-中断总线概念模糊型",
        "error_history": (
            "做2010年第21题(单级中断服务程序执行顺序)时选错，混淆了保护现场和开中断的顺序。"
            "做2012年第21题(I/O总线数据线传输内容)时选A(仅命令字+状态字)，"
            "漏了中断类型号也通过数据线传输这一事实，正确答案D(三个都在数据线上)。"
            "做2023年第21题(异常/中断)时选C，以为开中断就能立即响应，"
            "忽略了中断响应需要满足条件（当前指令执行完毕+开中断状态+有中断请求）。"
        ),
        "mastery_info": (
            "已掌握：中断的基本概念（保护现场、恢复现场、中断返回）；"
            "薄弱：①中断服务程序的精确执行顺序（关中断→保存断点→取中断向量→保护现场→开中断→处理→关中断→恢复现场→开中断→返回）；"
            "②I/O总线数据线vs控制线的传输内容区分；"
            "③中断响应的三个条件（指令结束、开中断、有请求）"
        ),
        "training_goal": "针对中断响应条件和I/O总线数据线传输内容，生成一道综合辨析题",
        "target_knowledge": ["中断", "总线", "数据线", "中断响应"],
    },
    {
        "name": "P5-指令系统与寻址计算型",
        "error_history": (
            "做2020年第16题(定长指令字+寻址范围)时选C而非A，"
            "在计算操作码和寻址特征位后的剩余位数时出错，导致直接寻址范围计算错误。"
            "做主观题[24](2010年第43题指令格式+汇编执行)时："
            "第1问分析到一半突然中断，所有结论（指令数16、寄存器数8、MAR/MDR位数）缺失；"
            "第2问(转移范围)和第3问(机器码+执行结果追踪)完全空白。"
            "做[90]主观题时自行假设了4位操作码(实际7位)，导致后续全错。"
        ),
        "mastery_info": (
            "已掌握：指令基本格式（操作码+地址码）；"
            "薄弱：①定长指令字中各字段位数的精确计算（48条指令需6位OP，4种寻址需2位特征位）；"
            "②在位数确定后，直接寻址和间接寻址范围的计算；"
            "③考试时间管理——前面的题耗时过多导致后面空白"
        ),
        "training_goal": "针对指令字格式中字段位数分配和寻址范围计算，生成一道需要精确计算的主观题",
        "target_knowledge": ["指令格式", "寻址方式", "操作码", "寻址范围"],
    },
    {
        "name": "P6-存储器交叉编址与DRAM型",
        "error_history": (
            "做2017年第13题(低位交叉编址+double型变量读取)时选B而非C，"
            "混淆了交叉编址的体号计算方式——特别是double型(8字节)跨越两个存储体时的读取周期。"
            "做2018年第17题(DRAM芯片r×c阵列)时选B(64×32)而非C(32×64)，"
            "在保证地址引脚最少(r=c)的前提下，需要r≤c以减少刷新开销（刷新按行进行），"
            "误以为64×32刷新开销更小。"
            "做2022年第15题(分页虚拟存储)时选D而非C，页表项的页号和偏移量位数计算错误。"
        ),
        "mastery_info": (
            "已掌握：主存编址基本概念、DRAM刷新原理；"
            "薄弱：①低位交叉编址中多体并行读取的体号计算——特别是跨体访问的判断；"
            "②DRAM阵列r×c的选择——引脚最少要求r≈c，减少刷新要求r≤c；"
            "③虚拟地址中页号位数vs页内偏移位数的精确划分"
        ),
        "training_goal": "针对低位交叉编址的跨体访问判断和DRAM阵列优化选择，生成一道综合选择题",
        "target_knowledge": ["交叉编址", "DRAM", "存储器", "刷新"],
    },
]


async def generate_questions_for_profiles():
    """Generate questions for all 6 profiles via GLM 5.1 pipeline."""
    # Load extraction data as knowledge base
    with open("docs/wrong_mcq_extractions.json", encoding="utf-8") as f:
        all_extractions = json.load(f)

    config = get_provider_config("glm5.1")
    provider = get_llm_provider(config)
    pipeline = GenerationPipeline(provider, max_tokens=4096)

    results = []
    for i, profile_info in enumerate(PROFILES):
        print(f"\n{'='*70}")
        print(f"Profile {i+1}/6: {profile_info['name']}")
        print(f"{'='*70}")

        # Filter knowledge base by target keywords
        target_kw = profile_info.get("target_knowledge", [])
        relevant = []
        for ext in all_extractions:
            ku_names = [ku.get("name", "").lower() for ku in ext.get("knowledge_units", {}).get("knowledge_units", [])]
            text = " ".join(ku_names) + " " + ext.get("question_id", "").lower()
            if any(kw.lower() in text for kw in target_kw):
                relevant.append(ext)
        # If no exact match, use all extractions (limited to 3)
        kb = relevant[:3] if relevant else all_extractions[:3]
        print(f"  Knowledge base: {len(kb)} extractions matched")

        t0 = time.time()
        try:
            result = await pipeline.generate(profile_info, kb)
            dt = time.time() - t0
            agg = result.get("aggregation", {})
            status = agg.get("status", agg.get("decision", "unknown"))
            print(f"  Status: {status}, Time: {dt:.1f}s")

            q = result.get("question", {})
            if q and q.get("stem"):
                print(f"  题干: {q['stem'][:120]}...")
                opts = q.get("options", {})
                for opt in ["A", "B", "C", "D"]:
                    if opts and opt in opts:
                        print(f"  {opt}: {str(opts[opt])[:80]}")
                print(f"  答案: {q.get('answer', 'N/A')}")

            solver = result.get("solver_results", [])
            if solver:
                s = solver[0]
                print(f"  Solver: answer={s.get('derived_answer', s.get('answer', '?'))} "
                      f"solvable={s.get('solvable', '?')} unique={s.get('unique_answer', '?')}")

            sim = result.get("simulation_result", {})
            if sim:
                print(f"  Sim: chose={sim.get('simulated_answer', '?')} "
                      f"matched={sim.get('matched_expected_failure', '?')}")

            result["_profile_index"] = i
            result["_profile_name"] = profile_info["name"]
            result["_time"] = dt
            results.append(result)

        except Exception as e:
            dt = time.time() - t0
            print(f"  FAILED: {e}")
            results.append({"error": str(e), "_profile_index": i, "_profile_name": profile_info["name"], "_time": dt})

    return results


async def test_with_local_model(results):
    """Test generated questions with local vLLM model."""
    client = AsyncOpenAI(base_url=LOCAL_URL, api_key="EMPTY")
    questions_to_test = []

    for r in results:
        q = r.get("question", {})
        if not q or not q.get("stem"):
            continue
        questions_to_test.append({
            "profile": r.get("_profile_name", "?"),
            "question": q,
        })

    if not questions_to_test:
        print("\nNo valid questions to test with local model")
        return

    print(f"\n{'='*70}")
    print(f"Testing {len(questions_to_test)} questions with local vLLM (Qwen3.6-27B)")
    print(f"{'='*70}")

    TEST_PROMPT = """请解答以下考研408真题，给出你的答案和简要分析。

{question}

请先分析题目，然后给出最终答案。如果是选择题，格式：\\boxed{{答案字母}}；如果是主观题，给出完整解答过程。"""

    test_results = []
    for item in questions_to_test:
        profile = item["profile"]
        q = item["question"]
        stem = q.get("stem", "")
        opts = q.get("options", {})
        answer = q.get("answer", "")

        opt_text = ""
        if opts:
            for k in ["A", "B", "C", "D"]:
                if k in opts:
                    opt_text += f"\n{k}: {opts[k]}"

        full_q = stem + opt_text
        prompt = TEST_PROMPT.format(question=full_q)

        print(f"\n  [{profile}] Solving...", end="", flush=True)
        t0 = time.time()
        try:
            resp = await client.chat.completions.create(
                model=LOCAL_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=1.0, top_p=0.95, max_tokens=4096,
                extra_body={"chat_template_kwargs": {"enable_thinking": True}},
            )
            dt = time.time() - t0
            content = resp.choices[0].message.content or ""
            m = re.match(r'<think[^>]*>(.*?)</think[^>]*>(.*)', content, re.DOTALL)
            model_answer = m.group(2).strip() if m else content

            # Extract boxed answer
            boxed = re.search(r'\\boxed\{([^}]+)\}', model_answer)
            model_choice = boxed.group(1).strip() if boxed else "?"

            correct = model_choice.upper() == str(answer).upper() if answer else None
            tag = "OK" if correct else ("WRONG" if correct is False else "?")
            print(f" {tag} ({dt:.0f}s) model={model_choice} gt={answer}")

            test_results.append({
                "profile": profile,
                "model_answer": model_choice,
                "model_full": model_answer[:500],
                "correct_answer": answer,
                "match": correct,
                "time": dt,
            })
        except Exception as e:
            dt = time.time() - t0
            print(f" FAILED ({dt:.0f}s): {e}")
            test_results.append({"profile": profile, "error": str(e), "time": dt})

    return test_results


async def main():
    print(f"{'='*70}")
    print("6 Profile-Based Question Generation + Local Model Test")
    print(f"{'='*70}")

    # Phase 1: Generate questions
    results = await generate_questions_for_profiles()

    # Save generation results
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved generation results to {DST}")

    # Phase 2: Test with local model
    test_results = await test_with_local_model(results)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    # Generation summary
    gen_ok = sum(1 for r in results if r.get("question", {}).get("stem"))
    gen_status = {}
    for r in results:
        agg = r.get("aggregation", {})
        st = agg.get("status", agg.get("decision", "error"))
        gen_status[st] = gen_status.get(st, 0) + 1

    print(f"\nGeneration: {gen_ok}/{len(results)} produced valid questions")
    for st, cnt in sorted(gen_status.items()):
        print(f"  {st}: {cnt}")

    if test_results:
        tested = [t for t in test_results if "error" not in t]
        matched = sum(1 for t in tested if t.get("match"))
        print(f"\nLocal test: {matched}/{len(tested)} answered correctly")
        for t in test_results:
            profile = t["profile"]
            if "error" in t:
                print(f"  [{profile}] ERROR: {t['error']}")
            else:
                tag = "MATCH" if t["match"] else "DIFF"
                print(f"  [{profile}] {tag}: model={t['model_answer']} gt={t['correct_answer']}")

    # Save full results
    full_dst = "docs/profile_generation_with_test.json"
    with open(full_dst, "w", encoding="utf-8") as f:
        json.dump({"generation": results, "test": test_results}, f, ensure_ascii=False, indent=2)
    print(f"\nSaved full results to {full_dst}")


if __name__ == "__main__":
    asyncio.run(main())
