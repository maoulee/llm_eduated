"""V2 interact API routes.

Endpoints for session-based teacher-agent interaction with draft
annotation and result retrieval.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from api.schemas_interact_v2 import (
    AnnotationResponse,
    AnnotationSubmission,
    DisplayResult,
    DraftData,
    InteractSessionCreate,
    InteractSessionInfo,
    InteractTurnRequest,
    InteractTurnResponse,
    QuestionAnnotationRequest,
    QuestionAnnotationResponse,
)
from api.services.display_result_service import DisplayResultService
from api.services.interact_v2_service import InteractV2Service

router = APIRouter(prefix="/v2/interact", tags=["interact-v2"])

_service = InteractV2Service()
_display_service = DisplayResultService(_service)


def _status_for_value_error(exc: ValueError) -> int:
    """Map service validation failures to stable HTTP status codes."""
    msg = str(exc)
    if msg.startswith("Session ") and msg.endswith(" not found"):
        return 404
    return 400


@router.post("/sessions", response_model=InteractSessionInfo)
async def create_session(body: InteractSessionCreate):
    """Create a new interact session."""
    return _service.create_session(
        body.provider,
        body.thinking,
        body.ui_mode,
        user_id=body.user_id,
    )


@router.post("/sessions/{session_id}/turn", response_model=InteractTurnResponse)
async def send_turn(session_id: str, body: InteractTurnRequest):
    """Send a teacher message and get agent response."""
    try:
        return await _service.send_turn(session_id, body.message)
    except ValueError as e:
        raise HTTPException(status_code=_status_for_value_error(e), detail=str(e))


@router.get("/sessions/{session_id}/draft", response_model=DraftData)
async def get_draft(session_id: str):
    """Get the latest parsed draft for a session."""
    try:
        draft = _service.get_draft(session_id)
    except ValueError as e:
        raise HTTPException(status_code=_status_for_value_error(e), detail=str(e))
    if not draft:
        raise HTTPException(404, "No draft available")
    return draft


@router.post("/sessions/{session_id}/annotate", response_model=AnnotationResponse)
async def submit_annotation(session_id: str, body: AnnotationSubmission):
    """Submit pruning annotation for the current draft."""
    try:
        ok = _service.submit_annotation(session_id, body)
    except ValueError as e:
        raise HTTPException(status_code=_status_for_value_error(e), detail=str(e))
    if not ok:
        raise HTTPException(404, "No draft to annotate")
    return AnnotationResponse(ok=True)


@router.get("/sessions/{session_id}/result")
async def get_result(session_id: str):
    """Get the parsed YAML result for a session."""
    try:
        result = _service.get_result(session_id)
    except ValueError as e:
        raise HTTPException(status_code=_status_for_value_error(e), detail=str(e))
    if not result:
        raise HTTPException(404, "No result available")
    return result


@router.get("/sessions/{session_id}/display-result", response_model=DisplayResult)
async def get_display_result(session_id: str):
    """Get teacher-facing generated question results for a session."""
    try:
        return _display_service.get_display_result(session_id)
    except ValueError as e:
        raise HTTPException(status_code=_status_for_value_error(e), detail=str(e))


@router.get("/sessions/{session_id}/pipeline-progress")
async def get_pipeline_progress(session_id: str):
    """Get real-time pipeline generation progress."""
    try:
        progress = _service.get_pipeline_progress(session_id)
    except ValueError as e:
        raise HTTPException(status_code=_status_for_value_error(e), detail=str(e))
    if not progress:
        return {"status": "none", "message": "Pipeline not started."}
    return progress


@router.get("/sessions/{session_id}/paper.md")
async def get_paper_markdown(session_id: str):
    """Download the latest teacher-facing paper markdown."""
    try:
        markdown = _display_service.get_paper_markdown(session_id)
    except ValueError as e:
        raise HTTPException(status_code=_status_for_value_error(e), detail=str(e))
    if not markdown:
        raise HTTPException(404, "No paper markdown available")
    return PlainTextResponse(
        markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="paper_with_answers.md"'},
    )


@router.post(
    "/sessions/{session_id}/questions/{slot_id}/annotation",
    response_model=QuestionAnnotationResponse,
)
async def submit_question_annotation(
    session_id: str,
    slot_id: str,
    body: QuestionAnnotationRequest,
):
    """Save a teacher annotation for one generated question."""
    try:
        return _display_service.save_question_annotation(session_id, slot_id, body)
    except ValueError as e:
        raise HTTPException(status_code=_status_for_value_error(e), detail=str(e))


@router.get("/sessions", response_model=list[InteractSessionInfo])
async def list_sessions(user_id: str | None = Query(default=None)):
    """List all sessions."""
    return _service.list_sessions(user_id=user_id)


@router.get("/sessions/{session_id}", response_model=InteractSessionInfo)
async def get_session(session_id: str):
    """Get session info."""
    try:
        info = _service.get_session_info(session_id)
    except ValueError as e:
        raise HTTPException(status_code=_status_for_value_error(e), detail=str(e))
    if not info:
        raise HTTPException(404, f"Session {session_id} not found")
    return info


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """Get reconstructed chat history from workspace files."""
    try:
        history = _service.get_session_history(session_id)
    except ValueError as e:
        raise HTTPException(status_code=_status_for_value_error(e), detail=str(e))
    return history


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its workspace."""
    try:
        _service.delete_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=_status_for_value_error(e), detail=str(e))
    return {"ok": True, "message": f"Session {session_id} deleted"}
