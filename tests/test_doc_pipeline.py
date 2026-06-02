"""Tests for the document-based 4-layer pipeline.

Run: python3 -m pytest tests/test_doc_pipeline.py -v
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from core_new.doc_pipeline.write_file_tool import WriteFileTool
from core_new.doc_pipeline.doc_parser import parse_doc_header, parse_doc_section, get_doc_status
from core_new.doc_pipeline.agents import AGENT_PROMPTS, AGENT_OUTPUT_FILES, MULTI_TURN_AGENTS
from core_new.doc_pipeline.scheduler import DocScheduler


def run_async(coro):
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


class FakeGateway:
    class Provider:
        model_name = "fake-model"
        sampling_params = {}

    _provider = Provider()


def _write_file_call(path: str, content: str, call_id: str = "call_1") -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": "write_file",
            "arguments": json.dumps({"path": path, "content": content}, ensure_ascii=False),
        },
    }


# ── WriteFileTool tests ──────────────────────────────────────────


class TestWriteFileTool:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tool = WriteFileTool(workspace=self.tmpdir)

    def test_write_success(self):
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            self.tool.execute(path="test.md", content="hello world")
        )
        data = json.loads(result)
        assert data["ok"] is True
        assert data["size"] > 0
        # File exists on disk
        assert (Path(self.tmpdir) / "test.md").exists()
        assert (Path(self.tmpdir) / "test.md").read_text() == "hello world"

    def test_write_subdirectory(self):
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            self.tool.execute(path="sub/dir/file.md", content="nested")
        )
        data = json.loads(result)
        assert data["ok"] is True
        assert (Path(self.tmpdir) / "sub" / "dir" / "file.md").exists()

    def test_write_overwrites(self):
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            self.tool.execute(path="f.md", content="v1")
        )
        asyncio.get_event_loop().run_until_complete(
            self.tool.execute(path="f.md", content="v2")
        )
        assert (Path(self.tmpdir) / "f.md").read_text() == "v2"

    def test_rejects_path_escape(self):
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            self.tool.execute(path="../../../etc/passwd", content="hack")
        )
        data = json.loads(result)
        assert data["ok"] is False
        assert "escapes" in data["error"].lower() or "escape" in data["error"].lower()

    def test_rejects_empty_content(self):
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            self.tool.execute(path="f.md", content="  ")
        )
        data = json.loads(result)
        assert data["ok"] is False

    def test_rejects_missing_path(self):
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            self.tool.execute(path="", content="data")
        )
        data = json.loads(result)
        assert data["ok"] is False

    def test_tool_schema(self):
        schema = self.tool.parameters
        assert schema["type"] == "object"
        assert "path" in schema["properties"]
        assert "content" in schema["properties"]
        assert "path" in schema["required"]
        assert "content" in schema["required"]

    def test_tool_name(self):
        assert self.tool.name == "write_file"


# ── Doc parser tests ─────────────────────────────────────────────


class TestDocParser:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _write_doc(self, filename: str, content: str) -> str:
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_parse_status_pass(self):
        path = self._write_doc("feedback.md", "## status\npass\n\n## summary\nOK")
        header = parse_doc_header(path)
        assert header["status"] == "pass"

    def test_parse_status_needs_fix(self):
        path = self._write_doc("feedback.md", "## status\nneeds_fix\n\n## summary\n参数矛盾")
        status = get_doc_status(path)
        assert status == "needs_fix"

    def test_parse_multiple_sections(self):
        path = self._write_doc("review.md", (
            "## status\npass\n\n"
            "## summary\n题目质量良好\n\n"
            "## detailed_feedback\n计算结果正确"
        ))
        header = parse_doc_header(path)
        assert header["status"] == "pass"
        assert "题目质量良好" in header["summary"]

    def test_parse_section_extraction(self):
        path = self._write_doc("review.md", (
            "## status\nneeds_fix\n\n"
            "## corrections\n### stem\n修正后题干\n\n"
            "## detailed_feedback\n具体意见"
        ))
        section = parse_doc_section(path, "detailed_feedback")
        assert "具体意见" in section

    def test_parse_missing_section(self):
        path = self._write_doc("review.md", "## status\npass")
        section = parse_doc_section(path, "nonexistent")
        assert section == ""

    def test_parse_strips_thinking(self):
        path = self._write_doc("doc.md", "<think >some reasoning</think >\n## status\npass")
        status = get_doc_status(path)
        assert status == "pass"

    def test_get_status_missing_file(self):
        with pytest.raises(FileNotFoundError):
            get_doc_status(os.path.join(self.tmpdir, "nonexistent.md"))


# ── Agent prompts tests ──────────────────────────────────────────


class TestAgentPrompts:
    def test_all_roles_have_prompts(self):
        expected_roles = {"design", "question", "analysis", "coding", "review", "fix", "format"}
        assert set(AGENT_PROMPTS.keys()) == expected_roles

    def test_all_roles_have_output_files(self):
        expected_roles = {"design", "question", "analysis", "coding", "review", "fix", "format"}
        assert set(AGENT_OUTPUT_FILES.keys()) == expected_roles

    def test_output_files_have_extensions(self):
        for role, filename in AGENT_OUTPUT_FILES.items():
            assert "." in filename, f"{role} output file '{filename}' has no extension"

    def test_coding_output_is_py(self):
        assert AGENT_OUTPUT_FILES["coding"] == "solve.py"

    def test_multi_turn_agents(self):
        assert "question" in MULTI_TURN_AGENTS
        assert "analysis" in MULTI_TURN_AGENTS

    def test_prompts_mention_write_file(self):
        for role, prompt in AGENT_PROMPTS.items():
            assert "write_file" in prompt, f"{role} prompt doesn't mention write_file tool"

    def test_prompts_mention_output_filename(self):
        for role, prompt in AGENT_PROMPTS.items():
            expected_file = AGENT_OUTPUT_FILES[role]
            assert expected_file in prompt, f"{role} prompt doesn't mention its output file {expected_file}"


# ── Integration: WriteFileTool + DocParser round-trip ────────────


class TestRoundTrip:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tool = WriteFileTool(workspace=self.tmpdir)

    def test_write_then_parse(self):
        import asyncio
        content = "## status\npass\n\n## summary\n题目参数一致，难度匹配"
        asyncio.get_event_loop().run_until_complete(
            self.tool.execute(path="feedback.md", content=content)
        )
        filepath = str(Path(self.tmpdir) / "feedback.md")
        header = parse_doc_header(filepath)
        assert header["status"] == "pass"
        assert "参数一致" in header["summary"]

    def test_write_code_then_check_exists(self):
        import asyncio
        code = "import math\nprint('hello')\n"
        asyncio.get_event_loop().run_until_complete(
            self.tool.execute(path="solve.py", content=code)
        )
        assert (Path(self.tmpdir) / "solve.py").exists()
        assert (Path(self.tmpdir) / "solve.py").read_text() == code


# ── DocScheduler protocol-level tool calling ────────────────────


class TestDocSchedulerToolProtocol:
    def test_run_agent_writes_only_from_protocol_tool_call(self, tmp_path):
        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)
        calls = []

        async def fake_stream(provider, messages, **kwargs):
            calls.append(kwargs)
            return {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [
                    _write_file_call("blueprint.md", "## status\ndraft\n\n## 知识点\nCache")
                ],
            }

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("design", "task", slot_id="S1"))

        assert result.startswith("## status")
        assert (tmp_path / "S1" / "blueprint.md").read_text(encoding="utf-8") == result
        assert calls[0]["tool_choice"] == "required"

    def test_run_agent_extracts_textual_tool_call(self, tmp_path):
        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)
        textual = (
            '[{"name": "write_file", "parameters": {"path": "blueprint.md", '
            '"content": "## status\\ndraft"}}]'
        )

        async def fake_stream(provider, messages, **kwargs):
            return {
                "content": textual,
                "reasoning_content": "",
                "tool_calls": None,
            }

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("design", "task", slot_id="S2"))

        assert result == "## status\ndraft"
        assert (tmp_path / "S2" / "blueprint.md").exists()

    def test_run_agent_does_not_reuse_stale_expected_file(self, tmp_path):
        slot_dir = tmp_path / "S3"
        slot_dir.mkdir()
        stale = slot_dir / "blueprint.md"
        stale.write_text("old content", encoding="utf-8")

        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)

        async def fake_stream(provider, messages, **kwargs):
            return {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [
                    _write_file_call("wrong.md", "## status\ndraft")
                ],
            }

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("design", "task", slot_id="S3"))

        assert result == ""
        assert not stale.exists()
        assert (slot_dir / "wrong.md").exists()

    def test_run_agent_retries_when_tool_writes_wrong_path(self, tmp_path):
        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)
        responses = [
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_write_file_call("wrong.md", "wrong", "call_1")],
            },
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_write_file_call("blueprint.md", "## status\ndraft", "call_2")],
            },
        ]

        async def fake_stream(provider, messages, **kwargs):
            return responses.pop(0)

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("design", "task", slot_id="S4"))

        assert result == "## status\ndraft"
        assert (tmp_path / "S4" / "blueprint.md").exists()
