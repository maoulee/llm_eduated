#!/usr/bin/env python3
"""Resume a pipeline run from a specific stage using saved debug dumps.

Usage:
    python resume_pipeline.py --debug-dir debug/Q43_20260531_132942 --resume-from final_review --debug
    python resume_pipeline.py --debug-dir debug/Q43_20260531_132942 --resume-from solve --slot-id Q43
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core_new.agents.unified_pipeline import UnifiedQuestionPipeline
from core_new.pipeline_resume import load_debug_state, rebuild_blackboard_state


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Resume pipeline from debug dump")
    parser.add_argument("--debug-dir", required=True, help="Path to debug dump directory")
    parser.add_argument("--resume-from", required=True,
                        choices=["design", "options", "gate", "solve", "verify",
                                 "format", "rubric", "final_review", "final_fixer"],
                        help="Stage to resume from")
    parser.add_argument("--slot-id", default=None, help="Slot ID (auto-detected if omitted)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output for resumed run")
    parser.add_argument("--max-rounds", type=int, default=1, help="Max revision rounds")
    args = parser.parse_args()

    # Auto-detect slot_id from directory contents
    if not args.slot_id:
        for fname in os.listdir(args.debug_dir):
            if fname.endswith("_summary.json"):
                args.slot_id = fname.split("_")[0]
                break
        if not args.slot_id:
            for fname in os.listdir(args.debug_dir):
                if "_design_" in fname:
                    args.slot_id = fname.split("_")[0]
                    break

    if not args.slot_id:
        logger.error("Cannot detect slot_id from debug dir. Use --slot-id.")
        sys.exit(1)

    logger.info("Resuming pipeline: slot=%s from=%s dir=%s", args.slot_id, args.resume_from, args.debug_dir)

    # Load state from debug dumps
    state = load_debug_state(args.debug_dir, args.slot_id, args.resume_from)
    if not state:
        logger.error("No debug state found")
        sys.exit(1)

    # Determine question type from design dump
    design = state.get("design", {})
    is_sc = bool(design.get("options")) or not design.get("sub_questions")

    resume_state = rebuild_blackboard_state(state, is_sc)

    # Minimal blueprint
    slot_blueprint = {
        "slot_id": args.slot_id,
        "question_type": "single_choice" if is_sc else "comprehensive",
    }
    experience_card = ""

    # New debug dir for resume output
    new_debug_dir = None
    if args.debug:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_debug_dir = os.path.join("debug", f"{args.slot_id}_resume_{args.resume_from}_{ts}")
        os.makedirs(new_debug_dir, exist_ok=True)
        logger.info("Resume debug output: %s", new_debug_dir)

    from core_new.llm_gateway import get_gateway
    gateway = get_gateway()

    pipeline = UnifiedQuestionPipeline(
        max_revision_rounds=args.max_rounds,
        debug_dir=new_debug_dir,
    )

    result = await pipeline.run(
        slot_blueprint=slot_blueprint,
        experience_card=experience_card,
        gateway=gateway,
        resume_from=args.resume_from,
        resume_state=resume_state,
    )

    fq = result.final_question
    print(f"\n{'='*60}")
    print(f"Pipeline result: type={result.pipeline_type}, time={result.generation_time_s}s")
    print(f"Export status: {fq.get('export_status', 'unknown')}")
    if fq.get("block_reasons"):
        print(f"Block reasons: {fq['block_reasons']}")
    print(f"Stem preview: {fq.get('stem', '')[:100]}...")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
