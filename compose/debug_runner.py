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
            "design": 1,
            "question": 2,
            "analysis": 2,
            "coding": 3,
            "review": 4,
            "fix": 4,
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
        "design": f"请根据以下数据设计 {slot_id} 的出题蓝图。",
        "question": f"请设计 {slot_id} 的完整题目。",
        "analysis": "请审核以下题目，检查参数一致性和难度对标。",
        "coding": "请编写完整的 Python 求解代码。",
        "review": "请全局审核题目和求解结果。",
        "fix": "请根据审核意见修复题目中的问题。优先使用 edit_file 做局部修改。",
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
