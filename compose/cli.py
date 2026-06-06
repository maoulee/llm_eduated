"""CLI entry point and full-pipeline orchestration."""

import asyncio
import json
import os
import re
import sys

from . import compose_runner, debug_runner, generate_runner


async def run_composition(
    gateway,
    slot_templates: dict,
    experience_cards: dict,
    user_requirements: str,
    slot_ids: list = None,
    output_dir: str = "docs",
    model_routing: dict[str, str] | None = None,
) -> dict:
    """Run the full composition pipeline (compose + generate).

    Backward-compatible entry point — calls run_compose() then run_generate().
    """
    compose_result = await compose_runner.run_compose(
        gateway, slot_templates, experience_cards, user_requirements,
        slot_ids=slot_ids, output_dir=output_dir, model_routing=model_routing,
    )
    if compose_result.get("status") != "ok":
        return compose_result

    return await generate_runner.run_generate(
        gateway,
        compose_dir=compose_result["compose_dir"],
        output_dir=output_dir,
        model_routing=model_routing,
        slot_filter=slot_ids,
        run_id=compose_result.get("run_id"),
    )


async def main():
    import argparse
    from core_new.provider_router import get_routed_gateway as _rgw

    routing_choices = ["all_local", "all_remote", "mixed", "glm_gen_qwen_review", "qwen_gpt_core", "hybrid"]

    parser = argparse.ArgumentParser(description="408 exam paper composition (doc pipeline)")
    subparsers = parser.add_subparsers(dest="command")

    # ── Default (no subcommand): full pipeline ──
    parser.add_argument("--slots", nargs="+", help="Specific slots (e.g., Q12 Q13)")
    parser.add_argument("--slots-dir", help="Directory containing slot MD files")
    parser.add_argument("--requirements", default="出一套标准难度的408模拟卷（计算机组成原理选择题部分），难度分布均匀，覆盖主要知识点")
    parser.add_argument("--output-dir", default="docs", help="Output directory")
    parser.add_argument("--routing", choices=routing_choices, default="all_local")
    parser.add_argument("--debug", action="store_true", default=False)

    # ── compose subcommand ──
    sub_compose = subparsers.add_parser("compose", help="组卷 only (compose + assemble, save to compose/)")
    sub_compose.add_argument("--slots", nargs="+", help="Specific slots")
    sub_compose.add_argument("--slots-dir", help="Directory containing slot MD files")
    sub_compose.add_argument("--requirements", default="出一套标准难度的408模拟卷（计算机组成原理选择题部分），难度分布均匀，覆盖主要知识点")
    sub_compose.add_argument("--output-dir", default="docs")
    sub_compose.add_argument("--routing", choices=routing_choices, default="all_local")

    # ── generate subcommand ──
    sub_gen = subparsers.add_parser("generate", help="出题 only (load compose artifacts)")
    sub_gen.add_argument("--compose-dir", required=True, help="Directory with *_assembled.md from compose")
    sub_gen.add_argument("--slots", nargs="+", help="Only generate these slots")
    sub_gen.add_argument("--output-dir", default="docs")
    sub_gen.add_argument("--routing", choices=routing_choices, default="all_local")
    sub_gen.add_argument("--resume-from", type=int, default=1, choices=[1, 2, 3, 4, 5],
                         help="Resume from pipeline layer (1=full, 2=skip outline, 3=skip question+review, 4=skip solve, 5=skip final review)")
    sub_gen.add_argument("--run-id", default=None,
                         help="Run ID for workspace isolation (default: read from compose manifest)")

    # ── debug subcommand ──
    sub_debug = subparsers.add_parser("debug", help="Run a single agent with workspace files")
    sub_debug.add_argument("--slot", required=True, help="Slot ID (e.g. Q12)")
    sub_debug.add_argument("--agent", required=True,
                           choices=["outline", "question_sc", "question_comp", "review", "solve", "final_review"])
    sub_debug.add_argument("--workspace", default="docs/workspace")
    sub_debug.add_argument("--routing", choices=routing_choices, default="all_local")
    sub_debug.add_argument("--run-id", default=None,
                           help="Run ID for workspace isolation (default: latest run)")
    sub_debug.add_argument("--inject", nargs="*", metavar="KEY=FILE",
                           help="Extra file injections, e.g. '蓝图=docs/workspace/Q12/blueprint.md'")

    # ── revise subcommand ──
    sub_revise = subparsers.add_parser("revise", help="修订大纲（基于教师批注/字段变更）")
    sub_revise.add_argument("--base", default=None,
                           help="修订前大纲路径（默认: docs/compose/outline.md）")
    sub_revise.add_argument("--annotated", default=None,
                           help="教师批注后大纲路径（默认: 与 --base 相同，即原地检测批注）")
    sub_revise.add_argument("--output-dir", default="docs")
    sub_revise.add_argument("--routing", choices=routing_choices, default="all_local")

    args = parser.parse_args()

    # ── Shared setup ──
    from core_new.provider_router import set_routing_profile
    model_routing = set_routing_profile(args.routing)
    print(f"[Routing] Profile: {args.routing}")

    # ── debug subcommand ──
    if args.command == "debug":
        await debug_runner.run_debug(args, model_routing)
        return

    # ── revise subcommand ──
    if args.command == "revise":
        base_path = args.base or os.path.join(args.output_dir, "compose", "outline.md")
        if not os.path.exists(base_path):
            print(f"Outline not found: {base_path}")
            print("Run 'compose compose' first to generate the outline.")
            return

        # Load templates and experience cards for re-assembly
        tpl_path = "data/slot_templates.json"
        if not os.path.exists(tpl_path):
            print(f"Templates not found: {tpl_path}")
            return
        with open(tpl_path, encoding="utf-8") as f:
            tpl_data = json.load(f)
        templates = tpl_data.get("templates", {})

        exp_cards = {}
        exp_dir = "data/slot_experiences"
        if os.path.isdir(exp_dir):
            for fname in os.listdir(exp_dir):
                if fname.endswith("_experience.md"):
                    slot_id = fname.replace("_experience.md", "")
                    with open(os.path.join(exp_dir, fname), encoding="utf-8") as f:
                        exp_cards[slot_id] = f.read()

        gateway = _rgw("paper_composer")
        result = await compose_runner.revise_outline(
            gateway, templates, exp_cards,
            base_outline_path=base_path,
            annotated_outline_path=args.annotated,
            output_dir=args.output_dir,
            model_routing=model_routing,
        )

        if result.get("status") == "ok":
            print(f"\n✅ 修订完成，已更新: {', '.join(result.get('changed_slots', []))}")
        elif result.get("status") == "unchanged":
            print("\n未检测到变更，大纲未修改。")
        else:
            print(f"\n❌ 修订失败: {result}")
        return

    # ── generate subcommand ──
    if args.command == "generate":
        gateway = _rgw("paper_composer")
        await generate_runner.run_generate(
            gateway,
            compose_dir=args.compose_dir,
            output_dir=args.output_dir,
            model_routing=model_routing,
            slot_filter=args.slots,
            resume_from=args.resume_from,
            run_id=args.run_id,
        )
        return

    # ── compose or full pipeline ──
    # Slot discovery
    discovered_slot_ids = None
    if args.slots_dir:
        if not os.path.isdir(args.slots_dir):
            print(f"Slots directory not found: {args.slots_dir}")
            return
        discovered_slot_ids = sorted([
            m.group(1) for f in os.listdir(args.slots_dir)
            if (m := re.match(r"(Q\d+)_slot\.md$", f))
        ])
        print(f"[Slots] Discovered {len(discovered_slot_ids)} slots from {args.slots_dir}: {discovered_slot_ids}")
        if args.slots:
            discovered_slot_ids = [s for s in discovered_slot_ids if s in args.slots]
            print(f"[Slots] Filtered to: {discovered_slot_ids}")
    slot_ids = discovered_slot_ids or args.slots

    tpl_path = "data/slot_templates.json"
    if not os.path.exists(tpl_path):
        print(f"Templates not found: {tpl_path}")
        print("Run slot_extractor.py first.")
        return

    with open(tpl_path, encoding="utf-8") as f:
        tpl_data = json.load(f)
    templates = tpl_data.get("templates", {})

    exp_cards = {}
    exp_dir = "data/slot_experiences"
    if os.path.isdir(exp_dir):
        for fname in os.listdir(exp_dir):
            if fname.endswith("_experience.md"):
                slot_id = fname.replace("_experience.md", "")
                with open(os.path.join(exp_dir, fname), encoding="utf-8") as f:
                    exp_cards[slot_id] = f.read()

    print(f"Loaded {len(templates)} templates, {len(exp_cards)} experience cards")

    gateway = _rgw("paper_composer")

    if args.command == "compose":
        await compose_runner.run_compose(
            gateway, templates, exp_cards, args.requirements,
            slot_ids=slot_ids, output_dir=args.output_dir, model_routing=model_routing,
        )
    else:
        # No subcommand: full pipeline
        await run_composition(
            gateway, templates, exp_cards, args.requirements,
            slot_ids=slot_ids, output_dir=args.output_dir, model_routing=model_routing,
        )
