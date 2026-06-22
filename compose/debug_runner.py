"""Debug runner — single-agent debugging with workspace file injection."""

import os
from pathlib import Path


def _resolve_debug_workspace(args) -> Path:
    """Resolve workspace path, accounting for run_id if provided."""
    base = Path(args.workspace)

    if args.run_id:
        return base / args.run_id

    # Prefer run-scoped dirs (with ISO timestamps containing 'T') over legacy flat layout
    if base.is_dir():
        run_dirs = sorted(d for d in base.iterdir() if d.is_dir() and 'T' in d.name)
        if run_dirs:
            latest = run_dirs[-1]
            if (latest / args.slot).exists():
                return latest

    return base


async def run_debug(args, model_routing):
    """Run a single agent with workspace files for debugging."""
    from core_new.provider_router import get_routed_gateway as _rgw

    slot_id = args.slot
    role = args.agent
    workspace_root = _resolve_debug_workspace(args)
    workspace = workspace_root / slot_id

    if not workspace.exists():
        print(f"Workspace not found: {workspace}")
        return

    print(f"[Debug] slot={slot_id} agent={role} workspace={workspace}")

    # Resolve inject files from workspace via ContextRegistry
    from core_new.doc_pipeline.config import PIPELINE_CONFIG
    registry = PIPELINE_CONFIG.context_registry

    inject_files = {}
    if registry:
        role_phase = {
            "outline": 1,
            "question_sc": 2,
            "question_comp": 2,
            "review": 3,
            "solve": 4,
            "final_review": 5,
        }.get(role, 2)
        resolved = await registry.resolve_for_role(role, workspace_root, slot_id, phase=role_phase)
        inject_files.update(resolved)

    # Apply user --inject overrides
    if args.inject:
        for item in args.inject:
            if "=" in item:
                key, filepath = item.split("=", 1)
                inject_files[key.strip()] = filepath.strip()

    print(f"  Inject: {list(inject_files.keys())}")

    # Build a minimal task prompt
    task_prompts = {
        "outline": f"请根据以下数据设计 {slot_id} 的出题规划。",
        "question_sc": f"请设计 {slot_id} 的选择题题目。",
        "question_comp": f"请设计 {slot_id} 的综合应用题题目。",
        "review": "请审核以下题目的设计质量（此阶段无答案，不评估答案正确性）。",
        "solve": "请独立求解以下题目。先判断是概念题还是数值题，选择对应的求解策略。",
        "final_review": "请终审题目和求解结果的整体质量，判定 pass/expression_fix/question_error/solution_error。",
    }

    task = task_prompts.get(role, f"请处理 {slot_id}。")

    from core_new.doc_pipeline.scheduler import DocScheduler
    scheduler = DocScheduler(
        gateway=_rgw(role),
        workspace=workspace_root,
        max_tokens=20000,
        model_routing=model_routing,
    )

    try:
        output = await scheduler.run_agent(
            role, task,
            slot_id=slot_id,
            inject_files=inject_files if inject_files else None,
        )
        print(f"\n[{role}] Output:\n{output[:2000]}")
    finally:
        await scheduler.cleanup_webgpt(slot_id)
