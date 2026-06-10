"""V2 interact API routes.

Endpoints for session-based teacher-agent interaction with draft
annotation and result retrieval.
"""

from fastapi import APIRouter, HTTPException

from api.schemas.interact_v2 import (
    AnnotationResponse,
    AnnotationSubmission,
    DraftData,
    InteractSessionCreate,
    InteractSessionInfo,
    InteractTurnRequest,
    InteractTurnResponse,
)
from api.services.interact_v2_service import InteractV2Service

router = APIRouter(prefix="/v2/interact", tags=["interact-v2"])

_service = InteractV2Service()


@router.post("/sessions", response_model=InteractSessionInfo)
async def create_session(body: InteractSessionCreate):
    """Create a new interact session."""
    return _service.create_session(body.provider, body.thinking, body.ui_mode)


@router.post("/sessions/{session_id}/turn", response_model=InteractTurnResponse)
async def send_turn(session_id: str, body: InteractTurnRequest):
    """Send a teacher message and get agent response."""
    try:
        return await _service.send_turn(session_id, body.message)
    except ValueError as e:
        raise HTTPException(status_code=400 if "Invalid" in str(e) else 404, detail=str(e))


@router.get("/sessions/{session_id}/draft", response_model=DraftData)
async def get_draft(session_id: str):
    """Get the latest parsed draft for a session."""
    draft = _service.get_draft(session_id)
    if not draft:
        raise HTTPException(404, "No draft available")
    return draft


@router.post("/sessions/{session_id}/annotate", response_model=AnnotationResponse)
async def submit_annotation(session_id: str, body: AnnotationSubmission):
    """Submit pruning annotation for the current draft."""
    try:
        ok = _service.submit_annotation(session_id, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(404, "No draft to annotate")
    return AnnotationResponse(ok=True)


@router.get("/sessions/{session_id}/result")
async def get_result(session_id: str):
    """Get the parsed YAML result for a session."""
    result = _service.get_result(session_id)
    if not result:
        raise HTTPException(404, "No result available")
    return result


@router.get("/sessions", response_model=list[InteractSessionInfo])
async def list_sessions():
    """List all sessions."""
    return _service.list_sessions()


@router.get("/sessions/{session_id}", response_model=InteractSessionInfo)
async def get_session(session_id: str):
    """Get session info."""
    info = _service.get_session_info(session_id)
    if not info:
        raise HTTPException(404, f"Session {session_id} not found")
    return info
