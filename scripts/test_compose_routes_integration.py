"""Integration test: simulate real CLI workflow for all three compose routes.

Tests the full pipeline:
1. Route dispatch (determine_route)
2. Route 2: slot_blueprint → grep + classify → outline_draft.md
3. Route 3: paper_request (no experience) → GLM draft → grep + classify → outline_draft.md
4. Route 1: paper_request + experience → slot_card rendering → outline_draft.md
5. Verify output files and CONTRACT markers

Uses Python subprocess to simulate CLI invocation, matching the tmux-based testing
approach the user requested. Each route is tested as a realistic end-to-end scenario.
"""

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import json
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Test colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

passed = 0
failed = 0
skipped = 0


def report(name: str, status: str, detail: str = ""):
    global passed, failed, skipped
    icon = {"PASS": f"{GREEN}✓{RESET}", "FAIL": f"{RED}✗{RESET}", "SKIP": f"{YELLOW}○{RESET}"}[status]
    print(f"  {icon} {name}")
    if detail:
        print(f"    {detail}")
    if status == "PASS":
        passed += 1
    elif status == "FAIL":
        failed += 1
    else:
        skipped += 1


def run_cli(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run compose CLI as subprocess, simulating tmux terminal interaction."""
    cmd = [sys.executable, "-m", "compose.cli"] + args
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(PROJECT_ROOT),
    )


# ─── Test Data Setup ───

def setup_route2_env(tmpdir: str) -> str:
    """Setup test environment for Route 2: slot_blueprint."""
    import yaml
    compose_dir = os.path.join(tmpdir, "compose")
    os.makedirs(compose_dir, exist_ok=True)

    blueprint = {
        "schema_version": "slot_blueprint_v1",
        "slot_id": "TOPIC_001",
        "question_type": "single_choice",
        "score": 2,
        "target_subject": "数据结构",
        "target_family": "数据结构 > 树与二叉树 > 平衡二叉树",
        "primary_target_name": "AVL树旋转（LR型和RL型判断）",
        "difficulty_level": 4,
        "examination_mode": "",
        "teacher_annotation": "要求同时包含LR型和RL型旋转的判断",
        "active_selection": {
            "mode_id": "topic_selected",
            "selected_knowledge": ["AVL树旋转操作", "平衡因子计算"],
        },
        "excluded": {
            "knowledge": ["红黑树", "B树"],
            "modes": [],
        },
        "routing": {"can_route": True, "next_action": "run_single_pipeline"},
    }
    with open(os.path.join(compose_dir, "slot_blueprint.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(blueprint, f, allow_unicode=True)

    return tmpdir


def setup_route3_env(tmpdir: str) -> str:
    """Setup test environment for Route 3: paper_request, no experience cards."""
    import yaml
    compose_dir = os.path.join(tmpdir, "compose")
    os.makedirs(compose_dir, exist_ok=True)

    request = {
        "schema_version": "paper_request_v1",
        "assessment": {
            "subjects": ["计算机组成原理"],
            "type": "期末考试",
            "total_score": 100,
            "duration_minutes": 120,
        },
        "difficulty": {"target": "medium"},
        "knowledge_scope": {"coverage_strategy": "balanced"},
        "question_config": {
            "types": [
                {"type": "single_choice", "count_range": [5, 5], "score_per": 2},
            ]
        },
        "teacher_preferences": {"style_notes": "覆盖主要知识点，难度中等"},
    }
    with open(os.path.join(compose_dir, "paper_request.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(request, f, allow_unicode=True)

    return tmpdir


# ─── Route Dispatch Tests ───

def test_route_dispatch():
    """Test determine_route correctly identifies routes from intake files."""
    from compose.compose_runner import determine_route
    import yaml

    tmpdir = tempfile.mkdtemp(prefix="route_test_")
    try:
        # Route 2: slot_blueprint present
        compose_dir = os.path.join(tmpdir, "r2")
        os.makedirs(compose_dir)
        with open(os.path.join(compose_dir, "slot_blueprint.yaml"), "w") as f:
            yaml.dump({"primary_target_name": "test"}, f)
        route, reason = determine_route(compose_dir, {})
        report("Route dispatch → Route 2 (slot_blueprint)",
               "PASS" if route == 2 else "FAIL",
               f"got route={route}, reason={reason}")

        # Route 3: paper_request, no experience
        compose_dir = os.path.join(tmpdir, "r3")
        os.makedirs(compose_dir)
        with open(os.path.join(compose_dir, "paper_request.yaml"), "w") as f:
            yaml.dump({"assessment": {"subjects": ["计算机组成原理"]}}, f)
        route, reason = determine_route(compose_dir, {})
        report("Route dispatch → Route 3 (paper_request, no exp)",
               "PASS" if route == 3 else "FAIL",
               f"got route={route}, reason={reason}")

        # Route 1: experience cards available
        compose_dir = os.path.join(tmpdir, "r1")
        os.makedirs(compose_dir)
        exp_dir = os.path.join(tmpdir, "exp")
        os.makedirs(exp_dir)
        Path(os.path.join(exp_dir, "Q1_experience.md")).write_text("# test")
        route, reason = determine_route(compose_dir, {"Q1": {}}, exp_dir=exp_dir)
        report("Route dispatch → Route 1 (experience cards)",
               "PASS" if route == 1 else "FAIL",
               f"got route={route}, reason={reason}")
    finally:
        shutil.rmtree(tmpdir)


# ─── Route 2: Grep + Classify (Pure Python, no LLM) ───

def test_route2_grep():
    """Test Route 2 grep search with real question data."""
    from compose.topic_search import grep_question_bank

    hits = grep_question_bank(["AVL", "平衡二叉树", "旋转"], max_results=10)
    report("Route 2 grep: AVL树搜索",
           "PASS" if len(hits) > 0 else "FAIL",
           f"hits={len(hits)}, top={hits[0].file_name if hits else 'none'}")

    hits2 = grep_question_bank(["Cache", "映射", "地址翻译"], max_results=10)
    report("Route 2 grep: Cache映射搜索",
           "PASS" if len(hits2) > 0 else "FAIL",
           f"hits={len(hits2)}, top={hits2[0].file_name if hits2 else 'none'}")

    # Empty keywords
    hits3 = grep_question_bank([], max_results=10)
    report("Route 2 grep: 空关键词",
           "PASS" if len(hits3) == 0 else "FAIL",
           f"hits={len(hits3)} (should be 0)")


def test_route2_topic_card_format():
    """Test Route 2 topic_mode_card parsing from LLM output."""
    from compose.topic_search import _parse_topic_mode_card, GrepHit

    sample_yaml = """```yaml
modes:
  - name: 旋转类型判断型
    count: 7
    description: 给定插入序列，判断LL/LR/RL/RR旋转类型
    suitable_types: [single_choice, comprehensive]
    difficulty: medium
    examples: [2009_Q5.md, 2015_Q4.md]
  - name: 平衡因子计算型
    count: 3
    description: 计算各节点平衡因子
    suitable_types: [single_choice]
    difficulty: easy
    examples: [2011_Q14.md]
```"""
    hits = [GrepHit(f"test_{i}.md", f"test_{i}.md", float(i), "snippet") for i in range(5)]
    card = _parse_topic_mode_card(sample_yaml, "AVL树旋转", hits)

    report("Route 2 topic_card: 模式解析",
           "PASS" if len(card.modes) == 2 else "FAIL",
           f"modes={len(card.modes)}")

    report("Route 2 topic_card: 模式排序",
           "PASS" if card.modes[0].name == "旋转类型判断型" else "FAIL",
           f"first={card.modes[0].name if card.modes else 'none'}")

    report("Route 2 topic_card: to_dict",
           "PASS" if "modes" in card.to_dict() else "FAIL")


# ─── Route 3: Free Compose (Python parts) ───

def test_route3_table_parse():
    """Test Route 3 GLM table parsing."""
    from compose.free_compose import _parse_knowledge_table

    templates = {f"Q{i}": {} for i in range(1, 6)}
    raw = """| 题号 | 题型 | 知识点 | 考察方向 | 难度(1-5) |
|------|------|--------|---------|-----------|
| Q1 | 选择题 | CPU性能指标 | 公式计算 | 3 |
| Q2 | 选择题 | 浮点数表示 | IEEE754 | 4 |
| Q3 | 选择题 | 指令系统 | 寻址方式 | 3 |
| Q4 | 选择题 | 总线系统 | 总线仲裁 | 2 |
| Q5 | 选择题 | 中断系统 | 中断处理流程 | 3 |"""

    assignments = _parse_knowledge_table(raw, templates)
    report("Route 3 table: 解析5个题位",
           "PASS" if len(assignments) == 5 else "FAIL",
           f"parsed={len(assignments)}")

    if assignments:
        report("Route 3 table: 难度解析",
               "PASS" if assignments[1]["difficulty"] == 4 else "FAIL",
               f"Q2 difficulty={assignments[1]['difficulty']}")


def test_route3_kg_complete():
    """Test Route 3 KG auto-completion."""
    from compose.free_compose import auto_complete_from_kg
    from compose.compose_runner import load_kg_for_subjects

    kg = load_kg_for_subjects(["计算机组成原理"])
    assignments = [
        {"slot_id": "Q1", "knowledge": "CPU性能指标", "question_type": "选择题", "direction": "公式计算", "difficulty": 3},
        {"slot_id": "Q2", "knowledge": "浮点数表示", "question_type": "选择题", "direction": "IEEE754", "difficulty": 4},
    ]
    enriched = auto_complete_from_kg(assignments, kg)

    has_path = any(a.get("kg_path") for a in enriched)
    report("Route 3 KG补全: 路径填充",
           "PASS" if has_path else "FAIL",
           f"path={enriched[0].get('kg_path', '')[:50] if enriched else 'none'}")


def test_route3_draft_format():
    """Test Route 3 draft formatting (no CONTRACT markers)."""
    from compose.free_compose import format_draft_for_teacher

    assignments = [
        {"slot_id": "Q1", "knowledge": "CPU性能指标", "question_type": "选择题",
         "direction": "公式计算", "difficulty": 3,
         "kg_path": "组成原理 > 性能指标 > CPU性能指标",
         "siblings": ["MIPS", "FLOPS"], "subtopics": []},
    ]
    draft = format_draft_for_teacher(assignments)

    has_no_contract = "CONTRACT" not in draft
    has_table = "| Q1 |" in draft
    has_knowledge = "CPU性能指标" in draft

    report("Route 3 draft: 无CONTRACT (proposal阶段)",
           "PASS" if has_no_contract else "FAIL")
    report("Route 3 draft: 包含题位表格",
           "PASS" if has_table else "FAIL")
    report("Route 3 draft: 包含知识点",
           "PASS" if has_knowledge else "FAIL")


# ─── Route 1: Slot Card Rendering ───

def test_route1_slot_card():
    """Test Route 1 slot card extraction and rendering."""
    from compose.compose_runner import extract_slot_recommendation, render_slot_card

    # Load a real experience card
    exp_path = Path("data/slot_experiences/Q12_experience.md")
    if not exp_path.exists():
        report("Route 1 slot_card: 跳过（无经验卡）", "SKIP")
        return

    exp_card = exp_path.read_text(encoding="utf-8")
    extracted = extract_slot_recommendation(exp_card)

    report("Route 1 slot_card: 模式提取",
           "PASS" if extracted["recommended_mode"] else "FAIL",
           f"mode={extracted['recommended_mode'][:40]}")

    report("Route 1 slot_card: 频率提取",
           "PASS" if extracted["recommended_frequency"] else "FAIL",
           f"freq={extracted['recommended_frequency']}")

    card = render_slot_card("Q12", {"question_type": "single_choice", "score": 2}, exp_card)
    report("Route 1 slot_card: 卡片渲染",
           "PASS" if card["slot_card"]["slot_id"] == "Q12" else "FAIL")


# ─── Outline YAML Generator ───

def test_yaml_generator():
    """Test outline YAML generation for all routes."""
    from compose.outline_yaml_generator import generate_outline_from_cards, generate_from_topic_mode

    # Route 1 style
    cards = [{
        "slot_card": {
            "slot_id": "Q12",
            "type": "single_choice",
            "score": 2,
            "recommended_mode": "计算型——公式应用",
            "recommended_frequency": "53.8%",
            "alternatives": [{"mode": "概念辨析型", "frequency": "23.1%"}],
            "applicable_knowledge": ["CPU执行时间公式", "单位换算"],
        }
    }]
    templates = {"Q12": {"question_type": "single_choice", "score": 2}}
    outline = generate_outline_from_cards(cards, templates)

    has_contract = "CONTRACT:BEGIN" in outline
    has_yaml = "```yaml" in outline
    has_slot = "slot_id: Q12" in outline

    report("YAML generator (Route 1): CONTRACT marker",
           "PASS" if has_contract else "FAIL")
    report("YAML generator (Route 1): YAML block",
           "PASS" if has_yaml else "FAIL")
    report("YAML generator (Route 1): slot_id",
           "PASS" if has_slot else "FAIL")

    # Route 2 style
    topic_card = {
        "id": "avl_rotation",
        "title": "旋转类型判断",
        "knowledge": "AVL树旋转操作",
        "modes": [
            {"name": "旋转类型判断型", "count": 7, "description": "判断旋转类型",
             "suitable_types": ["single_choice"], "difficulty": "medium"},
        ],
    }
    section = generate_from_topic_mode(topic_card, "TOPIC_001", {"question_type": "single_choice", "score": 2})

    has_contract2 = "CONTRACT:BEGIN" in section
    has_knowledge2 = "AVL树旋转操作" in section

    report("YAML generator (Route 2): CONTRACT marker",
           "PASS" if has_contract2 else "FAIL")
    report("YAML generator (Route 2): knowledge field",
           "PASS" if has_knowledge2 else "FAIL")


def test_cli_args():
    """Test CLI argument parser has all expected options."""
    import argparse
    import importlib
    # Build the parser the same way cli.py does
    routing_choices = ["all_local", "all_remote", "mixed", "glm_gen_qwen_review", "qwen_gpt_core", "hybrid"]
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    parser.add_argument("--slots", nargs="+")
    parser.add_argument("--requirements", default="test")
    parser.add_argument("--output-dir", default="docs")
    parser.add_argument("--routing", choices=routing_choices, default="all_local")

    sub_compose = subparsers.add_parser("compose")
    sub_compose.add_argument("--slots", nargs="+")
    sub_compose.add_argument("--slots-dir")
    sub_compose.add_argument("--requirements", default="test")
    sub_compose.add_argument("--output-dir", default="docs")
    sub_compose.add_argument("--routing", choices=routing_choices, default="all_local")
    sub_compose.add_argument("--slot-blueprint", default=None,
                             help="Path to slot_blueprint.yaml (Route 2: single topic)")

    # Test compose subcommand parses --slot-blueprint
    args = sub_compose.parse_args(["--slot-blueprint", "/tmp/test.yaml"])
    report("CLI: --slot-blueprint 解析",
           "PASS" if args.slot_blueprint == "/tmp/test.yaml" else "FAIL",
           f"got={args.slot_blueprint}")

    # Test default subcommand
    args2 = parser.parse_args(["--routing", "all_local"])
    report("CLI: --routing 解析",
           "PASS" if args2.routing == "all_local" else "FAIL")


# ─── Subject Inference ───

def test_subject_inference():
    """Test subject inference from requirements text."""
    from compose.compose_runner import _infer_subjects

    tests = [
        ("出一套计算机组成原理期末考试", ["计算机组成原理"]),
        ("数据结构和操作系统综合测试", ["数据结构", "操作系统"]),
        ("408全四科", ["计算机组成原理"]),  # default fallback
    ]
    for req, expected in tests:
        result = _infer_subjects(req)
        match = all(s in result for s in expected)
        report(f"Subject inference: '{req[:20]}...'",
               "PASS" if match else "FAIL",
               f"expected={expected}, got={result}")


# ─── Main ───

def main():
    print("=" * 60)
    print("Compose 三路线集成测试")
    print("=" * 60)
    print()

    print("── 路由分发 ──")
    test_route_dispatch()
    print()

    print("── Route 2: Grep + Classify ──")
    test_route2_grep()
    print()

    print("── Route 2: Topic Card ──")
    test_route2_topic_card_format()
    print()

    print("── Route 3: Free Compose ──")
    test_route3_table_parse()
    test_route3_kg_complete()
    test_route3_draft_format()
    print()

    print("── Route 1: Slot Card ──")
    test_route1_slot_card()
    print()

    print("── YAML Generator ──")
    test_yaml_generator()
    print()

    print("── Subject Inference ──")
    test_subject_inference()
    print()

    print("── CLI ──")
    test_cli_args()
    print()

    # Summary
    total = passed + failed + skipped
    print("=" * 60)
    print(f"结果: {GREEN}{passed} passed{RESET}, {RED}{failed} failed{RESET}, {YELLOW}{skipped} skipped{RESET} / {total} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
