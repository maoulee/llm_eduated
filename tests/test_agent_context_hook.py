"""Tests for pull-based context tools and output validation hooks.

Validates:
- list_context / read_context tool handlers
- context store injection via set_context_store
- required_fields validation and repair retry behavior
- context catalog text generation
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core_new.agent_base import AgentConfig, BaseAgent, _get_required_value, _is_empty_value
from core_new.agent_tools import (
    CONTEXT_TOOLS,
    CONTEXT_AWARE_TOOLS,
    ToolExecutor,
    _list_context,
    _read_context,
    set_context_store,
)


# ─── M. Context Tools ─────────────────────────────────────────


class TestContextStore:
    """Validate set_context_store and context tool handlers."""

    def setup_method(self):
        """Reset global context store before each test."""
        set_context_store({})

    def test_m1_list_context_empty(self):
        """Empty store returns info message."""
        result = _list_context()
        parsed = json.loads(result)
        assert "info" in parsed

    def test_m2_list_context_with_catalog(self):
        """list_context returns catalog with descriptions."""
        set_context_store({
            "__catalog__": {
                "design": ("题目设计", True),
                "solver": ("求解结果", False),
            },
        })
        result = _list_context()
        parsed = json.loads(result)
        assert "design" in parsed
        assert "solver" in parsed
        assert parsed["design"] == "题目设计"

    def test_m3_read_context_valid_key(self):
        """read_context returns content for valid key."""
        set_context_store({
            "__catalog__": {"design": ("题目设计", True)},
            "design": {"stem": "某计算机系统..."},
        })
        result = _read_context("design")
        parsed = json.loads(result)
        assert parsed["stem"] == "某计算机系统..."

    def test_m4_read_context_invalid_key(self):
        """read_context returns error for invalid key with available list."""
        set_context_store({
            "__catalog__": {"design": ("题目设计", True)},
        })
        result = _read_context("nonexistent")
        parsed = json.loads(result)
        assert "error" in parsed
        assert "design" in parsed["available"]

    def test_m5_read_context_none_value(self):
        """read_context returns error when value is None."""
        set_context_store({
            "__catalog__": {"design": ("题目设计", False)},
            "design": None,
        })
        result = _read_context("design")
        parsed = json.loads(result)
        assert "error" in parsed

    def test_m6_read_context_truncation(self):
        """read_context truncates content > 8000 chars."""
        set_context_store({
            "__catalog__": {"big": ("大数据", True)},
            "big": {"data": "x" * 10000},
        })
        result = _read_context("big")
        assert len(result) <= 8200  # Allow for JSON overhead

    def test_m7_context_tools_in_context_aware(self):
        """CONTEXT_AWARE_TOOLS includes both SLOT_TOOLS and CONTEXT_TOOLS."""
        names = [t.name for t in CONTEXT_AWARE_TOOLS]
        assert "list_context" in names
        assert "read_context" in names
        assert "read_slot" in names

    def test_m8_tool_executor_dispatches_read_context(self):
        """ToolExecutor can dispatch read_context calls."""
        set_context_store({
            "__catalog__": {"test": ("测试", True)},
            "test": {"value": 42},
        })
        executor = ToolExecutor(CONTEXT_TOOLS)
        result = executor.execute("read_context", {"key": "test"})
        # execute returns a coroutine
        import asyncio
        output = asyncio.get_event_loop().run_until_complete(result)
        parsed = json.loads(output)
        assert parsed["value"] == 42


# ─── N. Context Sources Config ─────────────────────────────────


class TestContextSourcesConfig:
    """Validate context_sources in AgentConfig."""

    def test_n1_default_empty(self):
        """Default context_sources is empty dict."""
        config = AgentConfig(name="test", phase="test")
        assert config.context_sources == {}

    def test_n2_custom_sources(self):
        """Custom context_sources stored correctly."""
        config = AgentConfig(
            name="test",
            phase="test",
            context_sources={
                "design": "题目设计",
                "solver": "求解结果",
            },
        )
        assert "design" in config.context_sources
        assert config.context_sources["solver"] == "求解结果"


# ─── O. Required Fields Validation ─────────────────────────────


class TestRequiredFieldsValidation:
    """Validate required_fields checking in validate_parsed."""

    def _make_agent(self, required_fields):
        """Create a minimal concrete agent with given required_fields."""
        from core_new.agents.final_review_team import FinalFixerAgent

        gw = MagicMock()
        agent = FinalFixerAgent.__new__(FinalFixerAgent)
        config = AgentConfig(
            name="test_agent",
            phase="test",
            required_fields=required_fields,
        )
        agent.config = config
        agent.llm = gw
        agent._memory = []
        from core_new.agent_roles import resolve_execution_policy
        agent.execution_policy = resolve_execution_policy(config.role_type, config.execution_policy)
        return agent

    def test_o1_missing_required_field_fails(self):
        """validate_parsed returns False when required field is missing."""
        agent = self._make_agent(["status", "fix_applied"])
        ok, detail = agent.validate_parsed({"status": "ok"})
        assert not ok
        assert "fix_applied" in detail

    def test_o2_all_required_present_passes(self):
        """validate_parsed returns True when all required fields present."""
        agent = self._make_agent(["status", "fix_applied"])
        ok, detail = agent.validate_parsed({"status": "ok", "fix_applied": "修正了术语"})
        assert ok

    def test_o3_empty_required_value_fails(self):
        """validate_parsed returns False when required field is empty string."""
        agent = self._make_agent(["status"])
        ok, detail = agent.validate_parsed({"status": ""})
        assert not ok

    def test_o4_nested_required_field(self):
        """validate_parsed supports dot-path for nested fields."""
        agent = self._make_agent(["fix_instruction.fix_target"])
        ok, detail = agent.validate_parsed({
            "fix_instruction": {"fix_target": "stem"}
        })
        assert ok

    def test_o5_nested_missing_field(self):
        """validate_parsed catches missing nested field."""
        agent = self._make_agent(["fix_instruction.fix_target"])
        ok, detail = agent.validate_parsed({"fix_instruction": {}})
        assert not ok
        assert "fix_target" in detail

    def test_o6_no_required_fields_nonempty_passes(self):
        """validate_parsed passes when no required_fields and output is non-empty."""
        agent = self._make_agent([])
        ok, detail = agent.validate_parsed({"some": "data"})
        assert ok

    def test_o7_none_value_fails(self):
        """validate_parsed returns False when required field is None."""
        agent = self._make_agent(["status"])
        ok, detail = agent.validate_parsed({"status": None})
        assert not ok


# ─── P. Context Catalog Text ──────────────────────────────────


class TestContextCatalogText:
    """Validate _context_catalog_text method."""

    def _make_agent(self, context_sources):
        from core_new.agents.final_review_team import FinalFixerAgent
        from core_new.agent_roles import resolve_execution_policy

        config = AgentConfig(
            name="test",
            phase="test",
            context_sources=context_sources,
        )
        agent = FinalFixerAgent.__new__(FinalFixerAgent)
        agent.config = config
        agent.llm = MagicMock()
        agent._memory = []
        agent.execution_policy = resolve_execution_policy(config.role_type, config.execution_policy)
        return agent

    def test_p1_empty_sources_no_text(self):
        """No context_sources produces empty catalog text."""
        agent = self._make_agent({})
        assert agent._context_catalog_text() == ""

    def test_p2_sources_produce_catalog(self):
        """context_sources produce formatted catalog text."""
        agent = self._make_agent({
            "design": "题目设计",
            "solver": "求解结果",
        })
        text = agent._context_catalog_text()
        assert "design" in text
        assert "题目设计" in text
        assert "list_context" in text or "read_context" in text

    def test_p3_prepare_context_store(self):
        """_prepare_context_store builds correct store from blackboard."""
        agent = self._make_agent({
            "design": "题目设计",
            "solver": "求解结果",
        })
        blackboard = MagicMock()
        blackboard.get = lambda key: {"stem": "test"} if key == "design" else None

        store = agent._prepare_context_store(blackboard)
        assert store["design"] == {"stem": "test"}
        assert store["solver"] is None
        assert "design" in store["__catalog__"]
