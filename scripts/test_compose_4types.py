#!/usr/bin/env python3
"""组卷测试：读 paper_request.yaml，按题型分发到新架构，验证四种类型。

四类型分发：
  概念题(complexity=conceptual) → concept_creator 批量（收集所有concept slot一次出）
  选择题(single_choice)         → design_direct → write_gen(关思考) → 派生干扰项 → dual_review
  综合题(comprehensive K3)      → design_direct → write_gen(关思考) → write_solution → dual_review
  融合题(comprehensive K4)      → 同综合题，但 design_direct 触发考点融合

意图注入：每个 agent 的 task 带 slot 的 examination_mode/teacher_annotation/k_dominant 等。
"""
import asyncio
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("GLM_MODEL", "glm-5.2")
os.environ.setdefault("GLM_API_BASE", "https://open.bigmodel.cn/api/coding/paas/v4/")
os.environ.setdefault("GLM_API_KEY", "d6f4904cd7d7462c8e82c5c4e097bebe.hQln0yGBA2muYhJU")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml
from core_new.llm_gateway import get_gateway
from core_new.doc_pipeline.scheduler import DocScheduler
from core_new.doc_pipeline.config import ROLE_PARAMS

# 各 agent 策略（今天验证过的）
ROLE_PARAMS["design_direct"] = {"max_tokens": 16000, "max_attempts": 4, "multi_turn": True, "enable_thinking": True}
ROLE_PARAMS["write_gen"] = {"max_tokens": 12000, "max_attempts": 8, "multi_turn": True, "enable_thinking": True}
ROLE_PARAMS["write_solution"] = {"max_tokens": 8000, "max_attempts": 4, "multi_turn": True, "enable_thinking": True}
ROLE_PARAMS["dual_review"] = {"max_tokens": 16000, "max_attempts": 3, "multi_turn": True, "enable_thinking": True}
ROLE_PARAMS["concept_creator"] = {"max_tokens": 8000, "max_attempts": 3, "multi_turn": True, "enable_thinking": True}
ROLE_PARAMS["review"] = {"max_tokens": 6000, "max_attempts": 3, "multi_turn": True, "enable_thinking": True}

WS = Path("/tmp/compose_test4")
PAPER_REQUEST = ROOT / "docs/compose/paper_request_test4.yaml"


def _load_slots():
    pr = yaml.safe_load(PAPER_REQUEST.read_text(encoding="utf-8"))
    return pr.get("slots", []), pr.get("teacher_preferences", {})


def _status_of(text):
    m = re.search(r"##\s*status\s*\n\s*(\w+)", text or "")
    return m.group(1).strip().lower() if m else "unknown"


def _intent_block(slot):
    """把 slot 的设计意图字段拼成文本块，注入 agent task。"""
    parts = [f"- slot_id: {slot.get('slot_id','')}",
             f"- 知识点: {slot.get('primary_target_name','')}",
             f"- 科目: {slot.get('target_subject','')}"]
    if slot.get("examination_mode"):
        parts.append(f"- 考察模式(设计意图): {slot['examination_mode']}")
    if slot.get("teacher_annotation"):
        parts.append(f"- 教师批注(设计意图): {slot['teacher_annotation']}")
    if slot.get("k_dominant"):
        parts.append(f"- K主维度: {slot['k_dominant']} (难度{slot.get('target_difficulty','?')})")
    if slot.get("difficulty_rationale"):
        parts.append(f"- 难度理由: {slot['difficulty_rationale']}")
    hc = slot.get("hard_constraints") or []
    if hc:
        parts.append("- 硬约束: " + "; ".join(hc))
    ct = slot.get("concept_topics") or []
    if ct:
        parts.append("- 概念考点列表: " + " | ".join(ct))
    return "\n".join(parts)


async def _run_concept_batch(sched, concept_slots, total_start, timings):
    """概念题批量：收集所有 concept slot 的考点，一次调用 concept_creator。"""
    print("\n" + "=" * 60, flush=True)
    print(f"概念题批量（{len(concept_slots)} 个 slot 合并一次出）", flush=True)
    print("=" * 60, flush=True)
    all_topics = []
    intent_parts = []
    for s in concept_slots:
        all_topics.extend(s.get("concept_topics") or [s.get("primary_target_name", "")])
        intent_parts.append(_intent_block(s))
    slot_id = concept_slots[0]["slot_id"] if concept_slots else "Q_CONCEPT"
    slot_ws = WS / slot_id
    slot_ws.mkdir(parents=True, exist_ok=True)
    (slot_ws / "blueprint.md").write_text(
        "# 蓝图\n## 考点列表\n" + "\n".join(f"- {t}" for t in all_topics) +
        "\n\n## 设计意图\n" + "\n\n".join(intent_parts), encoding="utf-8")

    t0 = time.monotonic()
    q = await sched.run_agent(
        "concept_creator",
        task=f"读 blueprint 考点列表，对每个考点出1道概念题（共{len(all_topics)}道），write question.md + solution.md。",
        slot_id=slot_id, inject_files={"蓝图": slot_ws / "blueprint.md"}, target_file="question.md")
    timings["概念题批量"] = time.monotonic() - t0
    qok = (slot_ws / "question.md").exists()
    n = open(slot_ws / "question.md").read().count("## 第") if qok else 0
    print(f"  [concept_creator] {timings['概念题批量']:.0f}s | question.md={'✓' if qok else '✗'} | 产出{n}道", flush=True)
    # review
    if qok:
        t0 = time.monotonic()
        r = await sched.run_agent(
            "review",
            task="§21 概念题审核：事实性检查+设计缺陷。逐题布尔判断（答案对不对/干扰项是否真实认知错误/有无设计缺陷），不展开推演。用 write_file 写 review.md（## status + 逐题理由）。",
            slot_id=slot_id, inject_files={"题目": slot_ws / "question.md", "解析": slot_ws / "solution.md"}, target_file="review.md")
        timings["概念题审核"] = time.monotonic() - t0
        print(f"  [review] {timings['概念题审核']:.0f}s | status={_status_of(r)}", flush=True)


async def _run_calc_question(sched, slot, label, timings):
    """计算题（选择/综合/融合）：design_direct → write_gen → write_solution → dual_review(A代码/B文档)。
    选择题额外：write_gen 后派生干扰项。"""
    slot_id = slot["slot_id"]
    is_choice = slot.get("question_type") == "single_choice"
    print("\n" + "=" * 60, flush=True)
    print(f"{label}（{slot_id}，{'选择题+干扰项' if is_choice else '综合题'}）", flush=True)
    print("=" * 60, flush=True)
    slot_ws = WS / slot_id
    slot_ws.mkdir(parents=True, exist_ok=True)
    dc = f"# design_card\n## blueprint_contract\n```yaml\nslot_id: {slot_id}\nquestion_type: {slot.get('question_type','')}\nscore: {slot.get('score','')}\nexamination_mode: {slot.get('examination_mode','')}\nprimary_target_name: {slot.get('primary_target_name','')}\ntarget_difficulty: {slot.get('target_difficulty','')}\nk_dominant: {slot.get('k_dominant','')}\nhard_constraints: {slot.get('hard_constraints','')}\n```\n## core_knowledge_intent\n{_intent_block(slot)}\n## reference_questions\n（无）\n"
    (slot_ws / "design_card.md").write_text(dc, encoding="utf-8")

    # ① design_direct
    t0 = time.monotonic()
    q = await sched.run_agent(
        "design_direct", task=f"根据 design_card 设计题干（含设计意图），写出 question.md。",
        slot_id=slot_id, inject_files={"design_card": slot_ws / "design_card.md"}, target_file="question.md")
    timings[f"{label}·design"] = time.monotonic() - t0
    print(f"  [design_direct] {timings[f'{label}·design']:.0f}s | question.md={'✓' if (slot_ws/'question.md').exists() else '✗'}", flush=True)

    # ② write_gen（关思考）
    t0 = time.monotonic()
    gen_task_extra = " 写完 gen.py 后，若为选择题，用 exec 输出的正确值派生3个干扰项（真实计算错误：常见错误步骤的产物），填入 question.md 的 A/B/C/D（A=正确）。" if is_choice else ""
    g = await sched.run_agent(
        "write_gen", task=f"读 question.md 写 gen.py 并 exec 验证（关思考，按工作规范分步）。{gen_task_extra}",
        slot_id=slot_id, inject_files={"question.md": slot_ws / "question.md", "design_card": slot_ws / "design_card.md"},
        target_file="gen.py", enable_thinking=True)
    timings[f"{label}·gen"] = time.monotonic() - t0
    genok = (slot_ws / "gen.py").exists()
    print(f"  [write_gen] {timings[f'{label}·gen']:.0f}s | gen.py={'✓' if genok else '✗'}", flush=True)

    # ③ write_solution（关思考）
    if genok:
        t0 = time.monotonic()
        s = await sched.run_agent(
            "write_solution", task="读 gen.py + exec 输出，整理成 solution.md（不重算，忠实整理）。",
            slot_id=slot_id, inject_files={"gen.py": slot_ws / "gen.py", "question.md": slot_ws / "question.md"}, target_file="solution.md")
        timings[f"{label}·solution"] = time.monotonic() - t0
        print(f"  [write_solution] {timings[f'{label}·solution']:.0f}s | solution.md={'✓' if (slot_ws/'solution.md').exists() else '✗'}", flush=True)

    # ④ dual_review A（审代码）+ B（审文档）
    if genok and (slot_ws / "solution.md").exists():
        t0 = time.monotonic()
        ra = await sched.run_agent(
            "dual_review", task="## 本轮阶段\n本轮审求解-代码（阶段2·A）。审 gen.py 建模思路对不对（看代码结构，不代入参数）。",
            slot_id=slot_id, inject_files={"question.md": slot_ws / "question.md", "gen.py": slot_ws / "gen.py"}, target_file="review.md", enable_thinking=True)
        sa = _status_of(ra)
        timings[f"{label}·review_code"] = time.monotonic() - t0
        print(f"  [review_code] {timings[f'{label}·review_code']:.0f}s | status={sa}", flush=True)
        if sa == "pass":
            t0 = time.monotonic()
            rb = await sched.run_agent(
                "dual_review", task="## 本轮阶段\n本轮审求解-文档（阶段2·B）。审 solution.md 是否忠实转写 gen.py（形式一致/抄写无误/无幻觉）。",
                slot_id=slot_id, inject_files={"gen.py": slot_ws / "gen.py", "solution.md": slot_ws / "solution.md"}, target_file="review.md")
            timings[f"{label}·review_doc"] = time.monotonic() - t0
            print(f"  [review_doc] {timings[f'{label}·review_doc']:.0f}s | status={_status_of(rb)}", flush=True)


async def main():
    slots, prefs = _load_slots()
    WS.mkdir(parents=True, exist_ok=True)
    for f in WS.glob("*"):
        if f.is_dir():
            for sf in f.glob("*"):
                sf.unlink()
    gw = get_gateway("glm5.2_anthropic")
    sched = DocScheduler(gateway=gw, workspace=str(WS), enable_thinking=True)
    print(f"模型: glm-5.2 | 共 {len(slots)} 个 slot | workspace: {WS}\n", flush=True)

    # 分发
    concept_slots = [s for s in slots if s.get("complexity") == "conceptual"]
    calc_slots = [s for s in slots if s.get("complexity") != "conceptual"]

    timings = {}
    total_start = time.monotonic()

    # 概念题批量（先做，合并所有 concept slot）
    if concept_slots:
        await _run_concept_batch(sched, concept_slots, total_start, timings)

    # 计算题（选择/综合/融合）逐个做
    for s in calc_slots:
        kd = s.get("k_dominant", "")
        qtype = s.get("question_type", "")
        if qtype == "single_choice":
            label = f"选择题({s['slot_id']})"
        elif kd in ("K4", "K5") or s.get("target_difficulty", 0) >= 4:
            label = f"融合题({s['slot_id']},K4)"
        else:
            label = f"综合题({s['slot_id']},K3)"
        await _run_calc_question(sched, s, label, timings)

    # 汇总
    total = time.monotonic() - total_start
    print("\n" + "=" * 60, flush=True)
    print("组卷测试汇总", flush=True)
    print("=" * 60, flush=True)
    for name, dt in timings.items():
        print(f"  {name:28s} {dt:6.0f}s", flush=True)
    print(f"  {'总耗时':28s} {total:6.0f}s ({total/60:.1f}min)", flush=True)

    # 产出齐全度
    print("\n各 slot 产出:", flush=True)
    for s in slots:
        sid = s["slot_id"]
        sw = WS / sid
        if s.get("complexity") == "conceptual":
            print(f"  {sid}: question.md={'✓' if (sw/'question.md').exists() else '✗'} solution.md={'✓' if (sw/'solution.md').exists() else '✗'} review.md={'✓' if (sw/'review.md').exists() else '✗'}", flush=True)
        else:
            print(f"  {sid}: question.md={'✓' if (sw/'question.md').exists() else '✗'} gen.py={'✓' if (sw/'gen.py').exists() else '✗'} solution.md={'✓' if (sw/'solution.md').exists() else '✗'} review.md={'✓' if (sw/'review.md').exists() else '✗'}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
