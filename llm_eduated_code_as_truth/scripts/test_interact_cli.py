"""Interactive CLI for testing the interact agent turn-by-turn.

Each invocation runs ONE conversation turn. Session state (messages, read_cache,
turn tracking) is persisted as JSON in workspace so context survives across calls.

Usage:
  # Turn 1: teacher sends request
  python scripts/test_interact_cli.py api_vllm sim_test --msg "出一道Cache映射的选择题，难度中等"

  # (read and edit the draft file manually)
  # (mark [✓]/[✗], add annotations)

  # Turn 2: teacher confirms
  python scripts/test_interact_cli.py api_vllm sim_test --msg "确认写入文件"

  # Turn 3: teacher edits and sends back
  python scripts/test_interact_cli.py api_vllm sim_test --msg "我已完成标注，请读取编辑后的文档"

  # Reset a session
  python scripts/test_interact_cli.py api_vllm sim_test --reset

Options:
  --msg TEXT       Teacher message
  --workspace DIR  Workspace directory (default: docs/output_interact_cli/workspace)
  --show-files     List session files after turn
  --show-draft     Show draft file content after turn
  --reset          Delete session state and start fresh
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core_new.doc_pipeline.scheduler import DocScheduler, InteractSession
from core_new.llm_gateway import get_gateway

SESSION_STATE_FILE = "_session_state.json"


def _session_path(workspace: Path, session_id: str) -> Path:
    return workspace / session_id / SESSION_STATE_FILE


def _save_session(scheduler: DocScheduler, session_id: str):
    """Persist interact session state to workspace."""
    session = scheduler._interact_sessions.get(session_id)
    if not session:
        return
    state = {
        "session_id": session.session_id,
        "role": session.role,
        "status": session.status,
        "scenario": session.scenario,
        "files_written": session.files_written,
        "messages": session.messages,
        "read_cache": session.read_cache,
        "turn_count": session.turn_count,
        "last_draft_write_turn": session.last_draft_write_turn,
    }
    path = _session_path(scheduler.workspace, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_session(scheduler: DocScheduler, session_id: str):
    """Restore interact session state from workspace."""
    path = _session_path(scheduler.workspace, session_id)
    if not path.exists():
        return
    state = json.loads(path.read_text(encoding="utf-8"))
    session = InteractSession(
        session_id=state["session_id"],
        role=state.get("role", "interact"),
        status=state.get("status", "collecting"),
        scenario=state.get("scenario", "unknown"),
        files_written=state.get("files_written", []),
        messages=state.get("messages", []),
        read_cache=state.get("read_cache", {}),
        turn_count=state.get("turn_count", 0),
        last_draft_write_turn=state.get("last_draft_write_turn", 0),
    )
    scheduler._interact_sessions[session_id] = session


async def run_single_turn(provider: str, session_id: str, msg: str,
                          workspace: Path, show_files: bool, show_draft: bool,
                          enable_thinking: bool = False):
    gateway = get_gateway(provider)
    workspace.mkdir(parents=True, exist_ok=True)

    scheduler = DocScheduler(
        gateway,
        workspace=workspace,
        enable_thinking=enable_thinking,
        model_routing={"_default": provider},
    )

    # Restore session state from previous turns
    _load_session(scheduler, session_id)

    print(f"\n{'='*70}")
    print(f"[教师 → 智能体] session={session_id}")
    turn_num = scheduler._interact_sessions[session_id].turn_count + 1 if session_id in scheduler._interact_sessions else 1
    print(f"Turn #{turn_num}")
    print(f"消息: {msg}")
    print("=" * 70)

    t0 = time.monotonic()
    result = await scheduler.run_conversation_turn(
        session_id=session_id,
        teacher_message=msg,
        role="interact",
    )
    elapsed = time.monotonic() - t0

    # Persist session state after each turn
    _save_session(scheduler, session_id)

    print(f"\n[响应 | {elapsed:.1f}s] status={result['status']}")
    print(f"files_written: {result['files_written']}")

    if result["response_text"]:
        print(f"\n--- 智能体回复 ---")
        print(result["response_text"][:3000])
        if len(result["response_text"]) > 3000:
            print(f"... (truncated, {len(result['response_text'])} chars total)")
        print("--- 回复结束 ---")

    # Show session files
    if show_files or show_draft:
        session_ws = workspace / session_id
        if session_ws.exists():
            print(f"\n--- 会话文件 ({session_ws}) ---")
            for f in sorted(session_ws.rglob("*")):
                if f.is_file() and f.name != SESSION_STATE_FILE:
                    rel = f.relative_to(session_ws)
                    size = f.stat().st_size
                    print(f"  {rel} ({size} bytes)")

    # Show draft content
    if show_draft:
        session_ws = workspace / session_id
        for candidate in ["compose/interact_draft.md", "interact_draft.md",
                          "interact_response.md"]:
            p = session_ws / candidate
            if p.exists():
                content = p.read_text(encoding="utf-8")
                print(f"\n--- 草案文件: {candidate} ({len(content)} chars) ---")
                print(content[:5000])
                if len(content) > 5000:
                    print(f"... (truncated)")
                print("--- 草案结束 ---")
                break

    # Show yaml files
    session_ws = workspace / session_id
    for yaml_name in ["slot_blueprint.yaml", "paper_request.yaml",
                      "retrieval_query.yaml"]:
        p = session_ws / yaml_name
        if p.exists():
            content = p.read_text(encoding="utf-8")
            print(f"\n--- 交接文档: {yaml_name} ---")
            print(content)
            print("--- YAML 结束 ---")


def main():
    parser = argparse.ArgumentParser(description="Interact agent CLI (one turn per invocation)")
    parser.add_argument("provider", help="LLM provider name (e.g. api_vllm)")
    parser.add_argument("session_id", help="Session ID (persisted across turns)")
    parser.add_argument("--msg", help="Teacher message")
    parser.add_argument("--workspace", default="docs/output_interact_cli/workspace",
                        help="Workspace directory")
    parser.add_argument("--show-files", action="store_true", help="List session files after turn")
    parser.add_argument("--show-draft", action="store_true", help="Show draft content after turn")
    parser.add_argument("--reset", action="store_true", help="Delete session state and start fresh")
    parser.add_argument("--thinking", action="store_true", help="Enable LLM thinking mode")
    args = parser.parse_args()

    workspace = Path(args.workspace)

    if args.reset:
        state_path = _session_path(workspace, args.session_id)
        if state_path.exists():
            state_path.unlink()
            print(f"Session state deleted: {state_path}")
        else:
            print("No session state found.")
        return

    if not args.msg:
        parser.error("--msg is required (unless using --reset)")

    asyncio.run(run_single_turn(
        args.provider,
        args.session_id,
        args.msg,
        workspace,
        args.show_files,
        args.show_draft,
        args.thinking,
    ))


if __name__ == "__main__":
    main()
