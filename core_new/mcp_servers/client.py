"""MCP Python exec client — singleton that manages the server subprocess.

Usage:
    from core_new.mcp_servers.client import mcp_python_exec

    # Returns dict: {ok, exit_code, stdout, stderr, timed_out}
    result = await mcp_python_exec("import math; print(math.pi)")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import threading
from typing import Any

from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
_PYTHONPATH = os.pathsep.join(
    part for part in (str(REPO_ROOT), os.environ.get("PYTHONPATH", "")) if part
)

_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "core_new.mcp_servers.python_exec_server"],
    cwd=str(REPO_ROOT),
    env={**os.environ, "PYTHONPATH": _PYTHONPATH},
)


class _MCPExecClient:
    """Lazy-initializing MCP client for python_exec.

    Starts the server subprocess on first call, reuses the session
    for subsequent calls. Thread-safe via asyncio lock.
    """

    def __init__(self):
        self._session: ClientSession | None = None
        self._stdio_cm = None
        self._session_cm = None
        self._lock: asyncio.Lock | None = None
        self._call_lock: asyncio.Lock | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = False

    def _clear_state(self) -> None:
        self._session = None
        self._session_cm = None
        self._stdio_cm = None
        self._started = False
        self._loop = None
        self._lock = None
        self._call_lock = None

    async def _ensure_loop(self) -> None:
        current = asyncio.get_running_loop()
        if self._loop is current and self._lock is not None and self._call_lock is not None:
            return
        if self._loop is not None and self._loop is not current:
            if self._loop.is_closed():
                logger.warning("MCP exec loop changed after old loop closed; dropping old session refs")
                self._clear_state()
            else:
                try:
                    await asyncio.wait_for(self._reset(), timeout=2.0)
                except Exception as exc:
                    logger.warning("MCP exec loop reset failed; dropping session refs: %s", exc)
                    self._clear_state()
        self._loop = current
        self._lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()

    async def _ensure_started(self):
        await self._ensure_loop()
        if self._started and self._session is not None:
            return
        async with self._lock:
            if self._started:
                return
            try:
                # Start server subprocess and establish session.
                self._stdio_cm = stdio_client(_SERVER_PARAMS)
                read, write = await self._stdio_cm.__aenter__()
                self._session_cm = ClientSession(read, write)
                self._session = await self._session_cm.__aenter__()
                await self._session.initialize()
                self._started = True
                logger.info("MCP python_exec server started")
            except Exception:
                await self._reset()
                raise

    async def exec_code(
        self,
        code: str,
        timeout: int = 10,
        max_output: int | None = None,
    ) -> dict[str, Any]:
        """Execute Python code via MCP server.

        Returns: {ok: bool, exit_code: int, stdout: str, stderr: str, timed_out: bool}
        """
        await self._ensure_loop()
        await self._ensure_started()

        payload: dict[str, Any] = {"code": code, "timeout": timeout}
        if max_output is not None:
            payload["max_output"] = max_output

        # ClientSession over stdio is a single stream; serialize calls to avoid
        # interleaving concurrent tool requests from parallel agent runs.
        async with self._call_lock:
            try:
                result = await self._session.call_tool("python_exec", payload)
                text = result.content[0].text
                return json.loads(text)
            except Exception as e:
                # Session broken — reset so next call restarts.
                logger.warning("MCP exec failed, resetting session: %s", e)
                await self._reset()
                return {
                    "ok": False,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": str(e),
                    "timed_out": False,
                }

    async def _reset(self):
        """Reset session so next call re-initializes."""
        try:
            if self._session_cm:
                await self._session_cm.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            if self._stdio_cm:
                await self._stdio_cm.__aexit__(None, None, None)
        except Exception:
            pass
        self._clear_state()

    async def shutdown(self):
        """Gracefully shut down the MCP server."""
        await self._reset()
        logger.info("MCP python_exec server shut down")


# Module-level singleton
_client = _MCPExecClient()


async def mcp_python_exec(
    code: str,
    timeout: int = 10,
    max_output: int | None = None,
) -> dict[str, Any]:
    """Execute Python code via the shared MCP server."""
    return await _client.exec_code(code, timeout=timeout, max_output=max_output)


async def mcp_shutdown():
    """Shut down the MCP server (call at app exit)."""
    await _client.shutdown()
