"""Quick test: run Q43 full pipeline with GLM (no WebGPT)."""

import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-30s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_glm")


async def main():
    # Force ALL routing to GLM (disable local vLLM)
    import core_new.provider_router as pr
    import time as _time
    pr._local_available = False
    pr._last_health_check = _time.monotonic()  # Prevent TTL re-check
    logger.info("Forced local provider OFF — all agents will use GLM")

    # 1. Load data
    with open("data/slot_templates.json") as f:
        templates_data = json.load(f)
    slot_template = templates_data["templates"]["Q43"]

    with open("data/slot_experiences/Q43_experience.md") as f:
        experience_card = f.read()

    # Build a realistic blueprint (like PaperComposer would produce)
    blueprint = {
        "slot_id": "Q43",
        "target_subject": "计算机组成原理",
        "target_family": "存储系统与总线性能",
        "primary_target_name": "Cache缺失代价与总线突发传输综合计算",
        "target_depth": "mechanism",
        "primary_paper_role": "difficulty_separator",
        "target_difficulty": 4,
        "difficulty_profile": {
            "knowledge_depth": 4,
            "reasoning_steps": 5,
            "calculation_load": 4,
        },
        "sub_questions": 3,
        "answer_format": "解答过程+最终结果",
        "must_include": "Cache缺失处理, 总线突发传输, CPU性能影响",
        "must_avoid": "纯概念辨析, 超大计算量",
        "question_type": "comprehensive",
        "typical_score": 10,
    }
    blueprint.update(slot_template)

    logger.info("Blueprint: %s", json.dumps(blueprint, ensure_ascii=False, indent=2)[:300])
    logger.info("Experience card: %d chars", len(experience_card))

    # 2. Create GLM gateway directly (bypass provider router)
    from core_new.llm_gateway import get_gateway
    glm_gw = get_gateway("glm5.1")
    logger.info("Gateway: glm5.1, model=%s", glm_gw.model_name if hasattr(glm_gw, 'model_name') else '?')

    # 3. Run pipeline
    from core_new.agents.unified_pipeline import UnifiedQuestionPipeline

    debug_dir = f"debug/Q43_glm_{time.strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(debug_dir, exist_ok=True)
    # Save blueprint for reference
    with open(f"{debug_dir}/Q43_blueprint.json", "w") as f:
        json.dump(blueprint, f, ensure_ascii=False, indent=2)

    pipeline = UnifiedQuestionPipeline(
        max_revision_rounds=1,
        enable_stem_gate=False,
        use_runtime_sc_design=False,
        debug_dir=debug_dir,
    )

    logger.info("Starting pipeline run for Q43...")
    t0 = time.monotonic()
    result = await pipeline.run(blueprint, experience_card, glm_gw)
    elapsed = time.monotonic() - t0

    # 4. Output results
    print("\n" + "=" * 70)
    print(f"PIPELINE RESULT ({elapsed:.1f}s)")
    print("=" * 70)

    fq = result.final_question or {}
    print(f"\nStem: {str(fq.get('stem', ''))[:200]}...")
    print(f"Sub-questions: {json.dumps(fq.get('sub_questions', []), ensure_ascii=False)[:200]}")
    print(f"Pipeline type: {result.pipeline_type}")
    print(f"Review status: {result.review.get('status', '?')}")
    print(f"Review score: {result.review.get('score', '?')}")
    print(f"Generation time: {result.generation_time_s:.1f}s")

    # Save full result
    summary = {
        "slot_id": "Q43",
        "provider": "glm5.1",
        "elapsed_s": round(elapsed, 1),
        "pipeline_type": result.pipeline_type,
        "stem": str(fq.get("stem", ""))[:500],
        "sub_questions": fq.get("sub_questions", []),
        "review_status": result.review.get("status"),
        "review_score": result.review.get("score"),
        "generation_time_s": result.generation_time_s,
    }
    with open(f"{debug_dir}/Q43_summary.json", "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\nDebug dir: {debug_dir}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
