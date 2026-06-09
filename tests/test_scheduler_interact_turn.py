from __future__ import annotations

import asyncio
import copy
import json
import os

from core_new.doc_pipeline.scheduler import DocScheduler
from core_new.doc_pipeline.read_file_tool import ReadFileTool


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


class FakeStreamGateway:
    provider_name = "fake"
    model_name = "fake"

    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    async def stream_chat(self, messages, **_kwargs):
        self.calls.append(copy.deepcopy(messages))
        if not self.responses:
            return {"content": ""}
        return self.responses.pop(0)


def _tool_call(name: str, arguments: dict, call_id: str = "call_1") -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }


def test_interact_turn_continues_after_tool_call(tmp_path):
    gateway = FakeStreamGateway([
        {
            "content": "",
            "tool_calls": [
                _tool_call(
                    "write_file",
                    {"path": "interact_draft.md", "content": "# 草案\n"},
                )
            ],
        },
        {"content": "草案已写入，请在右侧文档标注后确认。"},
    ])
    scheduler = DocScheduler(gateway, workspace=tmp_path, enable_thinking=False)

    result = run_async(
        scheduler.run_conversation_turn("s1", "出一套组成原理期末卷")
    )

    assert result["status"] == "ok"
    assert result["response_text"] == "草案已写入，请在右侧文档标注后确认。"
    assert result["files_written"] == ["interact_draft.md"]
    assert (tmp_path / "s1" / "interact_draft.md").read_text(encoding="utf-8") == "# 草案\n"

    assert len(gateway.calls) == 2
    second_call_messages = gateway.calls[1]
    assert second_call_messages[-1]["role"] == "tool"
    tool_result = json.loads(second_call_messages[-1]["content"])
    assert tool_result["ok"] is True
    assert tool_result["path"] == "interact_draft.md"


def test_interact_turn_returns_fallback_when_followup_is_empty(tmp_path):
    gateway = FakeStreamGateway([
        {
            "content": "",
            "tool_calls": [
                _tool_call(
                    "write_file",
                    {"path": "interact_draft.md", "content": "# 草案\n"},
                )
            ],
        },
        {"content": ""},
    ])
    scheduler = DocScheduler(gateway, workspace=tmp_path, enable_thinking=False)

    result = run_async(
        scheduler.run_conversation_turn("s1", "出一套组成原理期末卷")
    )

    assert result["status"] == "ok"
    assert result["response_text"] == "执行了 1 个工具调用"
    assert result["files_written"] == ["interact_draft.md"]


def test_read_file_tool_allows_explicit_read_roots(tmp_path):
    workspace = tmp_path / "workspace"
    data_root = tmp_path / "data"
    workspace.mkdir()
    data_root.mkdir()
    (workspace / "draft.md").write_text("workspace file\n", encoding="utf-8")
    (data_root / "kg.md").write_text("kg file\n", encoding="utf-8")

    tool = ReadFileTool(workspace=workspace, read_roots=[data_root])

    workspace_result = run_async(tool.execute(path="draft.md"))
    assert json.loads(workspace_result)["ok"] is True

    data_result = run_async(tool.execute(path=str(data_root / "kg.md")))
    parsed_data = json.loads(data_result)
    assert parsed_data["ok"] is True
    assert "kg file" in parsed_data["content"]

    relative_data_tool = ReadFileTool(workspace=workspace, read_roots=[tmp_path / "data"])
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        relative_data_result = run_async(relative_data_tool.execute(path="data/kg.md"))
    finally:
        os.chdir(old_cwd)
    parsed_relative_data = json.loads(relative_data_result)
    assert parsed_relative_data["ok"] is True
    assert "kg file" in parsed_relative_data["content"]

    escaped_result = run_async(tool.execute(path=str(tmp_path / "outside.md")))
    parsed_escaped = json.loads(escaped_result)
    assert parsed_escaped["ok"] is False
    assert "escapes allowed read roots" in parsed_escaped["error"]
