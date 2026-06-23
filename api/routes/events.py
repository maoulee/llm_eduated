"""Server-Sent Events (SSE) endpoint for real-time session updates."""

import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.event_bus import event_bus

router = APIRouter(tags=["events"])


@router.get("/sessions/{session_id}/events")
async def session_events(request: Request, session_id: str):
    """SSE endpoint for real-time session events.

    Clients can connect to this endpoint to receive real-time updates
    about session state changes, generation progress, and errors.

    The connection stays open with 30-second keepalive messages.
    """

    async def event_generator():
        queue = event_bus.subscribe(session_id)
        try:
            while True:
                try:
                    # Wait for events with 30s timeout for keepalive
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield f": keepalive\n\n"
                    # Check if client disconnected
                    if await request.is_disconnected():
                        break
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
