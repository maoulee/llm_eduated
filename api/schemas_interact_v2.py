"""Pydantic schemas for the Interact V2 Web API.

Models for draft display, annotation submission, and session management
in the pruning-based teacher interaction flow.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Draft display models
# ---------------------------------------------------------------------------


class DraftOption(BaseModel):
    """A single option within a draft slot."""

    id: str  # "opt_1_1"
    text: str  # option display text
    cognitive_desc: str = ""  # e.g. "需一步公式推导" (never expose K values)
    status: Literal["unselected", "kept"] = "unselected"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "opt_1_1",
                "text": "对有向无环图执行深度优先搜索，按完成时间递减排序",
                "cognitive_desc": "需理解DFS与拓扑排序的关系",
                "status": "unselected",
            }
        }
    )


class DraftSlot(BaseModel):
    """A question slot within a draft."""

    slot_id: str  # "Q1"
    title: str  # "Q1（选择题·2分）— 拓扑排序"
    options: list[DraftOption]
    annotation: str = ""  # teacher annotation

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slot_id": "Q1",
                "title": "Q1（选择题·2分）— 拓扑排序",
                "options": [
                    {
                        "id": "opt_1_1",
                        "text": "对有向无环图执行深度优先搜索，按完成时间递减排序",
                        "cognitive_desc": "需理解DFS与拓扑排序的关系",
                        "status": "unselected",
                    },
                    {
                        "id": "opt_1_2",
                        "text": "依次删除入度为0的顶点及其出边",
                        "cognitive_desc": "Kahn算法标准描述",
                        "status": "unselected",
                    },
                ],
                "annotation": "",
            }
        }
    )


class DraftData(BaseModel):
    """Complete draft returned to the teacher for review / annotation."""

    draft_id: str
    title: str  # "拓扑排序 — 考察模式草案"
    scenario: Literal["A", "B", "C"] = "A"
    current_round: int = 1  # Scenario C: 1 or 2
    sections: list[DraftSlot]
    raw_md: str = ""  # original markdown for fallback rendering

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "draft_id": "draft_20260610_topo",
                "title": "拓扑排序 — 考察模式草案",
                "scenario": "A",
                "current_round": 1,
                "sections": [
                    {
                        "slot_id": "Q1",
                        "title": "Q1（选择题·2分）— 拓扑排序",
                        "options": [
                            {
                                "id": "opt_1_1",
                                "text": "对有向无环图执行深度优先搜索，按完成时间递减排序",
                                "cognitive_desc": "需理解DFS与拓扑排序的关系",
                                "status": "unselected",
                            },
                        ],
                        "annotation": "",
                    }
                ],
                "raw_md": "# 拓扑排序 — 考察模式草案\n\n## Q1（选择题·2分）...",
            }
        }
    )


# ---------------------------------------------------------------------------
# Annotation submission models (pruning-based)
# ---------------------------------------------------------------------------


class SlotAnnotation(BaseModel):
    """Teacher annotation for a single slot — pruning-based selection."""

    slot_id: str
    kept_options: list[str]  # option_ids the teacher kept (usually just 1)
    removed_options: list[str]  # option_ids the teacher removed
    annotation: str = ""
    modified_text: dict[str, str] = Field(default_factory=dict)  # {option_id: modified text}

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slot_id": "Q1",
                "kept_options": ["opt_1_2"],
                "removed_options": ["opt_1_1"],
                "annotation": "保留Kahn算法描述，删除DFS变体",
                "modified_text": {
                    "opt_1_2": "依次删除当前入度为0的顶点及其所有出边，输出顶点序列"
                },
            }
        }
    )


class AnnotationSubmission(BaseModel):
    """Full annotation submission for all slots in a draft."""

    draft_id: str
    slots: list[SlotAnnotation]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "draft_id": "draft_20260610_topo",
                "slots": [
                    {
                        "slot_id": "Q1",
                        "kept_options": ["opt_1_2"],
                        "removed_options": ["opt_1_1"],
                        "annotation": "保留Kahn算法描述",
                        "modified_text": {},
                    }
                ],
            }
        }
    )


# ---------------------------------------------------------------------------
# Session management models
# ---------------------------------------------------------------------------


class InteractSessionCreate(BaseModel):
    """Request to create a new interact session."""

    provider: str = "api_vllm"  # provider name from config.py
    thinking: bool = False  # enable GLM thinking mode
    ui_mode: Literal["api", "file"] = "api"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider": "api_vllm",
                "thinking": False,
                "ui_mode": "api",
            }
        }
    )


class InteractTurnRequest(BaseModel):
    """Request to send a teacher message within a session."""

    message: str  # teacher message

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "请出3道拓扑排序的题目，覆盖Kahn算法和DFS方法"
            }
        }
    )


class InteractTurnResponse(BaseModel):
    """Response from a single turn in the interact session."""

    response_text: str  # agent text reply
    session_state: Literal["collecting", "reviewing", "confirmed"]
    has_draft: bool = False  # parseable draft available
    has_result: bool = False  # handoff YAML available
    files_written: list[str] = Field(default_factory=list)  # files written this turn

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "response_text": "已为您生成拓扑排序草案，共3题。请查看并标注保留或删除选项。",
                "session_state": "reviewing",
                "has_draft": True,
                "has_result": False,
                "files_written": ["output/draft_topo_20260610.md"],
            }
        }
    )


class InteractSessionInfo(BaseModel):
    """Summary information about an interact session."""

    session_id: str
    state: str
    scenario: str = "unknown"
    provider: str = ""
    created_at: float = 0
    turn_count: int = 0


class AnnotationResponse(BaseModel):
    """Response after submitting an annotation."""

    ok: bool
