"""Generate question for a single profile index (0-5). Usage: python gen_single_profile.py 0"""
import asyncio
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(line_buffering=True)

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from config import get_provider_config
from llm_providers_new import get_llm_provider
from core_new.generation_team import GenerationPipeline

DST_DIR = "docs/profile_questions"

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
            "薄弱：①中断服务程序的精确执行顺序；"
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
            "第1问分析到一半突然中断，所有结论缺失；"
            "第2问(转移范围)和第3问(机器码+执行结果追踪)完全空白。"
            "做[90]主观题时自行假设了4位操作码(实际7位)，导致后续全错。"
        ),
        "mastery_info": (
            "已掌握：指令基本格式（操作码+地址码）；"
            "薄弱：①定长指令字中各字段位数的精确计算；"
            "②在位数确定后，直接寻址和间接寻址范围的计算；"
            "③考试时间管理——前面的题耗时过多导致后面空白"
        ),
        "training_goal": "针对指令字格式中字段位数分配和寻址范围计算，生成一道需要精确计算的选择题",
        "target_knowledge": ["指令格式", "寻址方式", "操作码", "寻址范围"],
    },
    {
        "name": "P6-存储器交叉编址与DRAM型",
        "error_history": (
            "做2017年第13题(低位交叉编址+double型变量读取)时选B而非C，"
            "混淆了交叉编址的体号计算方式——特别是double型(8字节)跨越两个存储体时的读取周期。"
            "做2018年第17题(DRAM芯片r×c阵列)时选B(64×32)而非C(32×64)，"
            "在保证地址引脚最少(r=c)的前提下，需要r≤c以减少刷新开销，误以为64×32刷新开销更小。"
            "做2022年第15题(分页虚拟存储)时选D而非C，页表项的页号和偏移量位数计算错误。"
        ),
        "mastery_info": (
            "已掌握：主存编址基本概念、DRAM刷新原理；"
            "薄弱：①低位交叉编址中多体并行读取的体号计算；"
            "②DRAM阵列r×c的选择——引脚最少要求r≈c，减少刷新要求r≤c；"
            "③虚拟地址中页号位数vs页内偏移位数的精确划分"
        ),
        "training_goal": "针对低位交叉编址的跨体访问判断和DRAM阵列优化选择，生成一道综合选择题",
        "target_knowledge": ["交叉编址", "DRAM", "存储器", "刷新"],
    },
]


async def generate_one(idx: int):
    profile_info = PROFILES[idx]
    name = profile_info["name"]
    print(f"[{name}] Starting...")

    with open("docs/wrong_mcq_extractions.json", encoding="utf-8") as f:
        all_extractions = json.load(f)

    target_kw = profile_info.get("target_knowledge", [])
    relevant = []
    for ext in all_extractions:
        ku_names = [ku.get("name", "").lower() for ku in ext.get("knowledge_units", {}).get("knowledge_units", [])]
        text = " ".join(ku_names) + " " + ext.get("question_id", "").lower()
        if any(kw.lower() in text for kw in target_kw):
            relevant.append(ext)
    kb = relevant[:3] if relevant else all_extractions[:3]

    config = get_provider_config("glm5.1")
    provider = get_llm_provider(config)
    pipeline = GenerationPipeline(provider, max_tokens=4096)

    t0 = time.time()
    try:
        result = await pipeline.generate(profile_info, kb)
        dt = time.time() - t0
        agg = result.get("aggregation", {})
        status = agg.get("status", agg.get("decision", "unknown"))
        print(f"[{name}] Status: {status}, Time: {dt:.1f}s")

        q = result.get("question", {})
        if q and q.get("stem"):
            print(f"[{name}] 题干: {q['stem'][:100]}...")
            opts = q.get("options", {})
            for opt in ["A", "B", "C", "D"]:
                if opts and opt in opts:
                    print(f"  {opt}: {str(opts[opt])[:60]}")
            print(f"  答案: {q.get('answer', 'N/A')}")

            solver = result.get("solver_results", [])
            if solver:
                s = solver[0]
                print(f"  Solver: {s.get('derived_answer', '?')} solvable={s.get('solvable', '?')}")
            sim = result.get("simulation_result", {})
            if sim:
                print(f"  Sim: chose={sim.get('simulated_answer', '?')} matched={sim.get('matched_expected_failure', '?')}")

        result["_profile_index"] = idx
        result["_profile_name"] = name
        result["_time"] = dt

        os.makedirs(DST_DIR, exist_ok=True)
        with open(f"{DST_DIR}/p{idx}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[{name}] Saved to {DST_DIR}/p{idx}.json")
        return result

    except Exception as e:
        dt = time.time() - t0
        print(f"[{name}] FAILED: {e}")
        return {"error": str(e), "_profile_index": idx, "_profile_name": name, "_time": dt}


if __name__ == "__main__":
    idx = int(sys.argv[1])
    asyncio.run(generate_one(idx))
