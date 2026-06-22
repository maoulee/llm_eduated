"""Intake layer end-to-end artifact capture test.

Traces the FULL document chain:
  teacher input → LLM intake → intake_result.yaml
                  → paper_request.yaml (if gate passed)
                  → map_paper_request_to_params()
                  → compose_runner input verification

Uses tricky/edge-case teacher inputs. Captures every artifact for inspection.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core_new.llm_gateway import get_gateway
from compose.compose_runner import load_paper_request, map_paper_request_to_params

# ── Output directory for captured artifacts ────────────────────────

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "output_intake_e2e"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Agent prompt ───────────────────────────────────────────────────

AGENT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "core_new" / "doc_pipeline" / "agents" / "human_intake.md"
SKILL_PROMPT_PATH = Path(__file__).resolve().parent.parent / "core_new" / "doc_pipeline" / "skills" / "intake_core" / "SKILL.md"


def load_system_prompt() -> str:
    agent = AGENT_PROMPT_PATH.read_text(encoding="utf-8")
    if agent.startswith("---"):
        parts = agent.split("---", 2)
        if len(parts) >= 3:
            agent = parts[2].strip()
    skill = SKILL_PROMPT_PATH.read_text(encoding="utf-8")
    return f"""# 你是出题系统的 intake 智能体

## Agent 定义

{agent}

## Skill 规范

{skill}

## 输出要求

每次回复必须包含以下两部分：

### 1. 给教师的回复（自然语言）
解释你做了什么、需要什么、或者为什么拒绝。

### 2. 结构化输出（YAML 代码块）

用 ```yaml ... ``` 包裹。输出 intake_result，字段包括：
- task_type, intake_status, confidence (含 level/missing_fields/contradictions), routing (含 can_route/next_action/next_input/reason)

如果 route_gate 通过 (routing.can_route=true 且 confidence.level 为 high 或 medium)，
**必须额外输出一个 YAML 代码块**，包含完整的下游文件内容：
- paper 路径 → paper_request.yaml 完整字段
- single_question 路径 → slot_blueprint.yaml 完整字段
- retrieval 路径 → retrieval_query.yaml 完整字段

下游文件必须包含所有 schema 要求的字段，不能省略。
"""


# ── YAML extraction ────────────────────────────────────────────────

def extract_yaml_blocks(text: str) -> list[dict]:
    blocks = []
    in_block = False
    lines = []
    fence_count = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            fence_count += 1
            if not in_block and "yaml" in stripped.lower():
                in_block = True
                lines = []
            elif in_block:
                try:
                    data = yaml.safe_load("\n".join(lines))
                    if isinstance(data, dict):
                        blocks.append(data)
                except yaml.YAMLError:
                    pass
                lines = []
                in_block = False
        elif in_block:
            lines.append(line)
    return blocks


# ── Artifact inspector ─────────────────────────────────────────────

def inspect_intake_result(data: dict, label: str) -> dict:
    """Deep-inspect intake_result.yaml — report every field."""
    report = {
        "label": label,
        "task_type": data.get("task_type"),
        "intake_status": data.get("intake_status"),
        "confidence_level": data.get("confidence", {}).get("level") if isinstance(data.get("confidence"), dict) else None,
        "confidence_missing": data.get("confidence", {}).get("missing_fields") if isinstance(data.get("confidence"), dict) else None,
        "confidence_contradictions": data.get("confidence", {}).get("contradictions") if isinstance(data.get("confidence"), dict) else None,
        "can_route": data.get("routing", {}).get("can_route") if isinstance(data.get("routing"), dict) else None,
        "next_action": data.get("routing", {}).get("next_action") if isinstance(data.get("routing"), dict) else None,
        "next_input": data.get("routing", {}).get("next_input") if isinstance(data.get("routing"), dict) else None,
        "routing_reason": data.get("routing", {}).get("reason") if isinstance(data.get("routing"), dict) else None,
    }
    return report


def inspect_paper_request(data: dict, label: str) -> dict:
    """Deep-inspect paper_request.yaml — report all fields for compose_runner consumption."""
    assessment = data.get("assessment", {})
    ks = data.get("knowledge_scope", {})
    qc = data.get("question_config", {})
    diff = data.get("difficulty", {})
    pref = data.get("teacher_preferences", {})
    constraints = data.get("constraints", {})

    report = {
        "label": label,
        "schema_version": data.get("schema_version"),
        # Assessment
        "assessment_type": assessment.get("type"),
        "subjects": assessment.get("subjects"),
        "total_score": assessment.get("total_score"),
        "duration_minutes": assessment.get("duration_minutes"),
        # Knowledge scope
        "primary_chapters": ks.get("primary_chapters"),
        "focus_points": ks.get("focus_points"),
        "excluded_points": ks.get("excluded_points"),
        "coverage_strategy": ks.get("coverage_strategy"),
        # Question config
        "question_types": [
            {"type": t.get("type"), "count_range": t.get("count_range"), "score_per": t.get("score_per"), "score_range": t.get("score_range")}
            for t in qc.get("types", [])
        ],
        # Difficulty
        "difficulty_target": diff.get("target"),
        "difficulty_distribution": diff.get("distribution"),
        # Teacher preferences
        "require": pref.get("require"),
        "avoid": pref.get("avoid"),
        "style_notes": pref.get("style_notes"),
        # Constraints
        "allow_similar_to_past": constraints.get("allow_similar_to_past"),
        "min_knowledge_diversity": constraints.get("min_knowledge_diversity"),
    }
    return report


def trace_compose_mapping(pr_data: dict, label: str) -> dict:
    """Trace what compose_runner would receive from this paper_request."""
    try:
        mapped = map_paper_request_to_params(pr_data)
        return {
            "label": label,
            "mapping_ok": True,
            "user_requirements": mapped.get("user_requirements", ""),
            "subject_files": mapped.get("subject_files", []),
            "slot_templates_hints": mapped.get("slot_templates_hints", []),
            "model_routing": mapped.get("model_routing", {}),
        }
    except Exception as e:
        return {"label": label, "mapping_ok": False, "error": str(e)}


# ── Challenging scenarios ──────────────────────────────────────────

TRICKY_SCENARIOS = [
    {
        "id": "T1",
        "name": "408全科卷 — 多科混合 + 矛盾难度",
        "teacher_input": "我要一套完整的408考研模拟卷，难度整体偏难，但是数据结构部分简单点，操作系统部分要出些冷门考点，不要出Cache和虚拟内存的题，总分150分，180分钟",
        "expect": "多科subjects数组、难度分化处理、excluded_points处理、冷门考点要求",
    },
    {
        "id": "T2",
        "name": "口语化模糊需求 — 多轮才能确认",
        "teacher_input": "搞几张卷子，学生基础不太好，考及格就行，别太难，计算机网络和那个什么组成原理都要有",
        "expect": "意图模糊('几张'→practice_set还是paper)、科目口语化识别、难度推断、需要追问",
    },
    {
        "id": "T3",
        "name": "极限约束 — 指定知识点+排除+分数精确控制",
        "teacher_input": "组一套操作系统期末卷，只考进程管理和内存管理这两章，必须包含银行家算法和页面置换算法，不能出现PV操作相关题目，总分50分，5道选择题每题2分，2道综合题分别10分20分",
        "expect": "精确题型配置、require/avoid、score_range、单科、excluded_points",
    },
    {
        "id": "T4",
        "name": "完全矛盾输入",
        "teacher_input": "出一道数据结构的Cache地址映射题，要综合题但只要2分，难度5星但必须简单",
        "expect": "KMP属于数据结构但Cache属于组成原理(科目矛盾)、综合题2分不合理、难度矛盾→blocked",
    },
    {
        "id": "T5",
        "name": "单题生成 — 测试slot_blueprint路径",
        "teacher_input": "出一道关于AVL树旋转的综合题，要包含LR型和RL型的判断，难度中等偏上，10分",
        "expect": "task_type=single_question, slot_blueprint输出, target_family/primary_target_name正确",
    },
]


# ── Run one scenario ───────────────────────────────────────────────

async def run_scenario(gateway, system_prompt: str, scenario: dict) -> dict:
    """Run scenario, capture ALL artifacts, trace into compose_runner."""
    sid = scenario["id"]
    scenario_dir = OUTPUT_DIR / f"scenario_{sid}"
    scenario_dir.mkdir(parents=True, exist_ok=True)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"教师：{scenario['teacher_input']}"},
    ]

    print(f"\n{'='*70}")
    print(f"Scenario {sid}: {scenario['name']}")
    print(f"{'='*70}")
    print(f"教师输入: {scenario['teacher_input']}")
    print(f"期望验证: {scenario['expect']}")
    print()

    # ── Call LLM ──
    t0 = time.time()
    result = await gateway.generate_text(messages, max_tokens=3000)
    elapsed = time.time() - t0

    if not result.ok:
        print(f"  LLM ERROR: {result.error_message}")
        return {"scenario": sid, "error": result.error_message, "elapsed": elapsed}

    response = result.content or ""

    # Save raw response
    (scenario_dir / "raw_response.md").write_text(response, encoding="utf-8")
    print(f"  LLM 响应已保存 ({elapsed:.1f}s, {len(response)} chars)")

    # ── Extract YAML blocks ──
    yaml_blocks = extract_yaml_blocks(response)

    if not yaml_blocks:
        print("  ✗ 未找到 YAML 输出")
        (scenario_dir / "analysis.json").write_text(
            json.dumps({"error": "no yaml", "raw_preview": response[:500]}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return {"scenario": sid, "elapsed": elapsed, "yaml_found": 0, "pass": False}

    # Save all YAML blocks
    for i, blk in enumerate(yaml_blocks):
        (scenario_dir / f"block_{i}.yaml").write_text(
            yaml.dump(blk, allow_unicode=True, default_flow_style=False), encoding="utf-8"
        )

    # ── Identify which block is intake_result vs downstream file ──
    intake_result = None
    downstream_file = None
    downstream_file_type = "unknown"

    for blk in yaml_blocks:
        # intake_result is identified by intake_status field specifically
        if "intake_status" in blk and intake_result is None:
            intake_result = blk
        # Downstream files: identified by their unique structural keys
        elif "assessment" in blk and downstream_file is None:
            downstream_file = blk
            downstream_file_type = "paper_request"
        elif "slot_id" in blk and downstream_file is None:
            downstream_file = blk
            downstream_file_type = "slot_blueprint"
        elif blk.get("task_type") == "retrieval" and "keywords" in str(blk) and downstream_file is None:
            downstream_file = blk
            downstream_file_type = "retrieval_query"

    # If only one block and it has both, split mentally
    if intake_result is None and yaml_blocks:
        intake_result = yaml_blocks[0]

    print(f"  YAML blocks: {len(yaml_blocks)} (intake_result={'yes' if intake_result else 'no'}, downstream={'yes' if downstream_file else 'no'})")

    # ── Inspect intake_result ──
    intake_report = inspect_intake_result(intake_result or {}, f"{sid}_intake")
    (scenario_dir / "intake_inspection.json").write_text(
        json.dumps(intake_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  [intake_result 检查]")
    print(f"    task_type:     {intake_report.get('task_type')}")
    print(f"    intake_status: {intake_report.get('intake_status')}")
    print(f"    confidence:    {intake_report.get('confidence_level')}")
    print(f"    can_route:     {intake_report.get('can_route')}")
    print(f"    next_action:   {intake_report.get('next_action')}")
    print(f"    next_input:    {intake_report.get('next_input')}")
    if intake_report.get("confidence_missing"):
        print(f"    missing:       {intake_report['confidence_missing']}")
    if intake_report.get("confidence_contradictions"):
        print(f"    contradictions:{intake_report['confidence_contradictions']}")

    # ── Inspect downstream file ──
    compose_trace = None
    if downstream_file:
        file_type = downstream_file_type

        (scenario_dir / f"{file_type}.yaml").write_text(
            yaml.dump(downstream_file, allow_unicode=True, default_flow_style=False), encoding="utf-8"
        )

        if file_type == "paper_request":
            pr_report = inspect_paper_request(downstream_file, f"{sid}_paper_request")
            (scenario_dir / "paper_request_inspection.json").write_text(
                json.dumps(pr_report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"\n  [paper_request 检查]")
            print(f"    subjects:        {pr_report.get('subjects')}")
            print(f"    total_score:     {pr_report.get('total_score')}")
            print(f"    duration:        {pr_report.get('duration_minutes')}min")
            print(f"    primary_chapters:{pr_report.get('primary_chapters')}")
            print(f"    focus_points:    {pr_report.get('focus_points')}")
            print(f"    excluded_points: {pr_report.get('excluded_points')}")
            print(f"    question_types:  {pr_report.get('question_types')}")
            print(f"    difficulty:      {pr_report.get('difficulty_target')}")
            print(f"    distribution:    {pr_report.get('difficulty_distribution')}")
            print(f"    require:         {pr_report.get('require')}")
            print(f"    avoid:           {pr_report.get('avoid')}")

            # Trace into compose_runner
            compose_trace = trace_compose_mapping(downstream_file, f"{sid}_compose_mapping")
            (scenario_dir / "compose_mapping.json").write_text(
                json.dumps(compose_trace, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"\n  [compose_runner 映射]")
            print(f"    mapping_ok:      {compose_trace.get('mapping_ok')}")
            print(f"    user_requirements: {compose_trace.get('user_requirements', '')[:120]}...")
            print(f"    subject_files:   {compose_trace.get('subject_files')}")
            print(f"    slot_hints:      {compose_trace.get('slot_templates_hints')}")
            print(f"    model_routing:   {compose_trace.get('model_routing')}")

        elif file_type == "slot_blueprint":
            print(f"\n  [slot_blueprint 检查]")
            print(f"    slot_id:          {downstream_file.get('slot_id')}")
            print(f"    question_type:    {downstream_file.get('question_type')}")
            print(f"    target_subject:   {downstream_file.get('target_subject')}")
            print(f"    primary_target:   {downstream_file.get('primary_target_name')}")
            print(f"    target_family:    {downstream_file.get('target_family')}")
            print(f"    difficulty:       {downstream_file.get('difficulty_level')}")
            print(f"    score:            {downstream_file.get('score')}")
            print(f"    selected_knowledge: {downstream_file.get('active_selection', {}).get('selected_knowledge')}")

    # ── Overall assessment ──
    can_route = intake_report.get("can_route")
    conf_level = intake_report.get("confidence_level")

    issues = []

    # Check: route_gate consistency
    if can_route and conf_level in ("low", "blocked", "unsupported"):
        issues.append(f"INCONSISTENT: can_route=true but confidence={conf_level}")

    # Check: downstream file present when gate passed
    if can_route and not downstream_file:
        issues.append("MISSING: gate passed but no downstream file produced")

    # Check: downstream file absent when gate not passed
    if not can_route and downstream_file:
        issues.append("LEAK: gate not passed but downstream file present")

    # Check: compose mapping works
    if compose_trace and not compose_trace.get("mapping_ok"):
        issues.append(f"MAPPING_FAIL: {compose_trace.get('error')}")

    overall_pass = len(issues) == 0
    icon = "✓ PASS" if overall_pass else "✗ ISSUES"

    print(f"\n  结果: {icon}")
    if issues:
        for issue in issues:
            print(f"    ⚠ {issue}")

    # Save analysis summary
    analysis = {
        "scenario": sid,
        "name": scenario["name"],
        "teacher_input": scenario["teacher_input"],
        "elapsed_sec": round(elapsed, 1),
        "intake": intake_report,
        "has_downstream": downstream_file is not None,
        "compose_trace": compose_trace,
        "issues": issues,
        "overall_pass": overall_pass,
    }
    (scenario_dir / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    return analysis


# ── Main ───────────────────────────────────────────────────────────

async def main():
    print("=" * 70)
    print("Intake Layer 端到端文档产物追踪测试")
    print(f"产物目录: {OUTPUT_DIR}")
    print("=" * 70)

    system_prompt = load_system_prompt()
    print(f"System prompt: {len(system_prompt)} chars")

    gateway = get_gateway("glm5.1")
    print(f"Gateway: {gateway._provider_name}")

    results = []
    for scenario in TRICKY_SCENARIOS:
        r = await run_scenario(gateway, system_prompt, scenario)
        results.append(r)

    # ── Summary ──
    print("\n" + "=" * 70)
    print("汇总报告")
    print("=" * 70)

    for r in results:
        sid = r.get("scenario", "?")
        if "error" in r:
            print(f"  {sid}: LLM ERROR ({r['error'][:60]})")
            continue
        icon = "✓" if r.get("overall_pass") else "✗"
        downstream = "有下游文件" if r.get("has_downstream") else "无下游文件"
        can_route = r.get("intake", {}).get("can_route")
        conf = r.get("intake", {}).get("confidence_level")
        status = r.get("intake", {}).get("intake_status")
        print(f"  {sid}: {icon} | status={status} conf={conf} route={can_route} | {downstream} | {r.get('elapsed_sec', 0)}s")
        for issue in r.get("issues", []):
            print(f"       ⚠ {issue}")

    total = len(results)
    passed = sum(1 for r in results if r.get("overall_pass"))
    errors = sum(1 for r in results if "error" in r)
    print(f"\n  通过: {passed}/{total}  错误: {errors}")
    print(f"  产物目录: {OUTPUT_DIR}")
    print(f"  每个场景包含: raw_response.md, block_*.yaml, analysis.json, (paper_request/slot_blueprint + inspection)")

    return passed == total and errors == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
