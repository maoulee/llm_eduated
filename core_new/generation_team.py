# core_new/generation_team.py

"""
Multi-agent question generation team for 408 adaptive question generation.

Pipeline:
  ProfileInterpreter → BlueprintPlanner → QuestionWriter
  → SolverVerifier → UserSimulator → GenerationAggregator

Usage:
    from config import get_provider_config
    from llm_providers_new import get_llm_provider
    from core_new.generation_team import GenerationPipeline

    config = get_provider_config("glm5.1")
    provider = get_llm_provider(config)
    pipeline = GenerationPipeline(provider)

    result = await pipeline.generate(profile_info, knowledge_base)
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .generation_prompts import (
    PROFILE_INTERPRETER,
    BLUEPRINT_PLANNER,
    QUESTION_WRITER,
    SOLVER_VERIFIER,
    USER_SIMULATOR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _parse_xml(text: str) -> Optional[Dict[str, Any]]:
    """Extract XML-tagged fields from model output into a dict.

    Handles semicolon-separated lists within tags and provides fallback to JSON.
    Special handling for options with option_A, option_B, option_C, option_D tags.
    Reconstructs nested structures from flattened XML tags.
    """
    result = {}

    # Try XML parsing first
    for m in re.finditer(r'<(\w+)>(.*?)</\w+>', text, re.DOTALL):
        key = m.group(1)
        value = m.group(2).strip()
        # Split semicolon-separated lists
        if ';' in value:
            result[key] = [v.strip() for v in value.split(';') if v.strip()]
        else:
            result[key] = value

    if result:
        # Special handling for options: convert option_A, option_B, option_C, option_D to options dict
        if "option_A" in result or "option_B" in result:
            options = {}
            for opt_key in ["option_A", "option_B", "option_C", "option_D"]:
                if opt_key in result:
                    letter = opt_key.split("_")[1]
                    options[letter] = result.pop(opt_key)
            result["options"] = options

        # Reconstruct primary_target from flattened fields for BlueprintPlanner
        if "primary_target_type" in result or "primary_target_name" in result:
            primary_target = {
                "type": result.pop("primary_target_type", ""),
                "name": result.pop("primary_target_name", ""),
                "description": result.pop("primary_target_description", ""),
            }
            result["primary_target"] = primary_target

        # Reconstruct target_mapping for QuestionWriter
        if "primary_target_hit" in result or "expected_wrong_option" in result:
            target_mapping = {
                "primary_target_hit": result.pop("primary_target_hit", True),
                "expected_wrong_option": result.pop("expected_wrong_option", ""),
                "expected_wrong_reason": result.pop("expected_wrong_reason", ""),
            }
            result["target_mapping"] = target_mapping

        # Convert string "true"/"false" to boolean for known fields
        for bool_field in ["consistent", "unique_answer", "solvable", "primary_target_hit", "matched_expected_failure"]:
            if bool_field in result and isinstance(result[bool_field], str):
                result[bool_field] = result[bool_field].lower() == "true"

        # Convert numeric fields
        for num_field in ["recommended_difficulty", "difficulty", "difficulty_self_assessment"]:
            if num_field in result and isinstance(result[num_field], str):
                try:
                    result[num_field] = int(result[num_field])
                except ValueError:
                    pass

        return result

    # Fallback to JSON parsing for backward compatibility
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        if "```json" in text:
            clean = text.split("```json\n", 1)[1].rsplit("```", 1)[0]
        else:
            start, end = text.find("{"), text.rfind("}")
            clean = text[start:end + 1] if start != -1 and end != -1 else text
        return json.loads(clean)
    except (json.JSONDecodeError, IndexError, TypeError):
        logger.warning("Failed to parse XML and JSON. Raw output: %s", text[:200])
        return None


class ProfileInterpreter:
    """Analyzes user error history and mastery info to create a diagnostic profile."""

    def __init__(self, llm_provider, max_tokens: int = 4096):
        self.llm = llm_provider
        self.max_tokens = max_tokens

    def _build_prompt(self, error_history: str, mastery_info: str, training_goal: str) -> str:
        return PROFILE_INTERPRETER.format(
            error_history=error_history,
            mastery_info=mastery_info,
            training_goal=training_goal,
        )

    async def interpret(self, error_history: str, mastery_info: str, training_goal: str) -> Dict[str, Any]:
        """Generate user profile from error history and mastery info."""
        prompt = self._build_prompt(error_history, mastery_info, training_goal)
        messages = [[{"role": "user", "content": prompt}]]

        results = await self.llm.generate_json_batch(
            messages, max_tokens=self.max_tokens, enable_thinking=True
        )

        result = results[0] if results else None
        if result is None:
            logger.error("ProfileInterpreter returned None")
            return {}

        # Parse XML content from the result
        content = result.get("content", "")
        parsed = _parse_xml(content) if content else result
        return parsed if parsed else result


class BlueprintPlanner:
    """Plans a question blueprint based on user profile and available knowledge."""

    def __init__(self, llm_provider, max_tokens: int = 4096):
        self.llm = llm_provider
        self.max_tokens = max_tokens

    def _build_prompt(self, profile: Dict[str, Any], knowledge_base: List[Dict[str, Any]]) -> str:
        profile_str = json.dumps(profile, ensure_ascii=False, indent=2)
        kb_str = json.dumps(knowledge_base, ensure_ascii=False, indent=2)
        return BLUEPRINT_PLANNER.format(profile=profile_str, knowledge_base=kb_str)

    async def plan(self, profile: Dict[str, Any], knowledge_base: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a question blueprint from profile and knowledge base."""
        prompt = self._build_prompt(profile, knowledge_base)
        messages = [[{"role": "user", "content": prompt}]]

        results = await self.llm.generate_json_batch(
            messages, max_tokens=self.max_tokens, enable_thinking=True
        )

        result = results[0] if results else None
        if result is None:
            logger.error("BlueprintPlanner returned None")
            return {}

        # Parse XML content from the result
        content = result.get("content", "")
        parsed = _parse_xml(content) if content else result
        return parsed if parsed else result


class QuestionWriter:
    """Writes a complete 408-style question based on blueprint."""

    def __init__(self, llm_provider, max_tokens: int = 4096):
        self.llm = llm_provider
        self.max_tokens = max_tokens

    def _build_prompt(self, blueprint: Dict[str, Any], reference_knowledge: List[Dict[str, Any]]) -> str:
        blueprint_str = json.dumps(blueprint, ensure_ascii=False, indent=2)
        ref_str = json.dumps(reference_knowledge, ensure_ascii=False, indent=2)
        return QUESTION_WRITER.format(blueprint=blueprint_str, reference_knowledge=ref_str)

    async def generate(
        self,
        blueprint: Dict[str, Any],
        reference_knowledge: List[Dict[str, Any]],
        revision_instructions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a question from blueprint. Can include revision instructions."""
        prompt = self._build_prompt(blueprint, reference_knowledge)

        if revision_instructions:
            revision_note = "\n\n## 修订要求\n请根据以下反馈修订题目：\n" + "\n".join(f"- {r}" for r in revision_instructions)
            prompt = prompt + revision_note

        messages = [[{"role": "user", "content": prompt}]]

        results = await self.llm.generate_json_batch(
            messages, max_tokens=self.max_tokens, enable_thinking=True
        )

        result = results[0] if results else None
        if result is None:
            logger.error("QuestionWriter returned None")
            return {}

        # Parse XML content from the result
        content = result.get("content", "")
        parsed = _parse_xml(content) if content else result
        return parsed if parsed else result


class SolverVerifier:
    """Verifies a question by solving it independently."""

    def __init__(self, llm_provider, max_tokens: int = 4096):
        self.llm = llm_provider
        self.max_tokens = max_tokens

    def _build_prompt(self, question_json: Dict[str, Any]) -> str:
        question_str = json.dumps(question_json, ensure_ascii=False, indent=2)
        given_answer = question_json.get("answer", "")
        return SOLVER_VERIFIER.format(question=question_str, given_answer=given_answer)

    async def verify(self, question_json: Dict[str, Any]) -> Dict[str, Any]:
        """Solve the question independently and verify consistency."""
        prompt = self._build_prompt(question_json)
        messages = [[{"role": "user", "content": prompt}]]

        results = await self.llm.generate_json_batch(
            messages, max_tokens=self.max_tokens, enable_thinking=True
        )

        result = results[0] if results else None
        if result is None:
            logger.error("SolverVerifier returned None")
            return {}

        # Parse XML content from the result
        content = result.get("content", "")
        parsed = _parse_xml(content) if content else result
        return parsed if parsed else result


class UserSimulator:
    """Simulates a user with specific knowledge gaps answering a question."""

    def __init__(self, llm_provider, max_tokens: int = 4096):
        self.llm = llm_provider
        self.max_tokens = max_tokens

    def _build_prompt(self, profile: Dict[str, Any], question_json: Dict[str, Any]) -> str:
        profile_str = json.dumps(profile, ensure_ascii=False, indent=2)
        question_str = json.dumps(question_json, ensure_ascii=False, indent=2)
        return USER_SIMULATOR.format(profile=profile_str, question=question_str)

    async def simulate(self, profile: Dict[str, Any], question_json: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate user response to the question."""
        prompt = self._build_prompt(profile, question_json)
        messages = [[{"role": "user", "content": prompt}]]

        results = await self.llm.generate_json_batch(
            messages, max_tokens=self.max_tokens, enable_thinking=True
        )

        result = results[0] if results else None
        if result is None:
            logger.error("UserSimulator returned None")
            return {}

        # Parse XML content from the result
        content = result.get("content", "")
        parsed = _parse_xml(content) if content else result
        return parsed if parsed else result


class GenerationAggregator:
    """Aggregates solver and simulator results to make accept/revise/reject decisions."""

    @staticmethod
    def aggregate(
        solver_results: List[Dict[str, Any]],
        simulation_result: Dict[str, Any],
        blueprint: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Aggregate results and determine final status."""
        reasons: List[str] = []
        revision_instructions: List[str] = []

        # Rule 1: If any solver says consistent=False → reject
        for i, solver in enumerate(solver_results):
            if not solver.get("consistent", True):
                return {
                    "status": "reject",
                    "reasons": [f"Solver {i+1} found inconsistency with given answer"],
                    "revision_instructions": [],
                }

        # Rule 2: If any solver says solvable=False → reject
        for i, solver in enumerate(solver_results):
            if not solver.get("solvable", True):
                return {
                    "status": "reject",
                    "reasons": [f"Solver {i+1} found question unsolvable"],
                    "revision_instructions": [],
                }

        # Rule 3: If any solver says unique_answer=False → revise
        for i, solver in enumerate(solver_results):
            if not solver.get("unique_answer", True):
                reasons.append(f"Solver {i+1} found answer not unique")
                revision_instructions.append("Ensure the correct answer is uniquely determined")

        # Rule 4: If ambiguity found → revise
        for i, solver in enumerate(solver_results):
            ambiguity = solver.get("ambiguity_found", "")
            if ambiguity:
                reasons.append(f"Solver {i+1} found ambiguity: {ambiguity}")
                revision_instructions.append(f"Resolve ambiguity: {ambiguity}")

        # Rule 5: If simulation matched expected failure AND solver consistent → accept_candidate
        matched_failure = simulation_result.get("matched_expected_failure", False)
        # Handle distractor_plan as either list (from JSON) or string (from XML)
        distractor_plan = blueprint.get("distractor_plan", [])
        if isinstance(distractor_plan, str):
            # Parse semicolon-separated distractor plan from XML
            # Format: role1:desc1:weakness1;role2:desc2:weakness2
            expected_wrong = ""
            if distractor_plan:
                parts = distractor_plan.split(';')[0] if ';' in distractor_plan else distractor_plan
                if ':' in parts:
                    expected_wrong = parts.split(':')[-1] if parts.count(':') >= 2 else ""
        else:
            expected_wrong = distractor_plan[0].get("targeted_weakness", "") if distractor_plan else ""
        actual_wrong_option = simulation_result.get("simulated_answer", "")
        # Get expected_wrong_option from blueprint's target_mapping if available
        target_mapping = blueprint.get("target_mapping", {})
        if isinstance(target_mapping, dict):
            expected_wrong_option = target_mapping.get("expected_wrong_option", "")
        else:
            expected_wrong_option = blueprint.get("expected_wrong_option", "")

        if matched_failure:
            reasons.append("User simulation matched expected failure pattern")
            if not revision_instructions:
                return {
                    "status": "accept_candidate",
                    "reasons": reasons,
                    "revision_instructions": [],
                }
        else:
            reasons.append("User simulation did NOT match expected failure pattern")
            if expected_wrong_option and actual_wrong_option != expected_wrong_option:
                revision_instructions.append(
                    f"Adjust distractors to make '{expected_wrong_option}' more tempting for users with weakness: {expected_wrong}"
                )
            else:
                revision_instructions.append("Review question design to better target the diagnosed weakness")

        # Rule 6: If we have revision instructions, revise; otherwise accept
        if revision_instructions:
            return {
                "status": "revise",
                "reasons": reasons,
                "revision_instructions": revision_instructions,
            }

        return {
            "status": "accept_candidate",
            "reasons": reasons if reasons else ["All checks passed"],
            "revision_instructions": [],
        }


class GenerationPipeline:
    """Orchestrates the full question generation pipeline."""

    def __init__(self, llm_provider, max_tokens: int = 4096):
        self.llm = llm_provider
        self.max_tokens = max_tokens

        self.profile_interpreter = ProfileInterpreter(llm_provider, max_tokens)
        self.blueprint_planner = BlueprintPlanner(llm_provider, max_tokens)
        self.question_writer = QuestionWriter(llm_provider, max_tokens)
        self.solver_verifier = SolverVerifier(llm_provider, max_tokens)
        self.user_simulator = UserSimulator(llm_provider, max_tokens)

    async def generate(
        self,
        profile_info: Dict[str, Any],
        knowledge_base: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Run the full generation pipeline.

        Args:
            profile_info: dict with error_history, mastery_info, training_goal
            knowledge_base: list of extraction results with knowledge/mechanism info

        Returns:
            dict with all intermediate and final results
        """
        error_history = profile_info.get("error_history", "")
        mastery_info = profile_info.get("mastery_info", "")
        training_goal = profile_info.get("training_goal", "")

        logger.info("Starting generation pipeline for profile: %s", profile_info.get("name", "unknown"))

        # Step 1: ProfileInterpreter
        logger.info("Step 1: ProfileInterpreter")
        profile = await self.profile_interpreter.interpret(error_history, mastery_info, training_goal)
        if not profile:
            return {"error": "ProfileInterpreter failed", "profile_info": profile_info}

        # Step 2: BlueprintPlanner
        logger.info("Step 2: BlueprintPlanner")
        blueprint = await self.blueprint_planner.plan(profile, knowledge_base)
        if not blueprint:
            return {"error": "BlueprintPlanner failed", "profile": profile}

        # Find reference knowledge from knowledge base based on blueprint reference_concept
        ref_concept = blueprint.get("reference_concept", "")
        reference_knowledge = self._find_reference_knowledge(knowledge_base, ref_concept)

        # Step 3: QuestionWriter (initial draft)
        logger.info("Step 3: QuestionWriter (initial draft)")
        question = await self.question_writer.generate(blueprint, reference_knowledge)
        if not question or "stem" not in question:
            return {"error": "QuestionWriter failed", "blueprint": blueprint}

        # Step 4: SolverVerifier
        logger.info("Step 4: SolverVerifier")
        solver_result = await self.solver_verifier.verify(question)
        solver_results = [solver_result] if solver_result else []

        # Step 5: UserSimulator
        logger.info("Step 5: UserSimulator")
        simulation_result = await self.user_simulator.simulate(profile, question)
        if not simulation_result:
            simulation_result = {}

        # Step 6: Aggregator
        logger.info("Step 6: GenerationAggregator")
        aggregation = GenerationAggregator.aggregate(solver_results, simulation_result, blueprint)

        result = {
            "profile_info": profile_info,
            "profile": profile,
            "blueprint": blueprint,
            "question": question,
            "solver_results": solver_results,
            "simulation_result": simulation_result,
            "aggregation": aggregation,
        }

        # Revision rounds if needed
        max_revisions = 2
        for round_num in range(1, max_revisions + 1):
            if aggregation.get("status") != "revise":
                break

            logger.info("Revision round %d/%d", round_num, max_revisions)
            revision_instructions = aggregation.get("revision_instructions", [])

            revised_question = await self.question_writer.generate(
                blueprint, reference_knowledge, revision_instructions
            )

            if not revised_question or "stem" not in revised_question:
                logger.warning("Revision round %d failed", round_num)
                break

            question = revised_question
            solver_result = await self.solver_verifier.verify(question)
            solver_results = [solver_result] if solver_result else []
            simulation_result = await self.user_simulator.simulate(profile, question)
            if not simulation_result:
                simulation_result = {}

            aggregation = GenerationAggregator.aggregate(solver_results, simulation_result, blueprint)
            result.update({
                "question": question,
                "solver_results": solver_results,
                "simulation_result": simulation_result,
                "aggregation": aggregation,
                f"revision_round_{round_num}": {
                    "revision_instructions": revision_instructions,
                    "aggregation": aggregation,
                },
            })

        logger.info(
            "Generation pipeline completed with status: %s",
            aggregation.get("status", "unknown")
        )

        return result

    @staticmethod
    def _find_reference_knowledge(
        knowledge_base: List[Dict[str, Any]],
        reference_concept: str,
    ) -> List[Dict[str, Any]]:
        """Extract relevant knowledge/mechanism info from extraction results."""
        if not reference_concept:
            return []

        relevant = []

        for extraction in knowledge_base:
            ku = extraction.get("knowledge_units", {})

            # Add knowledge units
            for k in ku.get("knowledge_units", []):
                if reference_concept.lower() in k.get("name", "").lower():
                    relevant.append({"type": "knowledge", **k})

            # Add mechanisms
            for m in ku.get("mechanisms", []):
                if reference_concept.lower() in m.get("name", "").lower():
                    relevant.append({"type": "mechanism", **m})

        return relevant[:5] if relevant else []
