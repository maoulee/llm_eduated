"""WebGPT delegation client — per-slot GPT conversation manager."""

from __future__ import annotations

import asyncio
import os
from typing import Dict

import httpx


DEFAULT_WEBGPT_BASE_URL = "http://localhost:3000"
DEFAULT_WEBGPT_MODEL = "gpt-thinking"
DEFAULT_WEBGPT_MAX_TOKENS = 12000
DEFAULT_WEBGPT_TIMEOUT_S = 180.0


class WebGPTClient:
    """Manages per-slot GPT conversations via WebGPT gateway.

    Sessions keyed by slot_id — one GPT conversation per slot pipeline run.
    All steps within a slot share the same session for incremental context.

    Uses per-session locking: each session key has its own lock to allow
    parallel requests across different slots while serializing requests
    within the same slot.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        model: str = DEFAULT_WEBGPT_MODEL,
        max_tokens: int = DEFAULT_WEBGPT_MAX_TOKENS,
        timeout_s: float = DEFAULT_WEBGPT_TIMEOUT_S,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model.strip() or DEFAULT_WEBGPT_MODEL
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s
        self._sessions: Dict[str, str] = {}  # slot_id → conversation_url
        self._http: httpx.AsyncClient | None = None
        self._locks: Dict[str, asyncio.Lock] = {}  # Per-session locks
        self._lock_lock = asyncio.Lock()  # Lock for accessing _locks dict
        self._available: bool | None = None

    def _get_http(self) -> httpx.AsyncClient:
        """Lazy init httpx client with auth headers."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=httpx.Timeout(self.timeout_s),
            )
        return self._http

    async def _get_lock(self, slot_id: str) -> asyncio.Lock:
        """Get or create a lock for the given session key."""
        async with self._lock_lock:
            if slot_id not in self._locks:
                self._locks[slot_id] = asyncio.Lock()
            return self._locks[slot_id]

    async def health_check(self) -> bool:
        """GET /v1/models — return True if 200."""
        try:
            http = self._get_http()
            resp = await http.get(f"{self.base_url}/v1/models")
            ok = resp.status_code == 200
            self._available = ok
            return ok
        except httpx.HTTPError:
            self._available = False
            return False

    async def delegate(
        self,
        agent_name: str,
        slot_id: str,
        system_prompt: str,
        content: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """POST /v1/chat/completions with conversation continuity.

        Session key = slot_id — all steps within a slot share one conversation.
        If no existing session: include system_prompt in messages (first call).
        If session exists: pass conversation_url, only send user message (incremental).
        Store new conversation_url from response.
        Return response content text.

        Uses per-session locking: only requests for the same slot_id are serialized.
        Different slots can proceed in parallel.
        """
        lock = await self._get_lock(slot_id)
        async with lock:
            existing_url = self._sessions.get(slot_id)

            payload: dict = {
                "model": self._resolve_model(agent_name, model),
                "stream": False,
                "max_tokens": self._resolve_max_tokens(agent_name, max_tokens),
            }
            messages: list[dict[str, str]] = []

            if existing_url:
                payload["conversation_url"] = existing_url
                messages.append({"role": "user", "content": content})
            else:
                messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": content})

            payload["messages"] = messages

            http = self._get_http()
            resp = await http.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            )
            resp.raise_for_status()

            data = resp.json()
            new_url = data.get("conversation_url")
            if new_url:
                self._sessions[slot_id] = new_url

            return data["choices"][0]["message"]["content"]

    def _resolve_model(self, agent_name: str, explicit: str | None = None) -> str:
        if explicit:
            return explicit
        suffix = _agent_env_suffix(agent_name)
        if suffix:
            override = os.getenv(f"WEBGPT_MODEL_{suffix}", "").strip()
            if override:
                return override
        return self.model

    def _resolve_max_tokens(self, agent_name: str, explicit: int | None = None) -> int:
        if explicit:
            return explicit
        suffix = _agent_env_suffix(agent_name)
        if suffix:
            override = _parse_int_env(f"WEBGPT_MAX_TOKENS_{suffix}", 0)
            if override > 0:
                return override
        return self.max_tokens

    async def cleanup(self, slot_id: str = "") -> None:
        """Remove local session tracking AND delete ChatGPT cloud conversations.

        Calls WebGPT admin API DELETE /admin/chatgpt/conversation to remove
        the remote ChatGPT session, preventing session bloat.
        Also cleans up per-session locks.
        """
        import logging as _log
        _logger = _log.getLogger("webgpt_cleanup")

        if not slot_id:
            # Cleanup all sessions
            urls = list(self._sessions.values())
            self._sessions.clear()
            async with self._lock_lock:
                self._locks.clear()
            if urls:
                await self._delete_cloud_conversations(urls)
            return

        url = self._sessions.pop(slot_id, None)
        # Also cleanup the lock for this session
        async with self._lock_lock:
            self._locks.pop(slot_id, None)
        if url:
            await self._delete_cloud_conversations([url])

    async def _delete_cloud_conversations(self, urls: list[str]) -> None:
        """Delete ChatGPT cloud conversations via WebGPT admin API."""
        import logging as _log
        _logger = _log.getLogger("webgpt_cleanup")
        try:
            http = self._get_http()
            resp = await http.request(
                "DELETE",
                f"{self.base_url}/admin/chatgpt/conversation",
                json={"conversation_urls": urls},
            )
            if resp.status_code == 200:
                _logger.info("Deleted %d cloud conversations", len(urls))
            else:
                _logger.warning("Failed to delete cloud conversations: %s %s",
                                resp.status_code, resp.text[:200])
        except Exception as e:
            _logger.warning("Cloud conversation cleanup error: %s", e)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None


# Module-level singleton

_client: WebGPTClient | None = None


def get_webgpt_client() -> WebGPTClient | None:
    """Get or create singleton. Returns None if env vars not set."""
    global _client
    if _client is None:
        base_url = os.getenv("WEBGPT_BASE_URL", DEFAULT_WEBGPT_BASE_URL).strip()
        api_key = os.getenv("WEBGPT_API_KEY", "").strip()
        if base_url and api_key:
            model = os.getenv("WEBGPT_MODEL", DEFAULT_WEBGPT_MODEL).strip()
            max_tokens = _parse_int_env("WEBGPT_MAX_TOKENS", DEFAULT_WEBGPT_MAX_TOKENS)
            timeout_s = _parse_float_env("WEBGPT_TIMEOUT_S", DEFAULT_WEBGPT_TIMEOUT_S)
            _client = WebGPTClient(
                base_url,
                api_key,
                model=model,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
            )
    return _client


def reset_webgpt_client() -> None:
    """Reset singleton (for testing)."""
    global _client
    _client = None


def _parse_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _parse_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _agent_env_suffix(agent_name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in agent_name.upper()).strip("_")
