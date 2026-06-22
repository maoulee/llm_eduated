"""Teacher simulation — end-to-end LLM test for the intake layer.

Spawns a simulated teacher that sends realistic requests to the intake agent,
then evaluates whether the intake layer produces correct structured output.

Uses real LLM calls (GLM-5.1) with the human_intake.md agent prompt.
"""

import asyncio
import sys
import time
from pathlib import Path

import yaml

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core_new.llm_gateway import get_gateway

# ── Load agent prompt ──────────────────────────────────────────────

AGENT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "core_new" / "doc_pipeline" / "agents" / "human_intake.md"
SKILL_PROMPT_PATH = Path(__file__).resolve().parent.parent / "core_new" / "doc_pipeline" / "skills" / "intake_core" / "SKILL.md"

def load_system_prompt() -> str:
    """Load the human_intake agent prompt + intake_core skill as system prompt."""
    agent = AGENT_PROMPT_PATH.read_text(encoding="utf-8")
    # Strip YAML frontmatter (between --- markers)
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

你必须以 YAML 格式输出 intake_result，包含以下字段：
- task_type: paper | single_question | retrieval
- intake_status: collecting | needs_user_choice | ready | frontdesk_only | rejected
- confidence.level: high | medium | low | blocked | unsupported
- routing.can_route: true | false
- routing.next_action: run_compose | run_single_pipeline | retrieve | ask_user | recommend_alternatives | reject
- routing.next_input: paper_request.yaml | slot_blueprint.yaml | retrieval_query.yaml | null

如果 route_gate 通过 (routing.can_route=true)，额外输出对应的下游文件内容。

用 ```yaml ... ``` 代码块包裹你的结构化输出。
"""


# ── Validation helpers ─────────────────────────────────────────────

def extract_yaml_blocks(text: str) -> list[dict]:
    """Extract all YAML blocks from LLM response."""
    blocks = []
    in_block = False
    lines = []
    for line in text.split("\n"):
        if "```yaml" in line.lower() or "```" in line and in_block:
            if in_block:
                try:
                    data = yaml.safe_load("\n".join(lines))
                    if isinstance(data, dict):
                        blocks.append(data)
                except yaml.YAMLError:
                    pass
                lines = []
                in_block = False
            else:
                in_block = True
                lines = []
        elif in_block:
            lines.append(line)
    return blocks


def validate_intake_result(data: dict, scenario: str) -> dict:
    """Validate intake_result against expected behavior. Returns report."""
    report = {"scenario": scenario, "checks": [], "passed": True}

    def check(name: str, condition: bool, detail: str = ""):
        report["checks"].append({"name": name, "pass": condition, "detail": detail})
        if not condition:
            report["passed"] = False

    # Basic structure
    check("has_task_type", "task_type" in data, f"got keys: {list(data.keys())[:10]}")

    # Confidence level
    conf = data.get("confidence", {})
    if isinstance(conf, dict):
        level = conf.get("level", "")
        check("has_confidence_level", level in ("high", "medium", "low", "blocked", "unsupported"),
              f"got: {level}")
    else:
        check("has_confidence_level", False, f"confidence is not a dict: {type(conf)}")

    # Routing
    routing = data.get("routing", {})
    if isinstance(routing, dict):
        can_route = routing.get("can_route", None)
        check("has_routing.can_route", can_route is not None, f"got: {can_route}")
        check("has_routing.next_action", "next_action" in routing,
              f"got keys: {list(routing.keys())}")
    else:
        check("has_routing", False, f"routing is not a dict: {type(routing)}")

    # Intake status
    status = data.get("intake_status", "")
    check("has_intake_status", status in ("collecting", "needs_user_choice", "ready", "frontdesk_only", "rejected"),
          f"got: {status}")

    return report


def validate_scenario_expectations(data: dict, scenario_id: str) -> dict:
    """Scenario-specific expectations."""
    report = {"scenario_id": scenario_id, "expectations": [], "met": True}

    def expect(name: str, condition: bool, detail: str = ""):
        report["expectations"].append({"name": name, "met": condition, "detail": detail})
        if not condition:
            report["met"] = False

    routing = data.get("routing", {})
    conf = data.get("confidence", {})
    conf_level = conf.get("level", "") if isinstance(conf, dict) else ""
    can_route = routing.get("can_route", None) if isinstance(routing, dict) else None
    status = data.get("intake_status", "")

    if scenario_id == "A":
        expect("task_type=paper", data.get("task_type") == "paper", f"got: {data.get('task_type')}")
        expect("confidence=high", conf_level == "high", f"got: {conf_level}")
        expect("can_route=true", can_route == True, f"got: {can_route}")
        expect("status=ready", status == "ready", f"got: {status}")
        expect("next_action=run_compose",
               routing.get("next_action") == "run_compose" if isinstance(routing, dict) else False,
               f"got: {routing.get('next_action') if isinstance(routing, dict) else 'N/A'}")

    elif scenario_id == "B":
        expect("task_type=paper", data.get("task_type") == "paper", f"got: {data.get('task_type')}")
        expect("can_route=false (info insufficient)", can_route == False, f"got: {can_route}")
        expect("status not ready", status in ("collecting", "needs_user_choice"),
               f"got: {status}")
        expect("confidence low or below", conf_level in ("low", "medium"),
               f"got: {conf_level}")
        expect("no downstream file", routing.get("next_input") is None if isinstance(routing, dict) else True,
               f"got: {routing.get('next_input') if isinstance(routing, dict) else 'N/A'}")

    elif scenario_id == "C":
        expect("confidence=unsupported or blocked", conf_level in ("unsupported", "blocked"),
               f"got: {conf_level}")
        expect("can_route=false", can_route == False, f"got: {can_route}")
        expect("status=frontdesk_only or rejected", status in ("frontdesk_only", "rejected"),
               f"got: {status}")
        expect("next_action not run_*",
               routing.get("next_action") in ("ask_user", "recommend_alternatives", "reject") if isinstance(routing, dict) else True,
               f"got: {routing.get('next_action') if isinstance(routing, dict) else 'N/A'}")

    return report


# ── Teacher scenarios ──────────────────────────────────────────────

TEACHER_SCENARIOS = [
    {
        "id": "A",
        "name": "信息充足 — 直接路由组卷",
        "teacher_input": "帮我组一套数据结构期末考试卷，100分，120分钟，覆盖全书，中等难度，重点考树和图，选择题15道，综合题2道",
        "description": "教师提供了完整信息：科目、类型、分数、时间、范围、难度、题型 → 应直接通过 route_gate",
    },
    {
        "id": "B",
        "name": "信息不足 — 需要追问",
        "teacher_input": "组一套期末卷，100分",
        "description": "教师只说了期末卷和分数，缺少科目、范围、难度 → 应追问，不能进下游",
    },
    {
        "id": "C",
        "name": "超出范围 — 拒绝",
        "teacher_input": "出一道量子计算题，难度高一点",
        "description": "量子计算不在 408 四科范围 → 应拒绝，frontdesk_only",
    },
]


# ── Main simulation ───────────────────────────────────────────────

async def run_scenario(gateway, system_prompt: str, scenario: dict) -> dict:
    """Run one teacher scenario through the intake agent."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"教师：{scenario['teacher_input']}"},
    ]

    print(f"\n{'='*60}")
    print(f"Scenario {scenario['id']}: {scenario['name']}")
    print(f"{'='*60}")
    print(f"教师输入: {scenario['teacher_input']}")
    print(f"期望: {scenario['description']}")
    print()

    t0 = time.time()
    result = await gateway.generate_text(messages, max_tokens=2000)
    elapsed = time.time() - t0

    if not result.ok:
        print(f"  LLM ERROR: {result.error_message}")
        return {"scenario": scenario["id"], "error": result.error_message, "elapsed": elapsed}

    response = result.content or ""
    print(f"  LLM 响应 ({elapsed:.1f}s):")
    print(f"  {response[:500]}...")
    print()

    # Extract YAML blocks
    yaml_blocks = extract_yaml_blocks(response)
    if not yaml_blocks:
        print("  WARNING: No valid YAML block found in response")
        # Try to find intake_result in plain text
        return {
            "scenario": scenario["id"],
            "elapsed": elapsed,
            "raw_response": response[:1000],
            "yaml_blocks_found": 0,
            "validation": {"passed": False, "checks": [{"name": "yaml_output", "pass": False, "detail": "No YAML block in response"}]},
        }

    # Take the first (main) YAML block as intake_result
    intake_result = yaml_blocks[0]
    print(f"  解析到 YAML (keys: {list(intake_result.keys())[:8]})")

    # Validate
    basic_report = validate_intake_result(intake_result, scenario["id"])
    expect_report = validate_scenario_expectations(intake_result, scenario["id"])

    print(f"\n  基本结构检查:")
    for c in basic_report["checks"]:
        icon = "✓" if c["pass"] else "✗"
        print(f"    {icon} {c['name']}: {c.get('detail', 'OK')}")

    print(f"\n  场景期望检查 (Scenario {scenario['id']}):")
    for e in expect_report["expectations"]:
        icon = "✓" if e["met"] else "✗"
        print(f"    {icon} {e['name']}: {e.get('detail', 'OK')}")

    # Check for downstream file if gate passed
    can_route = intake_result.get("routing", {}).get("can_route", False) if isinstance(intake_result.get("routing"), dict) else False
    if can_route and len(yaml_blocks) > 1:
        print(f"\n  下游文件: 检测到 {len(yaml_blocks)-1} 个额外 YAML 块")
        for i, blk in enumerate(yaml_blocks[1:], 1):
            print(f"    Block {i}: keys={list(blk.keys())[:5]}")

    overall = basic_report["passed"] and expect_report["met"]
    icon = "✓ PASS" if overall else "✗ FAIL"
    print(f"\n  结果: {icon}")

    return {
        "scenario": scenario["id"],
        "elapsed": elapsed,
        "yaml_blocks_found": len(yaml_blocks),
        "basic_passed": basic_report["passed"],
        "expectations_met": expect_report["met"],
        "overall": overall,
        "intake_result": intake_result,
    }


async def main():
    print("=" * 60)
    print("Intake Layer 教师模拟测试")
    print("=" * 60)

    # Load system prompt
    print("加载 intake agent prompt...")
    system_prompt = load_system_prompt()
    print(f"  System prompt: {len(system_prompt)} chars")

    # Get LLM gateway
    print("初始化 LLM gateway (GLM-5.1)...")
    gateway = get_gateway("glm5.1")
    print(f"  Gateway: {gateway._provider_name}")

    # Run scenarios
    results = []
    for scenario in TEACHER_SCENARIOS:
        r = await run_scenario(gateway, system_prompt, scenario)
        results.append(r)

    # Summary
    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r.get("overall", False))
    errors = sum(1 for r in results if "error" in r)
    total_time = sum(r.get("elapsed", 0) for r in results)

    for r in results:
        sid = r.get("scenario", "?")
        if "error" in r:
            print(f"  Scenario {sid}: ERROR ({r['error'][:50]})")
        else:
            icon = "✓ PASS" if r.get("overall") else "✗ FAIL"
            print(f"  Scenario {sid}: {icon} ({r.get('elapsed', 0):.1f}s, {r.get('yaml_blocks_found', 0)} YAML blocks)")

    print(f"\n  通过: {passed}/{total}  错误: {errors}  总耗时: {total_time:.1f}s")
    print(f"  结果: {'ALL PASSED ✓' if passed == total and errors == 0 else 'HAS FAILURES ✗'}")

    return passed == total and errors == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
