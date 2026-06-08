# EduTeacher Workbench API Layer

FastAPI-based HTTP API layer for the EduTeacher Workbench interactive question generation system.

## Overview

The API layer provides REST endpoints for:
- **Session Management**: Create, read, update, delete sessions
- **Interactive Chat**: Send messages to sessions and receive responses
- **Compose/Outline Management**: View and edit generated outlines
- **Question Generation**: Trigger generation jobs and monitor progress
- **Artifact Access**: Retrieve generated content (final questions, reports, etc.)
- **Real-time Events**: SSE streaming for live updates

## Directory Structure

```
api/
├── __init__.py          # Package initialization
├── app.py              # FastAPI application entry point
├── schemas.py          # Pydantic models for requests/responses
├── deps.py             # Dependency injection and singletons
├── event_bus.py        # Async event bus for SSE
├── persistence.py      # SQLite session storage
└── routes/             # API route modules
    ├── __init__.py
    ├── session.py      # Session CRUD endpoints
    ├── interact.py     # Main chat endpoint
    ├── compose.py      # Outline & generation endpoints
    ├── artifacts.py    # Artifact retrieval
    ├── events.py       # SSE streaming endpoint
    └── health.py       # Health check

run_api.py              # Server startup script
```

## API Endpoints

### Health
- `GET /api/health` - Health check

### Sessions
- `GET /api/sessions` - List all sessions
- `GET /api/sessions/{session_id}` - Get session details
- `DELETE /api/sessions/{session_id}` - Delete a session

### Interaction
- `POST /api/sessions/{session_id}/message` - Send a message to a session
  - Request: `{"message": "user input text"}`
  - Response: Includes response text, state, mode, blueprint_id, collected_params

### Compose/Outline
- `GET /api/sessions/{session_id}/outline` - Get current outline (blueprint)
- `PUT /api/sessions/{session_id}/outline` - Update outline
  - Request: `{"outline_md": "markdown content"}`
- `POST /api/sessions/{session_id}/generate` - Start question generation

### Artifacts
- `GET /api/runs/{run_id}/artifacts/{artifact_type}` - Get generated content
  - artifact_type: `outline`, `final`, `revision_report`, `manifest`
  - Optional `slot_id` query param for per-slot artifacts

### Events (SSE)
- `GET /api/sessions/{session_id}/events` - Server-Sent Events stream
  - Emits events: `state_change`, `generation_complete`, `generation_error`

## Running the Server

### Development
```bash
cd /zhaoshu/llm_eduated
python run_api.py
```

### Production
```bash
# Set environment variables
export EDUCATE_PROVIDER=glm5.1
export API_HOST=0.0.0.0
export API_PORT=3001

# Run with uvicorn directly
uvicorn api.app:app --host 0.0.0.0 --port 3001 --workers 4
```

### Environment Variables

- `EDUCATE_PROVIDER` - LLM provider to use (default: `api_vllm`)
  - Options: `api_vllm`, `glm5.1`, `glm4flash`, `local`, etc.
- `COMPOSER_ROUTING` - Model routing for compose mode (default: `local`)
- `API_HOST` - Server host (default: `0.0.0.0`)
- `API_PORT` - Server port (default: `3001`)

## Architecture

### Dependency Injection
The `deps.py` module provides singleton instances:
- `get_orchestrator()` - Returns the InteractiveOrchestrator
- `get_gateway()` - Returns the LLMGateway
- `get_store()` - Returns the SessionStore

### Session Persistence
Sessions are automatically persisted to SQLite (`data/sessions.db`):
- State transitions are saved after each message
- Session data includes: state, mode, collected_params, blueprint_md, generation_results

### Event Streaming
The EventBus enables real-time updates via SSE:
- Subscribe to session-specific channels
- Published events include: state changes, generation progress, errors
- 30-second keepalive for connection health

### Background Generation
Question generation runs in background tasks:
- `POST /api/sessions/{session_id}/generate` returns immediately
- Progress is reported via SSE events
- Results are persisted to session storage

## Integration with Existing Code

The API layer integrates with existing modules:

- **`interact/orchestrator.py`**: `InteractiveOrchestrator` handles user input
- **`interact/session_manager.py`**: FSM states and session lifecycle
- **`core_new/llm_gateway.py`**: Unified LLM access
- **`config.py`**: Provider configuration and settings

## Example Usage

### Start a conversation
```bash
curl -X POST http://localhost:3001/api/sessions/test-123/message \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to generate 5 questions about TCP handshake"}'
```

### Get session status
```bash
curl http://localhost:3001/api/sessions/test-123
```

### Stream events
```bash
curl -N http://localhost:3001/api/sessions/test-123/events
```

### Get outline
```bash
curl http://localhost:3001/api/sessions/test-123/outline
```

### Start generation
```bash
curl -X POST http://localhost:3001/api/sessions/test-123/generate
```

## Frontend Integration

The API is designed to work with a Vue.js frontend (served from `/static`):
- All endpoints return JSON for AJAX calls
- SSE endpoint provides real-time updates
- CORS is enabled for development

## Static Files

If a `static/` directory exists at project root, it is served at `/`:
- Built Vue.js app should be placed in `static/`
- API routes remain under `/api/*`

## Testing

Run the TestClient tests:
```bash
cd /zhaoshu/llm_eduated
python -c "
from fastapi.testclient import TestClient
from api.app import app
client = TestClient(app)
# ... test code
"
```

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200 OK` - Successful request
- `400 Bad Request` - Invalid request data or state
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

Error responses include:
```json
{
  "detail": "Error message description"
}
```
