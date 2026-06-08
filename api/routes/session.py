"""Session CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from api.schemas import SessionInfo, SessionListResponse
from api.deps import get_store

router = APIRouter(tags=["session"])


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    """List all sessions."""
    store = get_store()
    return SessionListResponse(sessions=[
        SessionInfo(**s) for s in store.list_sessions()
    ])


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """Get a specific session by ID."""
    store = get_store()
    session = store.load(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return SessionInfo(
        session_id=session.session_id,
        state=session.state.value,
        mode=session.mode,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    store = get_store()
    store.delete(session_id)
    return {"ok": True}
