"""Main interaction endpoint for sending messages to sessions."""

from fastapi import APIRouter, Depends
from api.schemas import SendMessageRequest, SendMessageResponse
from api.deps import get_orchestrator, get_store
from api.event_bus import event_bus
from interact.session_manager import SessionState

router = APIRouter(tags=["interact"])


@router.post("/sessions/{session_id}/message", response_model=SendMessageResponse)
async def send_message(session_id: str, body: SendMessageRequest):
    """Send a message to a session and get a response.

    This endpoint processes user input through the InteractiveOrchestrator,
    persists the session state, and publishes events for SSE subscribers.
    """
    orch = get_orchestrator()
    store = get_store()

    response_text = await orch.handle_input(session_id, body.message)
    session = orch.session_manager.get_or_create(session_id)

    # Persist session state after each message
    store.save(session)

    # Publish state change event
    event_bus.publish(session_id, {
        "type": "state_change",
        "state": session.state.value,
        "mode": session.mode,
    })

    return SendMessageResponse(
        response=response_text,
        state=session.state.value,
        mode=session.mode,
        blueprint_id=session.blueprint_id,
        collected_params=session.collected_params,
        error=session.error_message if session.state == SessionState.ERROR else None,
    )
