"""AgentRegistry — wake up individual agents independently.

Allows the review team to route fixes to specific agents without
re-running the full pipeline. Used by HybridSubjectivePipeline's
revision loop:
  fix_target=question → wake up designer
  fix_target=answer   → wake up solver + formatter
  fix_target=rubric   → wake up rubric writer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type

from core_new.blackboard import Blackboard

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry for invoking individual agents by name."""

    _agent_map: Dict[str, Type] = {}

    @classmethod
    def _ensure_loaded(cls):
        if cls._agent_map:
            return
        from core_new.agents.hybrid_subjective_team import (
            QuestionDesignerAgent,
            HybridSolutionFormatter,
            HybridRubricWriter,
            IntentBasedReviewer,
        )
        from core_new.agents.file_code_solver import FileCodeSolverAgent

        cls._agent_map = {
            "designer": QuestionDesignerAgent,
            "solver": FileCodeSolverAgent,
            "formatter": HybridSolutionFormatter,
            "rubric": HybridRubricWriter,
            "reviewer": IntentBasedReviewer,
        }

    @classmethod
    def available_agents(cls) -> list:
        cls._ensure_loaded()
        return list(cls._agent_map.keys())

    @classmethod
    async def invoke(
        cls,
        agent_name: str,
        blackboard: Blackboard,
        gateway,
        **kwargs,
    ) -> Any:
        """Wake up a specific agent and run it.

        Args:
            agent_name: One of "designer", "solver", "formatter", "rubric", "reviewer"
            blackboard: Shared blackboard with input state
            gateway: LLM gateway instance
            **kwargs: Extra args passed to agent constructor (e.g. max_tokens)

        Returns:
            Agent's execution record
        """
        cls._ensure_loaded()

        if agent_name not in cls._agent_map:
            raise ValueError(
                f"Unknown agent '{agent_name}'. Available: {list(cls._agent_map.keys())}"
            )

        agent_cls = cls._agent_map[agent_name]

        # Agents that use BaseAgent interface (designer, formatter, rubric, reviewer)
        if agent_name in ("designer", "formatter", "rubric", "reviewer"):
            agent = agent_cls(gateway, **kwargs)
            record = await agent.execute(blackboard)
            return record

        # FileCodeSolver uses direct solve() interface
        if agent_name == "solver":
            agent = agent_cls(gateway, **kwargs)
            question_draft = blackboard.get("question_design", {}).get("stem", "")
            sub_questions = blackboard.get("question_design", {}).get("sub_questions")
            slot_id = blackboard.get("current_blueprint", {}).get("slot_id", "Q43")

            if isinstance(sub_questions, str):
                import json
                try:
                    sub_questions = json.loads(sub_questions)
                except json.JSONDecodeError:
                    sub_questions = [sub_questions]

            code_solution = await agent.solve(
                question_draft=question_draft,
                sub_questions=sub_questions if sub_questions else None,
                question_type="comprehensive",
                slot_id=slot_id,
            )
            blackboard.put("solver_result", code_solution.to_dict())
            blackboard.put("code_solution", code_solution)
            return code_solution

        raise ValueError(f"Unhandled agent: {agent_name}")

    @classmethod
    async def invoke_fix(
        cls,
        fix_target: str,
        blackboard: Blackboard,
        gateway,
    ) -> Dict[str, Any]:
        """Invoke the right agents based on fix_target from reviewer.

        Args:
            fix_target: "question" (redesign), "answer" (re-solve), "rubric" (re-rubric)
            blackboard: Contains question_design, current_blueprint, etc.
            gateway: LLM gateway instance

        Returns:
            Dict with updated state from invoked agents
        """
        results: Dict[str, Any] = {}

        if fix_target == "question":
            logger.info("Fix target=question: waking up designer + solver + formatter")
            record = await cls.invoke("designer", blackboard, gateway)
            if not record.error:
                results["design"] = blackboard.get("question_design", {})
                await cls.invoke("solver", blackboard, gateway)
                results["code_solution"] = blackboard.get("code_solution")
                await cls.invoke("formatter", blackboard, gateway)
                results["solution"] = blackboard.get("formatted_solution", {})

        elif fix_target == "answer":
            logger.info("Fix target=answer: waking up solver + formatter")
            await cls.invoke("solver", blackboard, gateway)
            results["code_solution"] = blackboard.get("code_solution")
            await cls.invoke("formatter", blackboard, gateway)
            results["solution"] = blackboard.get("formatted_solution", {})

        elif fix_target == "rubric":
            logger.info("Fix target=rubric: waking up rubric writer")
            await cls.invoke("rubric", blackboard, gateway)
            results["rubric"] = blackboard.get("rubric", {})

        else:
            logger.warning("Unknown fix_target: %s", fix_target)

        return results
