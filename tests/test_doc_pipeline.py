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
from core_new.doc_pipeline.orchestrator import DocPipelineOrchestrator
from core_new.doc_pipeline.scheduler import AGENT_PROMPTS, AGENT_OUTPUT_FILES, MULTI_TURN_AGENTS
from core_new.doc_pipeline.scheduler import DocScheduler
from core_new.agent_roles import TransportRetryPolicy
from core_new.llm_gateway import LLMGateway


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

    def test_get_status_missing_file(self):
        with pytest.raises(FileNotFoundError):
            get_doc_status(os.path.join(self.tmpdir, "nonexistent.md"))


# ── Agent prompts tests ──────────────────────────────────────────


class TestAgentPrompts:
    def test_all_roles_have_prompts(self):
        expected_roles = {
            "outline", "question_sc", "question_comp",
            "review", "solve", "final_review",
        }
        assert set(AGENT_PROMPTS.keys()) == expected_roles

    def test_all_roles_have_output_files(self):
        expected_roles = {
            "outline", "question_sc", "question_comp",
            "review", "solve", "final_review",
        }
        assert set(AGENT_OUTPUT_FILES.keys()) == expected_roles

    def test_output_files_have_extensions(self):
        for role, filename in AGENT_OUTPUT_FILES.items():
            assert "." in filename, f"{role} output file '{filename}' has no extension"

    def test_question_roles_share_output_file(self):
        assert AGENT_OUTPUT_FILES["question_sc"] == "question.md"
        assert AGENT_OUTPUT_FILES["question_comp"] == "question.md"

    def test_multi_turn_agents(self):
        assert "question_sc" in MULTI_TURN_AGENTS
        assert "question_comp" in MULTI_TURN_AGENTS

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
                    _write_file_call("outline.md", "## status\ndraft\n\n## 知识点\nCache")
                ],
            }

        scheduler._streaming_chat_call = fake_stream

        result = run_async(scheduler.run_agent("outline", "task", slot_id="S1"))

        assert result.startswith("## status")
        assert (tmp_path / "S1" / "outline.md").read_text(encoding="utf-8") == result
        assert calls[0]["tool_choice"] == {
            "type": "function",
            "function": {"name": "write_file"},
        }

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
    ):
        self.calls.append({
            "role": role,
            "inject_files": inject_files or {},
            "continue_session": continue_session,
            "max_tokens": max_tokens,
        })
        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)

        outputs = {
            "outline": ("outline.md", "## status\nready\n\n## 考点\nCache\n\n## 难度目标\nK1=2"),
            "question_sc": (
                "question.md",
                "## status\ndraft\n\n## 题干\n给定缓存系统。\n\n## 选项\n- A: 1\n- B: 2\n- C: 3\n- D: 4\n\n## 设计说明\n覆盖 Cache",
            ),
            "question_comp": (
                "question.md",
                "## status\ndraft\n\n## 题干\n给定缓存系统。\n\n## 子问题\n### (1) (3分)\n求命中率\n\n## 设计说明\n覆盖 Cache",
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

        result = run_async(orchestrator.run_pipeline("S5", {"slot_id": "S5"}))

        assert result.ok is True
        assert [c["role"] for c in scheduler.calls] == [
            "outline",
            "question_sc",
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

        result = run_async(orchestrator.run_pipeline(
            "S7",
            {"slot_id": "S7"},
            assembled_experience_doc="fresh assembled blueprint",
            start_layer=4,
        ))

        assert result.ok is True
        assert (slot_dir / "blueprint.md").read_text(encoding="utf-8") == "fresh assembled blueprint"
        assert [c["role"] for c in scheduler.calls] == ["solve", "final_review"]


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
            "outline", "question_sc", "question_comp",
            "review", "solve", "final_review",
        }
        assert set(specs.keys()) == expected

    def test_each_spec_has_required_fields(self):
        for name, spec in load_agents().items():
            assert isinstance(spec, AgentSpec)
            assert spec.name == name
            assert spec.output_file.endswith((".md", ".py"))
            assert len(spec.prompt) > 0

    def test_prompt_includes_write_file_suffix(self):
        for name, spec in load_agents().items():
            assert "【强制要求】" in spec.prompt, f"{name} missing write_file suffix"
            assert spec.output_file in spec.prompt, f"{name} missing filename in suffix"

    def test_multi_turn_agents(self):
        _, _, multi_turn, _, _, _ = get_agent_dicts()
        assert multi_turn == {"question_sc", "question_comp"}

    def test_thinking_budget_loaded(self):
        _, _, _, thinking, _, _ = get_agent_dicts()
        assert thinking["question_sc"] == 12000
        assert thinking["question_comp"] == 16000

    def test_compat_dicts_match_legacy(self):
        """AgentMD runtime roles match the current 5-layer pipeline."""
        prompts, output_files, multi_turn, _, _, _ = get_agent_dicts()
        expected_roles = {
            "outline", "question_sc", "question_comp",
            "review", "solve", "final_review",
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
        assert "工具调用智能体" in spec.prompt
        assert "out.md" in spec.prompt

    def test_parse_rejects_missing_frontmatter(self, tmp_path):
        bad_file = tmp_path / "bad.md"
        bad_file.write_text("No frontmatter here", encoding="utf-8")
        with pytest.raises(ValueError, match="no valid YAML frontmatter"):
            _parse_agent_md(bad_file)
