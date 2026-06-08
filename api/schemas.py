"""Pydantic schemas for API requests and responses."""

from pydantic import BaseModel
from typing import Optional, Dict, Any


class SendMessageRequest(BaseModel):
    """Request to send a message to a session."""
    message: str


class SendMessageResponse(BaseModel):
    """Response from sending a message."""
    response: str
    state: str  # FSM state name
    mode: str  # compose / knowledge_point
    blueprint_id: str = ""
    collected_params: Dict[str, Any] = {}
    error: Optional[str] = None


class SessionInfo(BaseModel):
    """Basic session information."""
    session_id: str
    state: str
    mode: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OutlineUpdateRequest(BaseModel):
    """Request to update an outline."""
    outline_md: str


class RetrySlotRequest(BaseModel):
    """Request to retry a specific generation slot."""
    slot_id: str


class SessionListResponse(BaseModel):
    """Response listing all sessions."""
    sessions: list[SessionInfo]
