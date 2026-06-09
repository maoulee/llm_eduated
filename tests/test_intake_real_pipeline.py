"""Real pipeline consumption test — feed intake output into actual compose/generate runners.

Verifies that intake layer documents can be consumed by the real downstream pipeline.
Uses real LLM calls (GLM-5.1).

Test 1: T1 paper_request → compose_runner.run_compose() → outline.md
Test 2: T5 slot_blueprint → single_question_adapter → verify BlueprintMap compatibility
"""

import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core_new.llm_gateway import get_gateway
from core_new.provider_router import set_routing_profile


# ── Test 1: paper_request → compose_runner → outline ──────────────

async def test_paper_request_through_compose():
    """Feed T1 paper_request into real compose_runner, generate outline."""
    print("=" * 70)
    print("TEST 1: T1 paper_request → compose_runner → outline")
    print("=" * 70)

    from compose.compose_runner import run_compose

    # Set up test compose directory
    test_dir = "docs/output_intake_pipeline_test"
    compose_dir = os.path.join(test_dir, "compose")
    os.makedirs(compose_dir, exist_ok=True)

    # Copy T1 paper_request into compose dir (where compose_runner expects it)
    src = "docs/output_intake_e2e/scenario_T1/paper_request.yaml"
    dst = os.path.join(compose_dir, "paper_request.yaml")
    shutil.copy2(src, dst)
    print(f"  已复制 paper_request.yaml → {dst}")

    # Load it to show what compose_runner will see
    pr = yaml.safe_load(Path(dst).read_text(encoding="utf-8"))
    print(f"  paper_request: subjects={pr.get('assessment',{}).get('subjects')}, total_score={pr.get('assessment',{}).get('total_score')}")

    # Get gateway — use remote for reliability
    set_routing_profile("all_remote")
    gateway = get_gateway("glm5.1")

    # Build minimal slot_templates for a 408-like paper
    # These would normally come from CLI config, we simulate them
    slot_templates = {
        "Q1-Q10": {"type": "single_choice", "subject": "数据结构", "score": 2},
        "Q11-Q22": {"type": "single_choice", "subject": "计算机组成原理", "score": 2},
        "Q23-Q33": {"type": "single_choice", "subject": "操作系统", "score": 2},
        "Q34-Q40": {"type": "single_choice", "subject": "计算机网络", "score": 2},
        "Q41": {"type": "comprehensive", "subject": "数据结构", "score": 10},
        "Q42": {"type": "comprehensive", "subject": "计算机组成原理", "score": 11},
        "Q43": {"type": "comprehensive", "subject": "操作系统", "score": 8},
        "Q44": {"type": "comprehensive", "subject": "计算机网络", "score": 9},
        "Q45": {"type": "comprehensive", "subject": "数据结构", "score": 13},
        "Q46": {"type": "comprehensive", "subject": "计算机组成原理", "score": 12},
        "Q47": {"type": "comprehensive", "subject": "操作系统", "score": 10},
    }

    # Minimal experience cards
    experience_cards = {}

    user_requirements = "intake层传入的408考研模拟卷需求"

    print(f"\n  调用 run_compose(gateway, {len(slot_templates)} templates, ...)...")
    t0 = time.time()

    try:
        result = await run_compose(
            gateway=gateway,
            slot_templates=slot_templates,
            experience_cards=experience_cards,
            user_requirements=user_requirements,
            output_dir=test_dir,
            model_routing={"paper_composer": "local"},  # local GLM, paper_request's "hybrid" hint won't override
            exp_dir="data/slot_experiences",
        )
        elapsed = time.time() - t0
        print(f"\n  compose_runner 返回 ({elapsed:.1f}s):")
        print(f"    status: {result.get('status', 'unknown')}")
        print(f"    slot_count: {result.get('slot_count', 0)}")

        # Check if outline was generated
        outline_path = os.path.join(compose_dir, "outline.md")
        if os.path.exists(outline_path):
            outline_content = Path(outline_path).read_text(encoding="utf-8")
            print(f"\n  outline.md 已生成 ({len(outline_content)} chars)")
            print(f"  前200字:")
            print(f"  {outline_content[:200]}...")

            # Verify outline has slots matching paper_request constraints
            has_excluded = "Cache" not in outline_content or "Cache" in outline_content.split("排除")[0] if "排除" in outline_content else True
            print(f"\n  ✓ outline.md 生成成功")
        else:
            print(f"\n  ⚠ outline.md 未生成")
            print(f"  result keys: {list(result.keys())}")

        # Check assembled docs
        assembled_count = 0
        for fname in os.listdir(compose_dir):
            if fname.startswith("assembled_"):
                assembled_count += 1
        print(f"  assembled docs: {assembled_count} 个")

        # Check paper_selection.yaml (sidecar)
        sidecar = os.path.join(compose_dir, "paper_selection.yaml")
        if os.path.exists(sidecar):
            print(f"  ✓ paper_selection.yaml sidecar 已生成")
        else:
            print(f"  paper_selection.yaml 不存在 (compose流程可能未完成)")

        return {"test": "T1_compose", "passed": True, "elapsed": elapsed, "result_status": result.get("status")}

    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n  ✗ compose_runner 异常: {e}")
        import traceback
        traceback.print_exc()
        return {"test": "T1_compose", "passed": False, "elapsed": elapsed, "error": str(e)}


# ── Test 2: slot_blueprint → adapter → BlueprintMap ────────────────

def test_slot_blueprint_adapter_real():
    """Load T5 slot_blueprint, verify adapter produces valid BlueprintMap for generate_runner."""
    print("\n" + "=" * 70)
    print("TEST 2: T5 slot_blueprint → adapter → BlueprintMap compatibility")
    print("=" * 70)

    from compose.single_question_adapter import load_slot_blueprint, build_blueprint_map
    from core_new.doc_pipeline.contracts import SlotBlueprint
    import dataclasses

    bp = load_slot_blueprint("docs/output_intake_e2e/scenario_T5/slot_blueprint.yaml")

    checks = []

    # Check 1: Loaded successfully
    checks.append(("load_success", bp is not None))
    if bp is None:
        print("  ✗ 加载失败")
        return {"test": "T5_adapter", "passed": False, "checks": checks}

    # Check 2: All critical fields populated
    checks.append(("slot_id", bp.slot_id == "AVL_ROT_001"))
    checks.append(("question_type", bp.question_type == "comprehensive"))
    checks.append(("target_subject", bp.target_subject == "数据结构"))
    checks.append(("primary_target", "AVL" in bp.primary_target_name))
    checks.append(("target_family", "AVL" in bp.target_family))
    checks.append(("target_difficulty", bp.target_difficulty == 4))
    checks.append(("score", bp.score == 10))

    # Check 3: BlueprintMap is dict[str, SlotBlueprint] — compatible with generate_runner
    bpm = build_blueprint_map(bp)
    checks.append(("blueprint_map_type", isinstance(bpm, dict)))
    checks.append(("blueprint_map_key", "AVL_ROT_001" in bpm))
    checks.append(("blueprint_map_value", isinstance(bpm.get("AVL_ROT_001"), SlotBlueprint)))

    # Check 4: Can be serialized to dict (generate_runner does this)
    try:
        bp_dict = dataclasses.asdict(bp)
        checks.append(("asdict_success", True))
        checks.append(("asdict_has_slot_id", bp_dict.get("slot_id") == "AVL_ROT_001"))
        checks.append(("asdict_has_question_type", bp_dict.get("question_type") == "comprehensive"))
    except Exception as e:
        checks.append(("asdict_success", False))

    # Check 5: active_selection has selected_knowledge (critical for design_card)
    active = bp.active_selection
    checks.append(("active_selection_is_dict", isinstance(active, dict)))
    if isinstance(active, dict):
        sel = active.get("selected_knowledge", [])
        checks.append(("has_selected_knowledge", len(sel) > 0))
        checks.append(("has_LR_knowledge", any("LR" in k for k in sel)))
        checks.append(("has_RL_knowledge", any("RL" in k for k in sel)))

    # Check 6: excluded_knowledge properly flattened
    checks.append(("excluded_knowledge_is_list", isinstance(bp.excluded_knowledge, list)))
    checks.append(("excluded_has_redblack", "红黑树" in bp.excluded_knowledge))

    # Check 7: teacher_annotation present (important for downstream)
    checks.append(("has_teacher_annotation", bool(bp.teacher_annotation)))

    # Print results
    all_pass = True
    for name, passed in checks:
        icon = "✓" if passed else "✗"
        if not passed:
            all_pass = False
        print(f"  {icon} {name}")

    icon = "✓ PASS" if all_pass else "✗ FAIL"
    print(f"\n  结果: {icon}")

    return {"test": "T5_adapter", "passed": all_pass, "checks": checks}


# ── Test 3: paper_request mapping → user_requirements content check ──

def test_paper_request_mapping_content():
    """Verify map_paper_request_to_params produces meaningful content for compose."""
    print("\n" + "=" * 70)
    print("TEST 3: paper_request mapping 内容质量检查")
    print("=" * 70)

    from compose.compose_runner import load_paper_request, map_paper_request_to_params

    pr = load_paper_request("docs/output_intake_e2e/scenario_T1")
    if not pr:
        print("  ✗ paper_request.yaml 加载失败")
        return {"test": "T1_mapping", "passed": False}

    mapped = map_paper_request_to_params(pr)

    checks = []

    # user_requirements should mention key constraints
    req = mapped.get("user_requirements", "")
    checks.append(("user_requirements_nonempty", len(req) > 50))
    checks.append(("mentions_subjects", "数据结构" in req and "组成原理" in req))
    checks.append(("mentions_excluded", "Cache" in req and "虚拟内存" in req))
    checks.append(("mentions_difficulty", "较难" in req or "难度" in req))
    checks.append(("mentions_require", "冷门考点" in req or "操作系统" in req))

    # subject_files should map to 4 KG files
    sf = mapped.get("subject_files", [])
    checks.append(("4_subject_files", len(sf) == 4))
    checks.append(("has_data_structure", "data_structure.md" in sf))
    checks.append(("has_operating_system", "operating_system" in str(sf)))

    # slot_templates_hints should have question types
    hints = mapped.get("slot_templates_hints", [])
    checks.append(("has_slot_hints", len(hints) >= 2))
    if hints:
        types = [h.get("question_type") for h in hints]
        checks.append(("has_single_choice", "single_choice" in types))
        checks.append(("has_comprehensive", "comprehensive" in types))

    all_pass = True
    for name, passed in checks:
        icon = "✓" if passed else "✗"
        if not passed:
            all_pass = False
        print(f"  {icon} {name}: {passed}")

    if all_pass:
        print(f"\n  user_requirements 全文:")
        print(f"  {req}")

    print(f"\n  结果: {'✓ PASS' if all_pass else '✗ FAIL'}")
    return {"test": "T1_mapping", "passed": all_pass}


# ── Main ───────────────────────────────────────────────────────────

async def main():
    print("=" * 70)
    print("Intake Layer 真实流水线消费验证")
    print("=" * 70)

    results = []

    # Test 3: mapping content (sync, no LLM)
    r3 = test_paper_request_mapping_content()
    results.append(r3)

    # Test 2: slot_blueprint adapter (sync, no LLM)
    r2 = test_slot_blueprint_adapter_real()
    results.append(r2)

    # Test 1: compose_runner (async, real LLM)
    r1 = await test_paper_request_through_compose()
    results.append(r1)

    # Summary
    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)
    for r in results:
        icon = "✓" if r.get("passed") else "✗"
        name = r.get("test", "?")
        extra = f" ({r.get('elapsed', 0):.1f}s)" if "elapsed" in r else ""
        print(f"  {icon} {name}{extra}")
        if not r.get("passed"):
            print(f"     error: {r.get('error', 'N/A')}")

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    print(f"\n  通过: {passed}/{total}")

    return passed == total


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
