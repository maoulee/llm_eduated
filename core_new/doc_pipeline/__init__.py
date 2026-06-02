"""Document-based 4-layer pipeline for 408 exam question generation.

Usage:
    from core_new.doc_pipeline import DocPipeline

    dp = DocPipeline(gateway=gateway)
    result = await dp.run(slot_id="Q43", slot_data={...})
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core_new.llm_gateway import LLMGateway
from core_new.provider_router import get_routed_gateway

from .scheduler import DocScheduler, DEFAULT_MAX_TOKENS

__all__ = ["DocPipeline"]


class DocPipeline:
    """High-level wrapper over DocScheduler.

    Handles gateway resolution and workspace setup.
    """

    def __init__(
        self,
        gateway: LLMGateway | None = None,
        workspace: str | Path = "workspace",
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        enable_thinking: bool | None = None,
        model_routing: dict[str, str] | None = None,
    ):
        self.gateway = gateway or get_routed_gateway("doc_design")
        self.workspace = Path(workspace)
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        self.model_routing = model_routing

    async def run(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        *,
        experience_card: str = "",
        k_definitions: str = "",
    ) -> dict[str, Any]:
        """Run the full document pipeline for one slot.

        Args:
            slot_id: Slot identifier (e.g. "Q43")
            slot_data: Raw slot data dict
            experience_card: Past exam stems for style reference
            k_definitions: K1-K5 difficulty definitions text

        Returns:
            Result dict with ok, final_content, files, timing, etc.
        """
        scheduler = DocScheduler(
            gateway=self.gateway,
            workspace=self.workspace,
            max_tokens=self.max_tokens,
            enable_thinking=self.enable_thinking,
            model_routing=self.model_routing,
        )
        return await scheduler.run_pipeline(
            slot_id,
            slot_data,
            experience_card=experience_card,
            k_definitions=k_definitions,
        )
