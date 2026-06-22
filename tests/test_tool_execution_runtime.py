from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from core_new.agent_runtime import Edu408AgentLoop, Tool, ToolRegistry
from core_new.agent_tools import ToolExecutor
from core_new.edu408_runtime import CodeExec408Tool
from core_new.llm_gateway import LLMResult
from core_new.mcp_servers.client import mcp_python_exec, mcp_shutdown


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


class EchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo a value."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        }

    async def execute(self, value: int) -> str:
        return json.dumps({"value": value})


class FakeGateway:
    provider_name = "fake"
    model_name = "fake"

    async def generate_with_tools(
        self,
        messages,
        *,
        tools,
        tool_executor,
        max_tokens=None,
        enable_thinking=False,
        max_rounds=10,
    ):
        observation = await tool_executor.execute("echo", {"value": "7"})
        return LLMResult.success(
            content=f"done: {observation}",
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=1,
        )


def test_tool_executor_dispatches_runtime_tool_with_casting():
    async def _run():
        executor = ToolExecutor([EchoTool()])
        raw = await executor.execute("echo", {"value": "3"})
        assert json.loads(raw) == {"value": 3}

        bad = await executor.execute("echo", {})
        parsed = json.loads(bad)
        assert parsed["ok"] is False
        assert "missing required value" in parsed["error"]

    run_async(_run())


def test_runtime_loop_records_tool_trace(tmp_path):
    async def _run():
        registry = ToolRegistry()
        registry.register(EchoTool())

        loop = Edu408AgentLoop(
            FakeGateway(),
            registry,
            workspace=tmp_path,
            max_iterations=2,
            enable_thinking=False,
        )
        result = await loop.run("use echo")

        assert result.tools_used == ["echo"]
        assert len(result.trace.tool_traces) == 1
        trace = result.trace.tool_traces[0]
        assert trace.tool_name == "echo"
        assert trace.arguments == {"value": "7"}
        assert json.loads(trace.observation) == {"value": 7}

    run_async(_run())


def test_code_exec_408_persists_and_reruns_script():
    async def _run():
        try:
            tool = CodeExec408Tool()
            raw = await tool.execute(
                code="print('hello from persisted script')",
                slot_id="TEST_TOOL_EXEC",
                step=1,
                persist=True,
                timeout=5,
            )
            parsed = json.loads(raw)
            assert parsed["ok"] is True
            assert "hello from persisted script" in parsed["stdout"]
            assert parsed["file_path"].startswith("tmp/solutions/TEST_TOOL_EXEC/")
            assert Path(parsed["file_path"]).exists()

            rerun_raw = await tool.execute(file_path=parsed["file_path"], timeout=5)
            rerun = json.loads(rerun_raw)
            assert rerun["ok"] is True
            assert "hello from persisted script" in rerun["stdout"]
        finally:
            await mcp_shutdown()

    run_async(_run())


def test_mcp_python_exec_serializes_concurrent_calls():
    async def _run():
        try:
            results = await asyncio.gather(
                mcp_python_exec("print(1 + 1)", timeout=5),
                mcp_python_exec("print(2 + 2)", timeout=5),
                mcp_python_exec("print(3 + 3)", timeout=5),
            )
            assert [r["ok"] for r in results] == [True, True, True]
            assert [r["stdout"].strip() for r in results] == ["2", "4", "6"]
        finally:
            await mcp_shutdown()

    run_async(_run())
