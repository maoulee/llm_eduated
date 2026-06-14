"""Tests for the document-based 4-layer pipeline.

Run: python3 -m pytest tests/test_doc_pipeline.py -v
"""

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from core_new.doc_pipeline.write_file_tool import WriteFileTool
from compose.artifact_store import _extract_knowledge_graph_section
from compose.compose_runner import _parse_outline_to_blueprint
from compose.generate_runner import _extract_structured_fields_from_final_md
from core_new.doc_pipeline.doc_parser import parse_doc_header, parse_doc_section, get_doc_status
from core_new.doc_pipeline.context import ContextRegistry, FileProvider, InlineProvider, ProviderDef
from core_new.doc_pipeline.agent_loader import load_agents, get_agent_dicts, AgentSpec, _parse_agent_md
from core_new.doc_pipeline.dual_agent_orchestrator import DualAgentOrchestrator
from core_new.doc_pipeline.grep_search_tool import GrepSearchTool
from core_new.doc_pipeline.orchestrator import DocPipelineOrchestrator
from core_new.doc_pipeline.scheduler import AGENT_PROMPTS, AGENT_OUTPUT_FILES, MULTI_TURN_AGENTS
from core_new.doc_pipeline.scheduler import DocScheduler, ROLE_SKILLS, ROLE_REQUIRED_TOOLS
from core_new.agent_roles import TransportRetryPolicy
from core_new.llm_gateway import LLMGateway
from compose.knowledge_index import KnowledgeIndex
from llm_providers_new.remote_api import RemoteAPIProvider


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


class FakeStreamClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **params):
        self.calls.append(params)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response

        async def _stream():
            for chunk in response:
                yield chunk

        return _stream()


class FakeChatCallProvider:
    model_name = "fake-chat-model"
    sampling_params = {}

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def _chat_call(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _stream_chunk(*, content="", reasoning="", tool_calls=None, finish_reason=None):
    delta = SimpleNamespace(
        content=content,
        reasoning_content=reasoning,
        reasoning="",
        tool_calls=tool_calls,
    )
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def _write_file_call(path: str, content: str, call_id: str = "call_1") -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": "write_file",
            "arguments": json.dumps({"path": path, "content": content}, ensure_ascii=False),
        },
    }


def _tool_call(name: str, arguments: dict, call_id: str = "call_1") -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
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

    def test_rejects_invalid_status(self):
        path = self._write_doc("feedback.md", "## status\nmaybe\n\n## summary\n格式异常")
        status = get_doc_status(path, allowed={"pass", "needs_fix"})
        assert status == ""

    def test_rejects_status_outside_allowed_set(self):
        path = self._write_doc("feedback.md", "## status\nexpression_fix\n\n## summary\n终审状态")
        status = get_doc_status(path, allowed={"pass", "needs_fix"})
        assert status == ""

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

    def test_get_status_accepts_bold_inline_status(self):
        path = self._write_doc("review.md", "## 审核结论\n\n**status: pass**\n")
        status = get_doc_status(path, allowed={"pass", "needs_fix"})
        assert status == "pass"

    def test_get_status_accepts_plain_inline_status(self):
        path = self._write_doc("review.md", "## 审核结论\n\nstatus: needs_fix\n")
        status = get_doc_status(path, allowed={"pass", "needs_fix"})
        assert status == "needs_fix"

    def test_get_status_missing_file(self):
        with pytest.raises(FileNotFoundError):
            get_doc_status(os.path.join(self.tmpdir, "nonexistent.md"))


# ── Agent prompts tests ──────────────────────────────────────────


class TestAgentPrompts:
    def test_all_roles_have_prompts(self):
        expected_roles = {
            "outline", "question_design",
            "review", "solve", "final_review",
            "paper_outline",
            "interact", "human_intake",
            # §19 split-focused design agents
            "design", "exam_form",
        }
        assert set(AGENT_PROMPTS.keys()) == expected_roles

    def test_all_roles_have_output_files(self):
        expected_roles = {
            "outline", "question_design",
            "review", "solve", "final_review",
            "paper_outline",
            "interact", "human_intake",
            # §19 split-focused design agents
            "design", "exam_form",
        }
        assert set(AGENT_OUTPUT_FILES.keys()) == expected_roles

    def test_output_files_have_extensions(self):
        for role, filename in AGENT_OUTPUT_FILES.items():
            assert "." in filename, f"{role} output file '{filename}' has no extension"

    def test_design_role_owns_question_md(self):
        # §19: design replaces question_sc/question_comp; both passes write question.md.
        assert AGENT_OUTPUT_FILES["design"] == "question.md"

    def test_multi_turn_agents(self):
        # §19: design is multi-turn (P1 feedback rounds across form_gate retries).
        assert "design" in MULTI_TURN_AGENTS

    def test_prompts_mention_write_file(self):
        for role, prompt in AGENT_PROMPTS.items():
            assert "write_file" in prompt, f"{role} prompt doesn't mention write_file tool"

    def test_prompts_mention_output_filename(self):
        for role, prompt in AGENT_PROMPTS.items():
            expected_file = AGENT_OUTPUT_FILES[role]
            assert expected_file in prompt, f"{role} prompt doesn't mention its output file {expected_file}"

    def test_solve_prompt_encodes_code_as_truth(self):
        # §18: solve = problem-solving code (brief-think-then-code). The solver
        # writes solve.py itself, execs, fixes the CODE (never the stem,
        # discipline ②), and writes solution. This is NOT a DAG / parameter
        # search — it's just solving the problem in code.
        prompt = AGENT_PROMPTS["solve"]
        # §18.6: brief-think-then-code is the discipline.
        assert "brief" in prompt
        # §18.2 discipline ②: exec error → fix solve.py, never the stem.
        assert "不得改题干" in prompt or "绝不改题干" in prompt
        # solve only computes correct — no error algorithms / distractors.
        assert "只算正确" in prompt or "只计算正确" in prompt
        assert "错误算法" in prompt
        # §19.5: exec errors = code bugs, fixed internally (no code_error back-route).
        assert "内部循环" in prompt or "内部 fix" in prompt
        # §18.3: solve.py is problem-solving code, NOT a DAG / parameter search.
        assert "解题代码" in prompt
        assert "参数搜索" in prompt  # mentioned as "not this" — over-architecture purged
        # Old minimal-fix / parameter-search endorsement is explicitly gone.
        assert "参数搜索仅作为兜底" not in prompt
        assert "不得为了匹配选项而枚举搜索参数" not in prompt

    def test_review_prompt_is_form_gate_not_answer_checker(self):
        # Form Gate (spec §15 Layer 3): review must NOT treat a choice question
        # missing its A/B/C/D option values as a defect. Under code-as-truth the
        # option values are assembled by the solve stage after solve.py runs —
        # at form_gate time question.md legitimately has no option values. A
        # reviewer that demanded options here would dead-loop question↔form_gate
        # until MAX_NODE_VISITS. Review must also never compute answer values.
        prompt = AGENT_PROMPTS["review"]
        skill = ROLE_SKILLS.get("review", "")

        # form_gate must not fail a choice question for lacking option values
        assert "不得因选择题缺选项值" in prompt or "不得因选择题缺选项值" in skill
        # review must not compute / propose answer numbers
        assert ("不得脑内算答案" in prompt or "不得脑内算答案" in skill)
        assert "计算/提出/建议任何答案" in prompt or "不得出现答案数值" in skill
        # The old checklist item that demanded "选项/子问题是否结构正确" with
        # "4选项1正确" is gone — replaced by solve.py logic / structure review.
        assert "4选项1正确" not in skill
        assert "选项/子问题是否结构正确" not in prompt


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
                    _write_file_call("outline.md", "## status\ndraft\n\n## 知识点\nCache")
                ],
            }

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("outline", "task", slot_id="S1"))

        assert result.startswith("## status")
        assert (tmp_path / "S1" / "outline.md").read_text(encoding="utf-8") == result
        assert calls[0]["tool_choice"] == "auto"

    def test_run_agent_extracts_textual_tool_call(self, tmp_path):
        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)
        textual = (
            '[{"name": "write_file", "parameters": {"path": "outline.md", '
            '"content": "## status\\ndraft"}}]'
        )

        async def fake_stream(provider, messages, **kwargs):
            return {
                "content": textual,
                "reasoning_content": "",
                "tool_calls": None,
            }

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("outline", "task", slot_id="S2"))

        assert result == "## status\ndraft"
        assert (tmp_path / "S2" / "outline.md").exists()

    def test_run_agent_does_not_reuse_stale_expected_file(self, tmp_path):
        slot_dir = tmp_path / "S3"
        slot_dir.mkdir()
        stale = slot_dir / "outline.md"
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

        result = run_async(scheduler.run_agent("outline", "task", slot_id="S3"))

        assert result == ""
        assert not stale.exists()
        assert (slot_dir / "wrong.md").exists()

    def test_preserve_existing_allows_edit_file_target(self, tmp_path):
        slot_dir = tmp_path / "S3B"
        slot_dir.mkdir()
        target = slot_dir / "question.md"
        target.write_text("## status\ndraft\n\n## 题干\nold\n", encoding="utf-8")

        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)

        async def fake_stream(provider, messages, **kwargs):
            return {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [
                    _tool_call(
                        "edit_file",
                        {"path": "question.md", "old_string": "old", "new_string": "new"},
                        "call_edit",
                    )
                ],
            }

        scheduler._streaming_chat_call = fake_stream

        result = run_async(
            scheduler.run_agent(
                "design",
                "fix",
                slot_id="S3B",
                target_file="question.md",
                preserve_existing=True,
            )
        )

        assert "new" in result
        assert target.exists()
        assert "new" in target.read_text(encoding="utf-8")

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
                "tool_calls": [_write_file_call("outline.md", "## status\ndraft", "call_2")],
            },
        ]

        async def fake_stream(provider, messages, **kwargs):
            return responses.pop(0)

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("outline", "task", slot_id="S4"))

        assert result == "## status\ndraft"
        assert (tmp_path / "S4" / "outline.md").exists()

    def test_normal_workflow_keeps_full_history(self, tmp_path):
        """A normal read→write workflow keeps full message history."""
        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)
        calls = []
        responses = [
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_tool_call("read_file", {"path": "assembled.md"}, "call_1")],
            },
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_write_file_call("question.md", "## status\ndraft\n\n## 题干\nT", "call_2")],
            },
        ]

        async def fake_stream(provider, messages, **kwargs):
            calls.append({"messages": list(messages), **kwargs})
            return responses.pop(0)

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("design", "task", slot_id="S5", skill_override="design_draft_skill"))

        assert result.startswith("## status")
        # 2 calls: read assembled.md, then write question.md
        assert len(calls) == 2
        second_call = calls[1]
        tool_names = [t["function"]["name"] for t in second_call["tools"]]
        assert "write_file" in tool_names
        assert "read_file" in tool_names
        assert "exec_file" not in tool_names
        # Normal history preserved — 1 system prompt
        assert len([m for m in second_call["messages"] if m["role"] == "system"]) == 1

    def test_context_trim_after_many_no_progress_rounds(self, tmp_path):
        """Many rounds with zero file writes should trigger context trimming."""
        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)
        calls = []
        # 8 rounds of only read_file (no file writes), then a write.
        responses = []
        for i in range(8):
            responses.append({
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_tool_call("read_file", {"path": "assembled.md"}, f"call_{i}")],
            })
        responses.append({
            "content": "",
            "reasoning_content": "",
            "tool_calls": [_write_file_call("question.md", "## status\ndraft\n\n## 题干\nT", "call_final")],
        })

        async def fake_stream(provider, messages, **kwargs):
            calls.append({"messages": list(messages), **kwargs})
            return responses.pop(0)

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("design", "task", slot_id="S6", skill_override="design_draft_skill"))

        assert result.startswith("## status")
        # The final call should have trimmed context — system + 1 compressed user message
        final_call = calls[-1]
        assert final_call["messages"][0]["role"] == "system"
        # Trimmed history: system + compressed summary (fewer messages than raw 8 rounds)
        assert len(final_call["messages"]) < 20

    def test_skeleton_design_grep_limit_forces_question_write(self, tmp_path):
        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)
        calls = []
        responses = [
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_tool_call(
                    "grep_search",
                    {"query": ["二叉树遍历"], "subject": "数据结构", "question_type": "综合题"},
                    "grep_1",
                )],
            },
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_tool_call(
                    "grep_search",
                    {"query": ["前序", "中序"], "subject": "数据结构", "question_type": "综合题"},
                    "grep_2",
                )],
            },
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_tool_call(
                    "grep_search",
                    {"query": ["还原二叉树"], "subject": "数据结构", "question_type": "综合题"},
                    "grep_3",
                )],
            },
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_write_file_call(
                    "question.md",
                    "## status\ndraft\n\n## 题干\nT\n\n## 设计说明\n复用骨架",
                    "write_after_limit",
                )],
            },
        ]

        async def fake_stream(provider, messages, **kwargs):
            calls.append({"messages": list(messages), **kwargs})
            return responses.pop(0)

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent(
            "design", "task", slot_id="S6A", skill_override="design_draft_skill",
        ))

        assert result.startswith("## status")
        assert (tmp_path / "S6A" / "question.md").exists()
        assert calls[-1]["tool_choice"] == {
            "type": "function",
            "function": {"name": "write_file"},
        }
        assert "grep_search 上限" in calls[-1]["messages"][-1]["content"]

    def test_skeleton_design_uses_upstream_cache_instead_of_grep(self, tmp_path):
        slot_dir = tmp_path / "S6CACHE"
        slot_dir.mkdir()
        (slot_dir / "assembled.md").write_text(
            "## 参考经验摘要\n"
            "- 历史模式: 给定二叉树遍历序列，还原结构并追问性质\n"
            "- 难度锚点: n=7-8, 2-3问\n",
            encoding="utf-8",
        )

        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)
        calls = []
        responses = [
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_tool_call(
                    "grep_search",
                    {"query": ["二叉树遍历"], "subject": "数据结构", "question_type": "综合题"},
                    "grep_should_skip",
                )],
            },
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_write_file_call(
                    "question.md",
                    "## status\ndraft\n\n## 题干\nT\n\n## 设计说明\n复用缓存骨架",
                    "write_after_cache",
                )],
            },
        ]

        async def fake_stream(provider, messages, **kwargs):
            calls.append({"messages": list(messages), **kwargs})
            return responses.pop(0)

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent(
            "design",
            "task",
            slot_id="S6CACHE",
            skill_override="design_draft_skill",
            inject_files={"规划": str(slot_dir / "assembled.md")},
        ))

        assert result.startswith("## status")
        assert calls[-1]["tool_choice"] == {
            "type": "function",
            "function": {"name": "write_file"},
        }
        assert "上游已提供经验缓存" in calls[-1]["messages"][-1]["content"]
        trace = (slot_dir / "trace.jsonl").read_text(encoding="utf-8")
        assert '"cache_present": true' in trace

    def test_intermediate_text_loop_aborts_before_exhausting_attempts(self, tmp_path):
        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)
        calls = []

        async def fake_stream(provider, messages, **kwargs):
            calls.append({"messages": list(messages), **kwargs})
            return {
                "content": "这是一段中间分析，不包含目标文件结构，也没有调用 write_file。" * 4,
                "reasoning_content": "",
                "tool_calls": None,
                "finish_reason": "stop",
            }

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("design", "task", slot_id="S6B", skill_override="design_draft_skill"))

        assert result == ""
        assert len(calls) == 10
        assert not (tmp_path / "S6B" / "question.md").exists()
        trace = (tmp_path / "S6B" / "trace.jsonl").read_text(encoding="utf-8")
        assert "abort_intermediate_loop" in trace

    def test_final_review_secondary_output_uses_write_file_only(self, tmp_path):
        scheduler = DocScheduler(FakeGateway(), workspace=tmp_path)
        calls = []
        responses = [
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_write_file_call("final_review.md", "## status\npass", "call_1")],
            },
            {
                "content": "",
                "reasoning_content": "",
                "tool_calls": [_write_file_call("final.md", "## 题目\nT", "call_2")],
            },
        ]

        async def fake_stream(provider, messages, **kwargs):
            calls.append(kwargs)
            return responses.pop(0)

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("final_review", "task", slot_id="S6"))

        assert result == "## status\npass"
        assert (tmp_path / "S6" / "final_review.md").exists()
        assert (tmp_path / "S6" / "final.md").exists()
        assert [t["function"]["name"] for t in calls[1]["tools"]] == ["write_file"]
        assert calls[1]["tool_choice"] == {
            "type": "function",
            "function": {"name": "write_file"},
        }


# ── Orchestration/scheduling separation ─────────────────────────


class FakeAgentSchedulerForOrchestration:
    def __init__(self, workspace):
        self.workspace = Path(workspace)
        self.calls = []

    async def run_agent(
        self,
        role,
        task,
        *,
        slot_id,
        inject_files=None,
        continue_session=False,
        max_tokens=None,
        skill_override=None,
    ):
        self.calls.append({
            "role": role,
            "inject_files": inject_files or {},
            "continue_session": continue_session,
            "max_tokens": max_tokens,
            "skill_override": skill_override,
        })
        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)

        outputs = {
            "outline": ("outline.md", "## status\nready\n\n## 考点\nCache\n\n## 难度目标\nK1=2"),
            "design": (
                "question.md",
                "## status\ndraft\n\n## 题干\n给定缓存系统。\n\n## 选项\n- A: 1\n- B: 2\n- C: 3\n- D: 4\n\n## 设计说明\n覆盖 Cache（§19 design）",
            ),
            "review": ("review.md", "## status\npass\n\n## summary\nOK\n\n## corrections\n无\n\n## detailed_feedback\n通过"),
            "solve": ("solution.md", "## status\nsolved\n\n## 求解过程\n推导过程\n\n## 最终答案\n42"),
            "final_review": ("final_review.md", "## status\npass\n\n## summary\nOK\n\n## corrections\n无\n\n## detailed_feedback\n通过"),
        }
        if role not in outputs:
            return ""
        filename, content = outputs[role]
        (ws / filename).write_text(content, encoding="utf-8")
        return content


class TestDocPipelineOrchestrator:
    def test_orchestrator_runs_without_llm_gateway(self, tmp_path):
        scheduler = FakeAgentSchedulerForOrchestration(tmp_path)
        orchestrator = DocPipelineOrchestrator(scheduler=scheduler, workspace=tmp_path)
        # This test exercises the stable graph path (FakeAgentScheduler handles
        # the stable roles only). Pin the §17 split path OFF so the stable path
        # is under test regardless of the config flag.
        orchestrator._split_design_enabled = False

        result = run_async(orchestrator.run_pipeline("S5", {"slot_id": "S5"}))

        assert result.ok is True
        assert [c["role"] for c in scheduler.calls] == [
            "outline",
            "question_design",
            "design",
            "review",
            "solve",
            "final_review",
        ]
        solve_call = next(c for c in scheduler.calls if c["role"] == "solve")
        assert solve_call["inject_files"]["题目"].endswith("question_public.md")
        public_question = Path(solve_call["inject_files"]["题目"]).read_text(encoding="utf-8")
        assert "## 题干" in public_question
        assert "## 选项" in public_question
        assert "设计说明" not in public_question
        final_text = (tmp_path / "S5" / "final.md").read_text(encoding="utf-8")
        assert "## 题目" in final_text
        assert "42" in final_text

    def test_resume_from_layer5_fails_without_solution(self, tmp_path):
        slot_dir = tmp_path / "S6"
        slot_dir.mkdir()
        (slot_dir / "blueprint.md").write_text("old blueprint", encoding="utf-8")
        (slot_dir / "question.md").write_text(
            "## status\ndraft\n\n## 题干\n计算题。\n\n## 答案\n42",
            encoding="utf-8",
        )

        scheduler = FakeAgentSchedulerForOrchestration(tmp_path)
        orchestrator = DocPipelineOrchestrator(scheduler=scheduler, workspace=tmp_path)
        # start_layer resume is a legacy-path feature; the graph uses
        # pipeline_state.json instead, so disable the graph here to exercise
        # the legacy resume contract.
        orchestrator._use_graph_enabled = False

        result = run_async(orchestrator.run_pipeline(
            "S6",
            {"slot_id": "S6"},
            assembled_experience_doc="fresh assembled blueprint",
            start_layer=5,
        ))

        assert result.ok is False
        assert "solution.md not found" in result.error
        assert (slot_dir / "blueprint.md").read_text(encoding="utf-8") == "fresh assembled blueprint"

    def test_resume_layer4_runs_solve_and_final_review(self, tmp_path):
        slot_dir = tmp_path / "S7"
        slot_dir.mkdir()
        (slot_dir / "blueprint.md").write_text("old blueprint", encoding="utf-8")
        (slot_dir / "question.md").write_text(
            "## status\ndraft\n\n## 题干\n计算题。\n\n## 答案\n42",
            encoding="utf-8",
        )

        scheduler = FakeAgentSchedulerForOrchestration(tmp_path)
        orchestrator = DocPipelineOrchestrator(scheduler=scheduler, workspace=tmp_path)
        # start_layer resume is a legacy-path feature; disable the graph here.
        orchestrator._use_graph_enabled = False

        result = run_async(orchestrator.run_pipeline(
            "S7",
            {"slot_id": "S7"},
            assembled_experience_doc="fresh assembled blueprint",
            start_layer=4,
        ))

        assert result.ok is True
        assert (slot_dir / "blueprint.md").read_text(encoding="utf-8") == "fresh assembled blueprint"
        assert [c["role"] for c in scheduler.calls] == ["solve", "final_review"]


class FakeDualAgentScheduler:
    def __init__(
        self,
        workspace,
        *,
        cp1_statuses=None,
        cp2_statuses=None,
        write_final=True,
    ):
        self.workspace = Path(workspace)
        self.cp1_statuses = list(cp1_statuses or ["pass"])
        self.cp2_statuses = list(cp2_statuses or ["pass"])
        self.write_final = write_final
        self.calls = []

    @staticmethod
    def _next_status(statuses, default):
        return statuses.pop(0) if statuses else default

    async def run_agent(
        self,
        role,
        task,
        *,
        slot_id,
        inject_files=None,
        continue_session=False,
        max_tokens=None,
        target_file=None,
        preserve_existing=False,
        **kwargs,
    ):
        self.calls.append({
            "role": role,
            "task": task,
            "inject_files": inject_files or {},
            "continue_session": continue_session,
            "max_tokens": max_tokens,
            "target_file": target_file,
            "preserve_existing": preserve_existing,
        })
        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)

        if target_file == "question.md":
            content = (
                "## status\n"
                "draft\n\n"
                "## 题干\n"
                "概念题。\n\n"
                "## 子问题\n"
                "### (1) (5分)\n说明。\n\n"
                "## 设计说明\n"
                "覆盖目标知识点。"
            )
        elif target_file == "solution.md":
            content = (
                "## status\n"
                "solved\n\n"
                "## 求解过程\n"
                "概念推理。\n\n"
                "## 最终答案\n"
                "答案。"
            )
        elif target_file == "review.md":
            if "检查点 2" in task:
                status = self._next_status(self.cp2_statuses, "pass")
            else:
                status = self._next_status(self.cp1_statuses, "pass")
            content = (
                f"## status\n{status}\n\n"
                f"## summary\n{status}\n\n"
                "## corrections\n需要最小修改\n\n"
                "## detailed_feedback\n表述修正建议\n\n"
                "## routing_feedback\n请修正对应位置。"
            )
        elif target_file == "final.md":
            if not self.write_final:
                return ""
            content = "## 题目\n概念题。\n\n## 答案\n答案。"
        else:
            return ""

        (ws / target_file).write_text(content, encoding="utf-8")
        return content


class TestPublicQuestionView:
    """Verify _write_public_question_view isolates solver from design notes."""

    def test_strips_design_notes(self, tmp_path):
        question = tmp_path / "question.md"
        question.write_text(
            "## status\ndraft\n\n"
            "## 题干\n某计算机主频500MHz。\n\n"
            "## 选项\nA. 8ms\nB. 12ms\n\n"
            "## 设计说明\n干扰项A基于遗漏25%指令。正确答案12ms。\n\n"
            "## 子问题\n无",
            encoding="utf-8",
        )
        from core_new.doc_pipeline.orchestrator import DocPipelineOrchestrator
        public_path = DocPipelineOrchestrator._write_public_question_view(question)
        public = public_path.read_text(encoding="utf-8")

        assert "## 题干" in public
        assert "500MHz" in public
        assert "## 选项" in public
        assert "12ms" in public  # option value, not answer
        assert "设计说明" not in public
        assert "干扰项" not in public
        assert "正确答案" not in public

    def test_preserves_ascii_art_and_code_blocks(self, tmp_path):
        question = tmp_path / "question.md"
        question.write_text(
            "## status\ndraft\n\n"
            "## 题干\n"
            "示意图如下：\n```\n┌─────┐\n│ CPU │\n└─────┘\n```\n请回答问题。\n\n"
            "## 子问题\n(1) 计算字段位数\n\n"
            "## 设计说明\n参数选择：主频500MHz",
            encoding="utf-8",
        )
        from core_new.doc_pipeline.orchestrator import DocPipelineOrchestrator
        public_path = DocPipelineOrchestrator._write_public_question_view(question)
        public = public_path.read_text(encoding="utf-8")

        assert "┌─────┐" in public
        assert "字段位数" in public
        assert "设计说明" not in public
        assert "参数选择" not in public

    def test_comprehensive_question_public_has_sub_questions(self, tmp_path):
        question = tmp_path / "question.md"
        question.write_text(
            "## status\ndraft\n\n"
            "## 题干\n已知R1=0001H, R2=7FFFH。\n\n"
            "## 子问题\n(1) 写出真值\n(2) 计算R3并判断CF/OF\n\n"
            "## 设计说明\nR1=0001H是种子值，R2=7FFFH是最大正数。",
            encoding="utf-8",
        )
        from core_new.doc_pipeline.orchestrator import DocPipelineOrchestrator
        public_path = DocPipelineOrchestrator._write_public_question_view(question)
        public = public_path.read_text(encoding="utf-8")

        assert "0001H" in public
        assert "CF/OF" in public
        assert "设计说明" not in public
        assert "种子值" not in public



    def test_concept_question_marks_code_skipped_without_code_exec_ok(self, tmp_path):
        scheduler = FakeDualAgentScheduler(
            tmp_path,
            cp1_statuses=["pass"],
            cp2_statuses=["pass"],
        )
        orchestrator = DualAgentOrchestrator(scheduler=scheduler, workspace=tmp_path)

        result = run_async(orchestrator.run_pipeline("D1", assembled_doc="blueprint"))

        assert result.ok is True
        assert result.review_status == "pass"
        assert result.code_skipped is True
        assert result.code_exec_ok is False

    def test_cp2_question_error_requires_cp1_re_review_to_pass(self, tmp_path):
        scheduler = FakeDualAgentScheduler(
            tmp_path,
            cp1_statuses=["pass", "needs_fix", "needs_fix", "needs_fix"],
            cp2_statuses=["question_error"],
        )
        orchestrator = DualAgentOrchestrator(scheduler=scheduler, workspace=tmp_path)

        result = run_async(orchestrator.run_pipeline("D2", assembled_doc="blueprint"))

        assert result.ok is False
        assert "CP1 re-review still needs_fix" in result.error
        assert any(
            call["target_file"] == "question.md" and call["preserve_existing"]
            for call in scheduler.calls
        )

    def test_expression_fix_requires_creator_final_output(self, tmp_path):
        scheduler = FakeDualAgentScheduler(
            tmp_path,
            cp1_statuses=["pass"],
            cp2_statuses=["expression_fix"],
            write_final=False,
        )
        orchestrator = DualAgentOrchestrator(scheduler=scheduler, workspace=tmp_path)

        result = run_async(orchestrator.run_pipeline("D3", assembled_doc="blueprint"))

        assert result.ok is False
        assert "final.md for expression_fix" in result.error


class TestContextRegistry:
    def test_resolve_for_role_honors_provider_phases(self, tmp_path):
        slot_dir = tmp_path / "S8"
        slot_dir.mkdir()
        (slot_dir / "review.md").write_text("review", encoding="utf-8")

        registry = ContextRegistry()
        registry.register(FileProvider(ProviderDef(
            name="review_comments",
            type="file",
            label="审核意见",
            phases=[4],
            path_pattern="{workspace}/{slot_id}/review.md",
        )))
        registry.register(InlineProvider(ProviderDef(
            name="experience_doc",
            type="inline",
            label="经验文档",
            phases=[1, 2],
        )))
        registry.set_role_binding("debug", ["review_comments", "experience_doc"])

        phase2 = run_async(registry.resolve_for_role(
            "debug",
            tmp_path,
            "S8",
            2,
            runtime_args={"experience_doc": "inline"},
        ))
        phase4 = run_async(registry.resolve_for_role(
            "debug",
            tmp_path,
            "S8",
            4,
            runtime_args={"experience_doc": "inline"},
        ))

        assert phase2 == {"经验文档": "inline"}
        assert phase4 == {"审核意见": str(slot_dir / "review.md")}


class TestRunSlotCompositionArtifacts:
    def test_outline_parser_preserves_machine_contract_codes(self):
        outline = (
            "# 试卷大纲\n\n"
            "## Q12\n\n"
            "### 机器契约\n"
            "```yaml\n"
            "target_subject: 计算机组成原理\n"
            "target_family: CO-1 > 计算机系统概述\n"
            "primary_target_name: 性能指标\n"
            "difficulty_level: 3\n"
            "k_target: K2\n"
            "difficulty_rationale: 常规计算\n"
            "examination_mode: 计算型\n"
            "```\n"
        )

        blueprint = _parse_outline_to_blueprint(outline, {"Q12": {"question_type": "single_choice"}})

        assert blueprint["slots"][0].target_family == "CO-1 > 计算机系统概述"

    def test_extracts_translated_cross_subject_knowledge_graph(self):
        section = _extract_knowledge_graph_section("数据结构-5 > 树与二叉树")

        assert "## 5. 树与二叉树" in section
        assert "二叉树" in section

    def test_parse_final_md_single_choice_for_export(self):
        final_md = (
            "## 题目\nCache 命中率为多少？\n\n"
            "## 选项\nA. 25%\nB. 50%\nC. 75%\nD. 100%\n\n"
            "## 求解过程\n逐一计算四个选项。\n\n"
            "## 答案\n正确答案：C\n\n"
            "## 设计说明\n覆盖 Cache"
        )

        data = _extract_structured_fields_from_final_md(final_md, "Q12")

        assert data["stem"] == "Cache 命中率为多少？"
        assert data["option_A"] == "25%"
        assert data["option_D"] == "100%"
        assert data["correct_answer"] == "C"
        assert "逐一计算" in data["explanation"]

    def test_parse_final_md_comprehensive_for_export(self):
        final_md = (
            "## 题目\n给定页表和访问序列。\n\n"
            "## 子问题\n### (1) (3分)\n计算缺页次数。\n\n### (2) (4分)\n计算平均访问时间。\n\n"
            "## 求解过程\n逐步模拟。\n\n"
            "## 答案\n(1) 3 次\n(2) 120 ns"
        )

        data = _extract_structured_fields_from_final_md(final_md, "Q43")

        assert data["question_type"] == "comprehensive"
        assert len(data["sub_questions"]) == 2
        assert "(1)" in data["sub_questions"][0]
        assert data["answer"].startswith("(1) 3")

    def test_run_composition_passes_slot_filter_to_generate(self, monkeypatch, tmp_path):
        import compose.compose_runner as compose_runner
        import compose.generate_runner as generate_runner
        import compose.cli as cli_mod

        captured = {}

        async def fake_compose(
            gateway,
            slot_templates,
            experience_cards,
            user_requirements,
            slot_ids=None,
            output_dir="docs",
            model_routing=None,
        ):
            captured["compose_slot_ids"] = slot_ids
            return {"status": "ok", "compose_dir": str(tmp_path / "compose")}

        async def fake_generate(
            gateway,
            compose_dir,
            output_dir="docs",
            model_routing=None,
            slot_filter=None,
            resume_from=1,
            run_id=None,
        ):
            captured["generate_slot_filter"] = slot_filter
            return {"status": "ok"}

        monkeypatch.setattr(compose_runner, "run_compose", fake_compose)
        monkeypatch.setattr(generate_runner, "run_generate", fake_generate)

        result = run_async(cli_mod.run_composition(
            None,
            {"Q12": {}},
            {},
            "requirements",
            slot_ids=["Q12"],
            output_dir=str(tmp_path),
        ))

        assert result["status"] == "ok"
        assert captured["compose_slot_ids"] == ["Q12"]
        assert captured["generate_slot_filter"] == ["Q12"]

    def test_run_compose_removes_stale_assembled_docs(self, monkeypatch, tmp_path):
        import compose.compose_runner as compose_runner
        import compose.artifact_store as artifact_store

        compose_dir = tmp_path / "compose"
        compose_dir.mkdir()
        stale = compose_dir / "Q99_assembled.md"
        stale.write_text("stale", encoding="utf-8")

        async def fake_compose_paper(gateway, templates, user_requirements, model_routing=None, exp_dir="data/slot_experiences"):
            return "# outline", {
                "total_questions": 1,
                "slots": [
                    {
                        "slot_id": "Q12",
                        "target_subject": "计算机组成原理",
                        "target_family": "CO-1",
                        "primary_target_name": "性能指标",
                        "target_difficulty": 3,
                        "examination_mode": "计算型",
                    }
                ],
            }

        monkeypatch.setattr(compose_runner, "compose_paper", fake_compose_paper)
        monkeypatch.setattr(
            artifact_store,
            "assemble_slot_experience_doc",
            lambda *args, **kwargs: "assembled Q12",
        )

        result = run_async(compose_runner.run_compose(
            None,
            {"Q12": {"question_type": "single_choice"}},
            {},
            "requirements",
            slot_ids=["Q12"],
            output_dir=str(tmp_path),
        ))

        assert result["status"] == "ok"
        assert not stale.exists()
        assert (compose_dir / "Q12_assembled.md").read_text(encoding="utf-8") == "assembled Q12"


# ── Gateway streaming infrastructure ────────────────────────────


class TestGatewayStreamChat:
    def test_vllm_preserve_thinking_extra_body(self):
        provider = RemoteAPIProvider(
            model_name="qwen-test",
            api_base_url="http://127.0.0.1:8000/v1",
            api_key="EMPTY",
            thinking_control_method="chat_template_kwargs",
            preserve_thinking=True,
        )

        assert provider._extra_body_for_thinking(True) == {
            "chat_template_kwargs": {
                "enable_thinking": True,
                "preserve_thinking": True,
            }
        }
        assert provider._extra_body_for_thinking(False) == {
            "chat_template_kwargs": {"enable_thinking": False}
        }

    def test_stream_chat_does_not_send_thinking_budget_to_remote_provider(self):
        provider = SimpleNamespace(
            model_name="glm-test",
            provider_type="api",
            api_base_url="https://example.invalid/v1",
            thinking_control_method="none",
            sampling_params={"temperature": 1.0, "top_p": 0.95, "top_k": 20},
            client=FakeStreamClient([
                [_stream_chunk(content="ok", finish_reason="stop")]
            ]),
        )
        gateway = LLMGateway.from_provider(provider, name="glm5.1")

        result = run_async(gateway.stream_chat(
            [{"role": "user", "content": "hello"}],
            max_tokens=123,
            thinking_budget=999,
            sampling_overrides={"temperature": 0.2},
        ))

        assert result["content"] == "ok"
        params = provider.client.calls[0]
        assert params["temperature"] == 0.2
        assert params["max_tokens"] == 123
        assert "extra_body" not in params

    def test_stream_chat_retries_retryable_stream_error(self):
        provider = SimpleNamespace(
            model_name="glm-test",
            provider_type="api",
            api_base_url="https://example.invalid/v1",
            thinking_control_method="none",
            sampling_params={},
            client=FakeStreamClient([
                httpx.ReadError("stream dropped"),
                [_stream_chunk(content="ok", finish_reason="stop")],
            ]),
        )
        gateway = LLMGateway.from_provider(
            provider,
            name="glm5.1",
            transport_retry=TransportRetryPolicy(max_attempts=2),
        )
        async def no_wait(attempt):
            return None
        gateway._wait_with_backoff = no_wait

        result = run_async(gateway.stream_chat(
            [{"role": "user", "content": "hello"}],
            max_tokens=50,
        ))

        assert result["content"] == "ok"
        assert len(provider.client.calls) == 2


class TestGatewayGenerateWithTools:
    def test_generate_with_tools_retries_retryable_chat_error(self):
        provider = FakeChatCallProvider([
            httpx.ReadError("chat dropped"),
            {"content": "ok", "reasoning_content": "", "tool_calls": None},
        ])
        gateway = LLMGateway.from_provider(
            provider,
            name="api_vllm",
            transport_retry=TransportRetryPolicy(max_attempts=2),
        )

        async def no_wait(attempt):
            return None

        gateway._wait_with_backoff = no_wait

        result = run_async(gateway.generate_with_tools(
            [{"role": "user", "content": "hello"}],
            tools=[],
            tool_executor=SimpleNamespace(),
            max_tokens=50,
            enable_thinking=False,
            max_rounds=1,
        ))

        assert result.ok is True
        assert result.content == "ok"
        assert len(provider.calls) == 2


# ── AgentMD loader tests ────────────────────────────────────────


class TestAgentLoader:
    def test_loads_online_runtime_agents(self):
        specs = load_agents()
        expected = {
            "outline", "question_design",
            "review", "solve", "final_review",
            "paper_outline",
            "interact", "human_intake",
            # §19 split-focused design agents
            "design", "exam_form",
        }
        assert set(specs.keys()) == expected

    def test_each_spec_has_required_fields(self):
        for name, spec in load_agents().items():
            assert isinstance(spec, AgentSpec)
            assert spec.name == name
            assert spec.output_file.endswith((".md", ".py", ".yaml"))
            assert len(spec.prompt) > 0

    def test_prompt_includes_write_file_suffix(self):
        for name, spec in load_agents().items():
            assert "产出文件" in spec.prompt, f"{name} missing write_file suffix"
            assert spec.output_file in spec.prompt, f"{name} missing filename in suffix"

    def test_multi_turn_agents(self):
        _, _, multi_turn, _, _, _ = get_agent_dicts()
        # §19: design is multi-turn (P1 feedback rounds across form_gate retries).
        assert multi_turn == {"design"}

    def test_thinking_budget_loaded(self):
        _, _, _, thinking, _, _ = get_agent_dicts()
        assert thinking["design"] == 12000

    def test_compat_dicts_match_legacy(self):
        """AgentMD runtime roles match the §19 design-unified pipeline."""
        prompts, output_files, multi_turn, _, _, _ = get_agent_dicts()
        expected_roles = {
            "outline", "question_design",
            "review", "solve", "final_review",
            "paper_outline",
            "interact", "human_intake",
            # §19 split-focused design agents
            "design", "exam_form",
        }
        assert set(prompts.keys()) == expected_roles
        assert set(output_files.keys()) == expected_roles

    def test_parse_custom_agent_md(self, tmp_path):
        agent_file = tmp_path / "test_role.md"
        agent_file.write_text(
            "---\n"
            "name: test_role\n"
            "phase: 1\n"
            "output_file: out.md\n"
            "thinking_budget: 5000\n"
            "multi_turn: false\n"
            "---\n\n"
            "You are a test agent.\n",
            encoding="utf-8",
        )
        spec = _parse_agent_md(agent_file)
        assert spec.name == "test_role"
        assert spec.phase == 1
        assert spec.output_file == "out.md"
        assert spec.thinking_budget == 5000
        # Prompt is now built from behavior layer, not MD body
        assert "按指令直接行动" in spec.prompt
        assert "out.md" in spec.prompt

    def test_parse_rejects_missing_frontmatter(self, tmp_path):
        bad_file = tmp_path / "bad.md"
        bad_file.write_text("No frontmatter here", encoding="utf-8")
        with pytest.raises(ValueError, match="no valid YAML frontmatter"):
            _parse_agent_md(bad_file)


# ── Graph routing + code-as-truth (spec §15) ────────────────────────


class _GraphTestScheduler:
    """Scheduler that writes controlled artifacts so graph routing can be
    asserted deterministically.

    - question_sc / question_comp write a stem-only question.md
    - solve writes solve.py (solver owns problem-solving code)
    - review / final_review statuses are configurable
    - solve agent always writes solution.md (post-exec assembly)
    """

    def __init__(self, workspace, *, review_status="pass", final_status="pass",
                 solve_py=None, conceptual=False):
        self.workspace = Path(workspace)
        self.calls = []
        self.review_status = review_status
        self.final_status = final_status
        self.solve_py = solve_py or (
            "print('正确: 10')\nprint('干扰1: 11')\nprint('干扰2: 12')\nprint('干扰3: 13')\n"
        )
        self.conceptual = conceptual

    async def run_agent(self, role, task, *, slot_id, inject_files=None,
                        continue_session=False, max_tokens=None, skill_override=None):
        self.calls.append({"role": role})
        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)

        if role == "outline":
            (ws / "outline.md").write_text(
                "## status\nready\n\n## 考点\nCache\n\n## 难度目标\nK1=2",
                encoding="utf-8",
            )
        elif role == "question_design":
            # design card is optional / non-blocking; write a minimal stub
            (ws / "design_card.md").write_text(
                "## status\nready\n\n## blueprint_contract\nCache", encoding="utf-8",
            )
        elif role == "design":
            (ws / "question.md").write_text(
                "## status\ndraft\n\n## 题干\n计算题。\n\n## 设计说明\n§19 design",
                encoding="utf-8",
            )
        elif role == "review":
            (ws / "review.md").write_text(
                f"## status\n{self.review_status}\n\n## summary\nOK\n\n## corrections\n无",
                encoding="utf-8",
            )
        elif role == "solve":
            if not self.conceptual:
                (ws / "solve.py").write_text(self.solve_py, encoding="utf-8")
            (ws / "solution.md").write_text(
                "## status\nsolved\n\n## 求解过程\n基于 exec 输出\n\n## 最终答案\n10",
                encoding="utf-8",
            )
        elif role == "final_review":
            (ws / "final_review.md").write_text(
                f"## status\n{self.final_status}\n\n## summary\nOK\n\n## corrections\n无\n\n## routing_feedback\n修一下",
                encoding="utf-8",
            )
        return ""


class TestPipelineGraphRouting:
    def _orch(self, scheduler, tmp_path):
        orch = DocPipelineOrchestrator(scheduler=scheduler, workspace=tmp_path)
        # graph is the default path now; pin it on explicitly.
        orch._use_graph_enabled = True
        # These tests exercise the STABLE graph (question/form_gate/solve).
        # Pin the §17 split-design path OFF regardless of the config flag so
        # the stable path is what's under test here.
        orch._split_design_enabled = False
        return orch

    def test_standard_graph_runs_full_path_and_assembles_result(self, tmp_path):
        sched = _GraphTestScheduler(tmp_path)
        orch = self._orch(sched, tmp_path)

        result = run_async(orch.run_pipeline("G1", {"slot_id": "G1"}))

        assert result.ok is True
        roles = [c["role"] for c in sched.calls]
        # §19: outline → design_card → design → form_gate → solve → final
        assert roles == [
            "outline", "question_design", "design", "review", "solve", "final_review",
        ]
        # code-as-truth: orchestrator exec'd solver's solve.py → solve_output.txt
        assert (tmp_path / "G1" / "solve_output.txt").exists()
        # final.md assembled
        assert (tmp_path / "G1" / "final.md").exists()

    def test_conceptual_graph_skips_solve_and_final(self, tmp_path):
        sched = _GraphTestScheduler(tmp_path, conceptual=True)
        orch = self._orch(sched, tmp_path)

        result = run_async(orch.run_pipeline(
            "G2", {"slot_id": "G2", "complexity": "conceptual"}
        ))

        assert result.ok is True
        roles = [c["role"] for c in sched.calls]
        # §19 conceptual: outline → design_card → design → done.
        # No form_gate/solve/final review (graph routes design → done for conceptual).
        assert roles == ["outline", "question_design", "design"]
        assert "review" not in roles
        assert "solve" not in roles
        assert "final_review" not in roles

    def test_solve_failure_is_terminal_no_back_route(self, tmp_path):
        # §19.5: exec failure = code bug, solver self-retries internally
        # (context-clear + rerun, cap=1), then escalates to a hard failure.
        # solve emits ``failed`` (terminal) — never routes back to design.
        bad_solve = "raise RuntimeError('boom')\n"
        sched = _GraphTestScheduler(tmp_path, solve_py=bad_solve)
        orch = self._orch(sched, tmp_path)

        result = run_async(orch.run_pipeline("G3", {"slot_id": "G3"}))

        state = json.loads((tmp_path / "G3" / "pipeline_state.json").read_text())
        solve_signals = [h["signal"] for h in state["history"] if h["node"] == "solve"]
        # §19: solve never emits code_error to the graph; on exhaustion it
        # escalates to a failed result. No back-route to design.
        assert "code_error" not in solve_signals
        assert result.ok is False
        # design is NOT revisited because of solve failure (§19: no back-route).
        assert state["visit_counts"].get("design", 0) <= 1
        # and no final.md should be assembled for a failed slot
        assert not (tmp_path / "G3" / "final.md").exists()

    def test_solve_failure_on_missing_correct_is_terminal(self, tmp_path):
        # §19.5: solve.py that raises at exec → solver self-retries, then
        # escalates to failure. No code_error back-route to design.
        bad_exec = "raise RuntimeError('no correct answer computed')\n"
        sched = _GraphTestScheduler(tmp_path, solve_py=bad_exec)
        orch = self._orch(sched, tmp_path)

        result = run_async(orch.run_pipeline("G4", {"slot_id": "G4"}))

        state = json.loads((tmp_path / "G4" / "pipeline_state.json").read_text())
        solve_signals = [h["signal"] for h in state["history"] if h["node"] == "solve"]
        assert "code_error" not in solve_signals
        # B1: never solved → must report failure.
        assert result.ok is False

    def test_solve_succeeds_with_only_correct_no_distractors(self, tmp_path):
        # §17.5: solve.py outputs ONLY the correct answer (no error algorithms,
        # no distractor values). This must succeed at the solve stage —
        # distractor distinctness is verified later, not here.
        correct_only = "print('正确: 10')\n"
        sched = _GraphTestScheduler(tmp_path, solve_py=correct_only)
        orch = self._orch(sched, tmp_path)

        run_async(orch.run_pipeline("G5", {"slot_id": "G5"}))

        state = json.loads((tmp_path / "G5" / "pipeline_state.json").read_text())
        solve_signals = [h["signal"] for h in state["history"] if h["node"] == "solve"]
        # solve succeeded (correct answer present) — no code_error from solve.
        assert "success" in solve_signals


class TestEvidenceSolverCodeAsTruth:
    def test_behavior_file_is_code_as_truth(self):
        """behavior/evidence_solver.md must carry the §18 solve = problem-solving
        code contract: solver writes solve.py, brief-think-then-code, fix code
        never stem (discipline ②), no DAG/parameter-search, only correct."""
        from core_new.doc_pipeline.agent_loader import _load_behavior_file
        text = _load_behavior_file("evidence_solver")

        # §18.6: brief-think-then-code is the solve discipline.
        assert "brief" in text
        # §18.2 discipline ②: exec error → fix solve.py, never the stem.
        assert "绝不改题干" in text or "不得改题干" in text
        assert "code_error" in text
        # §18.3: solve.py is problem-solving code, only correct answer.
        assert "解题代码" in text
        assert "只算正确" in text
        assert "错误算法" in text
        # distractors are NOT solve's job (choice options assembled in design 2nd pass)
        assert "干扰项不由 solve 给" in text or "干扰值不由 solve" in text
        # §18.3: no DAG / parameter search over-architecture.
        assert "参数搜索" in text  # mentioned as forbidden
        # legacy anti-patterns explicitly gone
        assert "参数搜索仅作为兜底" not in text
        assert "不得为了匹配选项而枚举搜索参数" not in text

    def test_solve_system_prompt_resolves_contradiction(self):
        """The assembled solve prompt (CORE + behavior + body) must carry the
        §18 solve = problem-solving code contract and must NOT carry legacy
        DAG / stem-edit / parameter-search endorsement."""
        prompt = AGENT_PROMPTS["solve"]
        # §18 contract tokens
        assert "brief" in prompt
        assert "解题代码" in prompt
        assert "不得改题干" in prompt or "绝不改题干" in prompt
        assert "code_error" in prompt
        # §18.3: DAG/parameter-search over-architecture purged
        assert "参数搜索" in prompt  # mentioned as "not this"
        # legacy contradictions purged
        assert "参数搜索仅作为兜底" not in prompt
        assert "不得为了匹配选项而枚举搜索参数" not in prompt


# ── §17 split-focused design architecture ──────────────────────────


class _SplitTestScheduler:
    """Scheduler for the §19 split-design graph. Handles roles:
    exam_form, design (P1 draft / P2 finalize), (+ outline/design_card/
    review/solve/final_review). design P1 writes question.md (stem + params);
    solve writes problem-solving code; design P2 appends options / fills back.
    """

    def __init__(self, workspace, *, review_status="pass", final_status="pass",
                 solve_py=None, conceptual=False, question_type="single_choice"):
        self.workspace = Path(workspace)
        self.calls = []
        self.review_status = review_status
        self.final_status = final_status
        self.solve_py = solve_py or "print('正确: 10')\n"
        self.conceptual = conceptual
        self.question_type = question_type

    async def run_agent(self, role, task, *, slot_id, inject_files=None,
                        continue_session=False, max_tokens=None, skill_override=None):
        # §19: both design P1 and P2 arrive as role="design"; skill_override
        # distinguishes draft (P1) from finalize (P2). Record a synthetic role
        # tag so tests can assert the two-pass sequence.
        tag = role
        if role == "design" and skill_override == "design_finalize_skill":
            tag = "design2"
        elif role == "design":
            tag = "design"
        self.calls.append({"role": tag})
        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)

        if role == "outline":
            (ws / "outline.md").write_text(
                "## status\nready\n\n## 考点\nCache\n\n## 难度目标\nK1=2", encoding="utf-8",
            )
        elif role == "question_design":
            (ws / "design_card.md").write_text(
                "## status\nready\n\n## blueprint_contract\nCache", encoding="utf-8",
            )
        elif role == "exam_form":
            (ws / "exam_form.md").write_text(
                "## status\ndraft\n\n## examination_form\n多步串行推演\n\n## k_radar\nK3: 4",
                encoding="utf-8",
            )
        elif role == "design" and skill_override == "design_finalize_skill":
            # §19 design P2: choice → append options; comprehensive → fill back.
            if self.question_type != "comprehensive":
                q = ws / "question.md"
                cur = q.read_text(encoding="utf-8") if q.exists() else ""
                q.write_text(cur + "\n\n## 选项\nA. 10\nB. 11\nC. 12\nD. 13\n", encoding="utf-8")
        elif role == "design":
            # §19 design P1: writes question.md (stem + experience-value params).
            (ws / "question.md").write_text(
                "## status\ndraft\n\n## 题干\n题干 + 经验值参数。\n\n## 设计说明\n骨架复用，大胆不验证",
                encoding="utf-8",
            )
        elif role == "review":
            (ws / "review.md").write_text(
                f"## status\n{self.review_status}\n\n## summary\nOK\n\n## corrections\n无",
                encoding="utf-8",
            )
        elif role == "solve":
            # §18/§19: the solver writes solve.py (problem-solving code) + solution.md.
            if not self.conceptual:
                (ws / "solve.py").write_text(self.solve_py, encoding="utf-8")
            (ws / "solution.md").write_text(
                "## status\nsolved\n\n## 求解过程\n基于 exec\n\n## 最终答案\n10", encoding="utf-8",
            )
        elif role == "final_review":
            (ws / "final_review.md").write_text(
                f"## status\n{self.final_status}\n\n## summary\nOK\n\n## corrections\n无",
                encoding="utf-8",
            )
        return ""


class TestSplitDesignGraph:
    def _orch(self, scheduler, tmp_path):
        orch = DocPipelineOrchestrator(scheduler=scheduler, workspace=tmp_path)
        orch._use_graph_enabled = True
        orch._split_design_enabled = True  # §17 split path on
        return orch

    def test_split_choice_runs_full_split_path(self, tmp_path):
        sched = _SplitTestScheduler(tmp_path)
        orch = self._orch(sched, tmp_path)

        result = run_async(orch.run_pipeline("SP1", {"slot_id": "SP1"}))

        assert result.ok is True
        roles = [c["role"] for c in sched.calls]
        # §19: outline → design_card → exam_form → design(P1) → form_gate
        #        → solve → design(P2) → final
        assert roles == [
            "outline", "question_design", "exam_form", "design",
            "review", "solve", "design2", "final_review",
        ]
        # design P2 appended A/B/C/D options
        q = (tmp_path / "SP1" / "question.md").read_text(encoding="utf-8")
        assert "## 选项" in q
        # final.md assembled
        assert (tmp_path / "SP1" / "final.md").exists()

    def test_split_conceptual_short_circuits_after_skeleton(self, tmp_path):
        sched = _SplitTestScheduler(tmp_path, conceptual=True)
        orch = self._orch(sched, tmp_path)

        result = run_async(orch.run_pipeline(
            "SP2", {"slot_id": "SP2", "complexity": "conceptual"}
        ))

        assert result.ok is True
        roles = [c["role"] for c in sched.calls]
        # §19 conceptual: outline → design_card → exam_form → design(P1) → done
        assert roles == ["outline", "question_design", "exam_form", "design"]
        assert "solve" not in roles
        assert "design2" not in roles
        assert "final_review" not in roles

    def test_split_comprehensive_skips_distractor_assembly(self, tmp_path):
        # Comprehensive questions have no distractor step — correct fills back
        # the symbolic stem. The distractor_assembly graph node is a no-op for
        # comprehensive (it short-circuits at the node level, never calling the
        # distractor agent) and routes straight to final.
        sched = _SplitTestScheduler(tmp_path, question_type="comprehensive")
        orch = self._orch(sched, tmp_path)

        result = run_async(orch.run_pipeline(
            "SP3", {"slot_id": "SP3", "question_type": "comprehensive"}
        ))

        assert result.ok is True
        roles = [c["role"] for c in sched.calls]
        # §19: comprehensive reaches final via design2 (P2 fills back, no options)
        assert "design2" in roles
        assert "final_review" in roles
        q = (tmp_path / "SP3" / "question.md").read_text(encoding="utf-8")
        assert "## 选项" not in q

    def test_split_solve_failure_is_terminal_no_back_route(self, tmp_path):
        # §19.5: solve exec failure = code bug; solver self-retries then
        # escalates to failure. No code_error back-route to design.
        bad_solve = "raise RuntimeError('boom')\n"
        sched = _SplitTestScheduler(tmp_path, solve_py=bad_solve)
        orch = self._orch(sched, tmp_path)

        result = run_async(orch.run_pipeline("SP4", {"slot_id": "SP4"}))

        state = json.loads((tmp_path / "SP4" / "pipeline_state.json").read_text())
        solve_signals = [h["signal"] for h in state["history"] if h["node"] == "solve"]
        assert "code_error" not in solve_signals
        # design is NOT revisited because of solve failure (§19: no back-route).
        assert state["visit_counts"].get("design", 0) <= 1
        # B1: never solved → failure
        assert result.ok is False

    def test_split_solver_writes_solve_py_after_design(self, tmp_path):
        # §19: the solver writes solve.py (problem-solving code) after
        # design P1 has produced the stem and experience-value params.
        sched = _SplitTestScheduler(tmp_path)
        orch = self._orch(sched, tmp_path)

        result = run_async(orch.run_pipeline("SP5", {"slot_id": "SP5"}))

        assert result.ok is True
        # solve.py produced by the solver role and exec'd → solve_output.txt
        assert (tmp_path / "SP5" / "solve.py").exists()
        assert (tmp_path / "SP5" / "solve_output.txt").exists()
        roles = [c["role"] for c in sched.calls]
        assert roles.index("design") < roles.index("solve")


class TestSplitDesignAgents:
    def test_design_and_exam_form_agents_load(self):
        # §19: design (dual-pass) + exam_form carry the split-design contract.
        for role in ("exam_form", "design"):
            assert role in AGENT_PROMPTS, f"{role} agent not loaded"
        ef = AGENT_PROMPTS["exam_form"]
        assert "考察形式" in ef and "判断任务" in ef
        d = AGENT_PROMPTS["design"]
        # §19 design focuses on experience-value design (no solve.py ownership).
        assert "经验值" in d
        assert "大胆" in d  # discipline ①: bold design, no verify

    def test_design_skills_carry_pass_contracts(self):
        # §19: design runs two passes; each skill is loaded by name at runtime.
        from core_new.doc_pipeline.scheduler import _load_skill_by_name
        draft = _load_skill_by_name("design_draft_skill")
        finalize = _load_skill_by_name("design_finalize_skill")
        # P1 (draft): experience-value params, no solve.py, no options.
        assert "经验值" in draft
        assert "solve.py" not in draft
        assert "§17.6" in draft and "条件融合" in draft  # fusion capability preserved
        # P2 (finalize): option design / fill-back, no recompute.
        assert "干扰" in finalize
        assert "不重算" in finalize

    def test_solve_agent_carries_19_disciplines(self):
        # §18/§19: solve = problem-solving code. The solver writes solve.py, execs,
        # fixes the CODE (never the stem, discipline ②), brief-think-then-code.
        prompt = AGENT_PROMPTS["solve"]
        assert "brief" in prompt  # brief-think-then-code
        assert "解题代码" in prompt  # §18.3: not a DAG/parameter search
        assert "绝不改题干" in prompt or "不得改题干" in prompt  # discipline ②
        # the solver writes solve.py (edit_file present for fixing the code)
        tools = ROLE_REQUIRED_TOOLS.get("solve", [])
        assert "write_file" in tools and "exec_file" in tools and "edit_file" in tools

    def test_split_flag_resolves_from_config_and_can_be_pinned(self, tmp_path):
        # The §17 split path is feature-flagged via enable_split_design.
        # Verify the orchestrator resolves the flag from config, and that
        # pinning _split_design_enabled overrides it (so tests can force either
        # path regardless of the config default).
        orch = DocPipelineOrchestrator(scheduler=_SplitTestScheduler(tmp_path), workspace=tmp_path)
        # Reads the config flag (whatever it currently is) — must not error.
        config_value = orch._should_use_split_design()
        assert isinstance(config_value, bool)
        # Pinning overrides the cached config value.
        orch._split_design_enabled = False
        assert orch._should_use_split_design() is False
        orch._split_design_enabled = True
        assert orch._should_use_split_design() is True

    def test_design_has_grep_search_tool(self):
        # §19: design P1 uses grep_search as a coarse fallback (cache-first) to
        # retrieve same-type past papers (analysis, not invention). Without it
        # the agent invents structure → 60k over-thinking (T3 root cause).
        tools = ROLE_REQUIRED_TOOLS.get("design", [])
        assert "grep_search" in tools, (
            "design must have grep_search to retrieve past papers "
            "(强制分析不发明); missing it causes invention→over-thinking"
        )

    def test_design_uses_upstream_cache_before_grep(self):
        # §19: design P1 consumes the upstream retrieval/design cache; grep is
        # only a coarse fallback when that cache is absent. The cache-first
        # discipline lives in the draft skill (loaded at runtime).
        from core_new.doc_pipeline.scheduler import _load_skill_by_name
        prompt = AGENT_PROMPTS["design"]
        draft = _load_skill_by_name("design_draft_skill")
        assert "缓存优先" in draft
        assert "缓存存在则不 grep" in draft
        assert "粗粒度 fallback" in draft
        assert "question_type" in draft

    def test_knowledge_index_filters_by_question_type(self, tmp_path):
        (tmp_path / "choice.md").write_text(
            "## 基本信息\n"
            "- **年份**: 2010  **题位**: Q5  **题型**: 选择题\n"
            "- **知识点**: DS-5 > 5.1 树的基本概念 > 叶结点\n"
            "- **科目**: 数据结构\n\n"
            "## 题干原文\n选择题题干\n",
            encoding="utf-8",
        )
        (tmp_path / "comp.md").write_text(
            "## 基本信息\n"
            "- **年份**: 2016  **题位**: Q42  **题型**: 综合题\n"
            "- **知识点**: DS-5 > 5.1 树的基本概念 > 叶结点\n"
            "- **科目**: 数据结构\n\n"
            "## 题干原文\n综合题题干\n",
            encoding="utf-8",
        )

        idx = KnowledgeIndex(str(tmp_path))
        hits = idx.search(
            ["DS-5", "树的基本概念", "叶结点"],
            subject="数据结构",
            question_type="综合题",
        )

        assert [h.file_name for h in hits] == ["comp.md"]
        assert hits[0].question_type == "综合题"
        assert hits[0].slot_id == "Q42"

    def test_grep_search_tool_supports_question_type_filter(self):
        tool = GrepSearchTool()
        assert "question_type" in tool.parameters["properties"]

        raw = run_async(tool.execute(
            query=["DS-5", "5.1", "树的基本概念", "叶结点"],
            subject="数据结构",
            question_type="综合题",
            max_results=5,
        ))
        payload = json.loads(raw)

        assert payload["ok"] is True
        assert payload["count"] > 0
        assert all("综合" in r["question_type"] for r in payload["results"])
        assert {"year", "slot_id", "subject", "question_type"} <= set(payload["results"][0])
