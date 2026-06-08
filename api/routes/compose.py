"""Compose-specific routes for outline management and generation."""

import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from api.schemas import OutlineUpdateRequest, RetrySlotRequest
from api.deps import get_orchestrator, get_store, get_gateway
from api.event_bus import event_bus
from interact.session_manager import SessionState

router = APIRouter(tags=["compose"])


@router.get("/sessions/{session_id}/outline")
async def get_outline(session_id: str):
    """Get the current outline (blueprint) for a session."""
    orch = get_orchestrator()
    session = orch.session_manager.get_or_create(session_id)
    if not session.blueprint_md:
        raise HTTPException(404, "No outline yet")
    return PlainTextResponse(session.blueprint_md)


@router.put("/sessions/{session_id}/outline")
async def save_outline(session_id: str, body: OutlineUpdateRequest):
    """Update the outline (blueprint) for a session."""
    orch = get_orchestrator()
    session = orch.session_manager.get_or_create(session_id)
    session.blueprint_md = body.outline_md
    get_store().save(session)
    return {"ok": True}


@router.post("/sessions/{session_id}/generate")
async def start_generation(session_id: str):
    """Start the question generation process for a session.

    This endpoint triggers generation in the background and returns immediately.
    Progress is reported via SSE events on the /sessions/{session_id}/events endpoint.
    """
    orch = get_orchestrator()
    session = orch.session_manager.get_or_create(session_id)

    if session.state.value not in ("approved",):
        raise HTTPException(
            400,
            f"Session state is {session.state.value}, expected approved"
        )

    # Trigger generation in background
    asyncio.create_task(_run_generation_background(orch, session_id))

    session.state = SessionState.GENERATING
    get_store().save(session)

    return {"status": "started", "session_id": session_id}


async def _run_generation_background(orch, session_id: str):
    """Background task to run generation and publish events."""
    try:
        result = await orch.run_generation(session_id)
        session = orch.session_manager.get_or_create(session_id)
        get_store().save(session)

        event_bus.publish(session_id, {
            "type": "generation_complete",
            "results": result.get("results", []),
        })
    except Exception as e:
        session = orch.session_manager.get_or_create(session_id)
        session.state = SessionState.ERROR
        session.error_message = str(e)
        get_store().save(session)

        event_bus.publish(session_id, {
            "type": "generation_error",
            "error": str(e),
        })
