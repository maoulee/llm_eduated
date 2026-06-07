"""WebGPT delegation client — per-slot GPT conversation manager."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Dict

import httpx

logger = logging.getLogger(__name__)


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

    Cloud conversation deletion is deferred: completed sessions are
    accumulated in a pending list and batch-deleted when the threshold
    is reached, preventing context leakage caused by immediate URL
    recycling.
    """

    # Batch-delete cloud conversations once this many accumulate.
    _BATCH_DELETE_THRESHOLD = 10

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        model: str = DEFAULT_WEBGPT_MODEL,
        max_tokens: int = DEFAULT_WEBGPT_MAX_TOKENS,
        timeout_s: float = DEFAULT_WEBGPT_TIMEOUT_S,
        batch_delete_threshold: int | None = None,
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
        self._pending_deletions: list[str] = []  # URLs awaiting cloud deletion
        self._batch_threshold = (
            batch_delete_threshold if batch_delete_threshold is not None
            else _parse_int_env("WEBGPT_BATCH_DELETE_THRESHOLD", self._BATCH_DELETE_THRESHOLD)
        )
        self._flush_fail_count: int = 0  # consecutive flush failure count
        self._MAX_FLUSH_FAILS = 3  # drop URLs after this many consecutive failures

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

            content = data["choices"][0]["message"].get("content", "") or ""

            # gpt-thinking 交错思考：先输出一段简介 → 思考 → 再输出完整答案。
            # 初始响应可能只有思考前的片段（< 200 chars）。
            # 如果内容过短且有 conversation_url，等待后通过 admin API 重新拉取。
            if len(content.strip()) < 200 and new_url:
                content = await self._refetch_full_response(new_url, content)

            return content

    async def _refetch_full_response(
        self, conversation_url: str, initial_content: str
    ) -> str:
        """Re-fetch complete response via admin API after thinking model finishes.

        gpt-thinking returns a brief pre-thinking text first, then thinks for
        10-30s, then writes the full answer.  If the initial content is short
        (< 200 chars), wait for thinking to complete and pull the full
        assistant message from the ChatGPT backend API.

        Returns the full content if recovered, otherwise the initial content.
        """
        conv_id = _extract_conversation_id(conversation_url)
        if not conv_id:
            return initial_content

        # Thinking models typically take 10-30s.  Wait before polling.
        logger.info(
            "Response too short (%d chars), waiting 15s before re-fetching conversation %s",
            len(initial_content.strip()), conv_id[:8],
        )
        await asyncio.sleep(15)

        try:
            http = self._get_http()
            resp = await http.get(
                f"{self.base_url}/admin/chatgpt/conversation/{conv_id}",
                timeout=httpx.Timeout(30.0),
            )
            if resp.status_code != 200:
                logger.warning("Admin API returned %d, using initial content", resp.status_code)
                return initial_content

            data = resp.json()
            messages = data.get("messages", [])
            # Find the latest assistant message
            assistant_msgs = [m for m in messages if m.get("role") == "assistant" and m.get("text", "").strip()]
            if not assistant_msgs:
                logger.warning("No assistant messages found in re-fetch, using initial content")
                return initial_content

            # Pick the last assistant message (most recent)
            latest = assistant_msgs[-1]
            full_text = latest["text"].strip()

            if len(full_text) > len(initial_content.strip()):
                logger.info(
                    "Re-fetch recovered full response (%d chars, was %d)",
                    len(full_text), len(initial_content.strip()),
                )
                return full_text

            logger.info("Re-fetch content not longer than initial (%d vs %d), keeping initial", len(full_text), len(initial_content.strip()))
            return initial_content

        except Exception as exc:
            logger.warning("Re-fetch failed: %s, using initial content", exc)
            return initial_content

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
        """Remove local session tracking; defer cloud conversation deletion.

        Moves completed conversation URLs into a pending-deletion list.
        Cloud conversations are NOT deleted immediately — they are batch-
        deleted once the pending list reaches ``_batch_threshold``.
        This prevents ChatGPT from recycling URLs too fast and leaking
        residual context into new conversations.

        Call ``flush_pending_deletions()`` to force immediate cloud deletion.
        """
        if not slot_id:
            # Mark all sessions as pending deletion
            self._pending_deletions.extend(self._sessions.values())
            self._sessions.clear()
            async with self._lock_lock:
                self._locks.clear()
        else:
            url = self._sessions.pop(slot_id, None)
            async with self._lock_lock:
                self._locks.pop(slot_id, None)
            if url:
                self._pending_deletions.append(url)

        # Batch-delete when threshold is reached
        if len(self._pending_deletions) >= self._batch_threshold:
            await self._flush_batch()

    async def flush_pending_deletions(self) -> None:
        """Force-delete all pending cloud conversations immediately."""
        await self._flush_batch()

    async def _flush_batch(self) -> None:
        """Batch-delete accumulated conversation URLs from ChatGPT cloud."""
        if not self._pending_deletions:
            return
        urls, self._pending_deletions = self._pending_deletions, []
        try:
            http = self._get_http()
            resp = await http.request(
                "DELETE",
                f"{self.base_url}/admin/chatgpt/conversation",
                json={"conversation_urls": urls},
            )
            if resp.status_code == 200:
                logger.info("Batch-deleted %d cloud conversations", len(urls))
                self._flush_fail_count = 0
            else:
                self._flush_fail_count += 1
                if self._flush_fail_count >= self._MAX_FLUSH_FAILS:
                    logger.error(
                        "Batch delete failed %d consecutive times (%s %s), dropping %d URLs",
                        self._flush_fail_count, resp.status_code, resp.text[:200], len(urls),
                    )
                    self._flush_fail_count = 0
                else:
                    logger.warning("Batch delete failed: %s %s — re-queuing %d URLs",
                                   resp.status_code, resp.text[:200], len(urls))
                    self._pending_deletions[:0] = urls
        except Exception as exc:
            self._flush_fail_count += 1
            if self._flush_fail_count >= self._MAX_FLUSH_FAILS:
                logger.error("Batch delete error after %d retries: %s, dropping URLs",
                             self._flush_fail_count, exc)
                self._flush_fail_count = 0
            else:
                logger.warning("Batch delete error: %s — re-queuing %d URLs", exc, len(urls))
                self._pending_deletions[:0] = urls

    async def close(self) -> None:
        """Flush pending deletions and close the underlying HTTP client."""
        await self._flush_batch()
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
            batch_threshold_raw = _parse_int_env("WEBGPT_BATCH_DELETE_THRESHOLD", -1)
            batch_threshold = batch_threshold_raw if batch_threshold_raw >= 0 else None
            _client = WebGPTClient(
                base_url,
                api_key,
                model=model,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                batch_delete_threshold=batch_threshold,
            )
    return _client


def reset_webgpt_client() -> None:
    """Reset singleton (for testing)."""
    global _client
    _client = None


def shutdown_webgpt_client() -> None:
    """Synchronous shutdown: flush pending deletions and close HTTP client.

    Safe to call from atexit or signal handlers. Best-effort: logs
    failures but never raises.
    """
    global _client
    if _client is None:
        return
    client = _client
    _client = None
    try:
        asyncio.run(client.close())
    except RuntimeError:
        pass
    except Exception as exc:
        logger.warning("shutdown_webgpt_client error: %s", exc)


import atexit
atexit.register(shutdown_webgpt_client)


def _extract_conversation_id(url: str) -> str | None:
    """Extract ChatGPT conversation UUID from a /c/ URL."""
    if not url:
        return None
    m = re.search(r'/c/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url, re.IGNORECASE)
    return m.group(1) if m else None


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
