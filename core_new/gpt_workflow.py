"""GPT 3-Agent Pipeline — 出题 → 审核 → 求解 → 审核 → Qwen 格式化.

3 independent GPT agents, 4 sequential sessions per slot:
  Session 1 (Agent: 出题):    Generate complete question from blueprint
  Session 2 (Agent: 审核):    Audit question stem + knowledge points
  Session 3 (Agent: 求解):    Generate Python solver code
  Session 4 (Agent: 审核):    Full audit of question + computation results

Each session is a NEW, independent GPT conversation. Previous session OUTPUT
is passed as INPUT to the next session. No incremental context reuse.

Qwen handles final formatting/assembly (local LLM, lightweight).
If any GPT session fails, the pipeline falls back to the local path.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from core_new.slot_prompts import K_RADAR_DEFINITIONS
from core_new.webgpt_client import get_webgpt_client

__all__ = ["GptWorkflow", "GptSessionError", "parse_review_response"]

logger = logging.getLogger(__name__)


# ── Exception ────────────────────────────────────────────────────


class GptSessionError(Exception):
    """Raised when any GPT session fails, triggering fallback to local pipeline."""


# ── GPT Response Parser ──────────────────────────────────────────


def parse_review_response(md_text: str) -> Dict[str, Any]:
    """Parse GPT's Markdown review response into structured data.

    Extracts:
    - status: pass/needs_fix
    - corrected_stem: GPT's corrected stem (if needs_fix)
    - corrected_sub_questions: GPT's corrected sub_questions (if needs_fix)
    - reason: GPT's explanation/reasoning

    Handles Chinese keywords: "通过", "纠正", "修改", "问题"
    """
    if not md_text:
        return {"status": "unknown", "reason": "empty_response"}

    text = md_text.strip()
    result: Dict[str, Any] = {"raw_response": text}

    # Detect status
    if re.search(r"通过|pass|合格|无需修改", text, re.IGNORECASE):
        result["status"] = "pass"
    elif re.search(r"纠正|修改|问题|needs_fix|需要修改|建议修改", text, re.IGNORECASE):
        result["status"] = "needs_fix"
    else:
        result["status"] = "unclear"

    # Extract sections using markdown parsing
    sections: Dict[str, str] = {}
    for match in re.finditer(r"^##\s*(.+?)\s*$(.*?)(?=^##|\Z)", text, re.MULTILINE | re.DOTALL):
        header = match.group(1).strip().lower()
        content = match.group(2).strip()
        sections[header] = content

    # Extract reason/comment
    for key in ("审核意见", "理由", "说明", "reason", "comment", "审核结果"):
        if key in sections:
            result["reason"] = sections[key][:500]
            break
    if "reason" not in result:
        first_para = text.split("\n\n")[0]
        if first_para and len(first_para) > 10:
            result["reason"] = first_para[:500]

    # Extract corrected stem
    for key in ("纠正后题干", "修正后题干", "修改后题干", "corrected_stem", "题干（修正）"):
        if key in sections:
            result["corrected_stem"] = sections[key]
            break

    # Extract corrected sub_questions
    for key in ("纠正后子问题", "修正后子问题", "修改后子问题", "corrected_sub_questions", "子问题（修正）"):
        if key in sections:
            content = sections[key]
            try:
                result["corrected_sub_questions"] = json.loads(content)
            except json.JSONDecodeError:
                result["corrected_sub_questions_raw"] = content
            break

    # Extract issues/problems list
    for key in ("问题", "issues", "发现的问题"):
        if key in sections:
            result["issues"] = sections[key]
            break

    # If needs_fix but no corrected content found, extract from "fix" section
    if result.get("status") == "needs_fix" and "corrected_stem" not in result:
        for key in ("修正", "修改", "fix", "correction"):
            if key in sections:
                content = sections[key]
                if len(content) > 20:
                    result["corrected_stem"] = content
                break

    return result


# ── Prompt Constants ─────────────────────────────────────────────

_SYSTEM_DESIGNER = (
    "你是一名408考研出题专家。你的任务是根据蓝图、经验卡和认知雷达K值标准，"
    "直接设计一道完整的408考试题目。\n\n"
    "输出格式：Markdown（使用##标题和- **key**: value格式）。\n\n"
    "单选题输出示例:\n"
    "## 题目\n"
    "- **stem**: 题干内容\n"
    "- **option_A**: A选项\n"
    "- **option_B**: B选项\n"
    "- **option_C**: C选项\n"
    "- **option_D**: D选项\n"
    "- **correct_answer**: B\n"
    "- **design_intent**: 设计意图\n"
    "- **knowledge_points**: 知识点\n"
    "- **distractor_intent_A**: A选项干扰策略\n"
    "- **given_conditions**: 条件1; 条件2\n\n"
    "综合题输出示例:\n"
    "## 题目\n"
    "- **stem**: 题干内容\n"
    '- **sub_questions**: [{"index":1,"text":"第一问","score":3},{"index":2,"text":"第二问","score":5}]\n'
    "- **given_conditions**: 条件1; 条件2\n"
    "- **design_intent**: 设计意图\n"
    "- **knowledge_points**: 知识点\n"
    "- **difficulty_self_assessment**: 中等偏难\n\n"
    "核心规则：\n"
    "1. 所有给定条件必须被使用\n"
    "2. 参数必须自洽，确保唯一解\n"
    "3. 子问数量、难度必须匹配蓝图\n"
    "4. 推理路径完整无跳步\n"
    "5. 题干描述清晰无歧义\n"
    "6. 数值参数必须合理（不要出现不可能的参数组合）"
)

_SYSTEM_AUDITOR_QUESTION = (
    "你是一名408考研出题审核专家。你将审核一道新设计的题目，"
    "重点检查题干描述和知识点匹配度。\n\n"
    "输出格式：Markdown。\n\n"
    "审核重点：\n"
    "1. 题干描述是否清晰无歧义\n"
    "2. 知识点是否匹配蓝图要求\n"
    "3. 难度是否对标蓝图（参照K值定义）\n"
    "4. 子问数量是否正确\n"
    "5. 给定条件是否合理且充分\n"
    "6. 参数是否自洽\n\n"
    "如果通过，简要说明理由。\n"
    "如果有问题，先指出问题，然后直接给出纠正后的题干和子问题。"
)

_SYSTEM_SOLVER = (
    "你是一名Python解题智能体。你的任务是为408考研题目编写完整的Python求解脚本。\n\n"
    "输出格式：纯Python代码（不要用Markdown代码块包裹）。\n\n"
    "要求：\n"
    "1. 代码必须自包含，只依赖Python标准库（math, decimal, fractions, itertools, collections）\n"
    "2. 必须打印完整求解过程（每一步都要print）\n"
    "3. 最终答案必须单独一行打印，格式: ANSWER: xxx\n"
    "4. 严禁硬编码中间值，所有数据必须从题目条件推导\n"
    "5. 对于选择题，逐选项验证\n"
    "6. 对于综合题，逐子问题求解"
)

_SYSTEM_AUDITOR_FINAL = (
    "你是一名408考研出题审核专家。你将审核完整的题目及其求解结果。\n\n"
    "输出格式：Markdown。\n\n"
    "审核重点：\n"
    "1. 数值计算是否正确\n"
    "2. 答案是否自洽\n"
    "3. 所有给定条件是否被使用\n"
    "4. 解析是否完整\n"
    "5. 是否匹配蓝图要求\n\n"
    "如果通过，简要说明理由。\n"
    "如果有问题，先指出问题，然后直接给出纠正后的内容。"
)


# ── GptWorkflow ──────────────────────────────────────────────────


class GptWorkflow:
    """3-Agent GPT pipeline: 出题 → 审核 → 求解 → 审核.

    Each session is a NEW, independent GPT conversation with its own
    system prompt. Previous session OUTPUT is passed as INPUT to the next.
    """

    def __init__(self) -> None:
        self._client = get_webgpt_client()

    @property
    def available(self) -> bool:
        return self._client is not None

    def _key(self, slot_id: str, step: str) -> str:
        """Unique session key per step: Q43:s1_gen, Q43:s2_aq, Q43:s3_solve, Q43:s4_af"""
        return f"{slot_id}:{step}"

    # ── Agent 1: 出题 ──────────────────────────────────────

    async def generate_question(
        self,
        slot_id: str,
        blueprint: Dict[str, Any],
        experience_card: str,
    ) -> Dict[str, Any]:
        """Session 1: Generate complete question from blueprint.

        New GPT conversation. System prompt = 408 exam designer.
        Returns parsed JSON question dict.
        Raises GptSessionError on failure.
        """
        if not self._client:
            raise GptSessionError("WebGPT not configured")

        content_parts = [
            f"{K_RADAR_DEFINITIONS}\n---",
            f"## 题位蓝图\n{json.dumps(blueprint, ensure_ascii=False, indent=2)}",
        ]
        if experience_card:
            content_parts.append(f"## 往年出题经验与范式\n{experience_card}")
        content_parts.append("请直接输出JSON格式的完整题目。")
        content = "\n\n".join(content_parts)

        session_key = self._key(slot_id, "s1_gen")
        logger.info("[%s] GPT Session 1 (generate_question): content_len=%d",
                     slot_id, len(content))
        try:
            raw = await self._client.delegate(
                agent_name="gpt_designer",
                slot_id=session_key,
                system_prompt=_SYSTEM_DESIGNER,
                content=content,
            )
            result = self._parse_design_response(raw, "generate_question")
            logger.info("[%s] GPT Session 1 done: stem=%s",
                         slot_id, str(result.get("stem", ""))[:80])
            return result
        except GptSessionError:
            raise
        except Exception as e:
            raise GptSessionError(f"generate_question failed: {e}") from e

    # ── Agent 3: 审核 (question audit) ─────────────────────

    async def audit_question(
        self,
        slot_id: str,
        question: Dict[str, Any],
        blueprint: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Session 2: Audit question stem + knowledge points.

        New GPT conversation. Returns parsed audit result.
        Raises GptSessionError on failure.
        """
        if not self._client:
            raise GptSessionError("WebGPT not configured")

        content = (
            f"## 题目\n{json.dumps(question, ensure_ascii=False, indent=2)}\n\n"
            f"## 蓝图要求\n{json.dumps(blueprint, ensure_ascii=False, indent=2)}\n\n"
            f"{K_RADAR_DEFINITIONS}\n\n"
            "请重点审核：题干清晰度、知识点覆盖、难度对标蓝图、子问数量、参数自洽。\n"
            "如果通过，简要说明。\n"
            "如果有问题，指出问题并给出纠正后的题干和子问题。"
        )

        session_key = self._key(slot_id, "s2_aq")
        logger.info("[%s] GPT Session 2 (audit_question): content_len=%d",
                     slot_id, len(content))
        try:
            raw = await self._client.delegate(
                agent_name="gpt_auditor",
                slot_id=session_key,
                system_prompt=_SYSTEM_AUDITOR_QUESTION,
                content=content,
            )
            result = parse_review_response(raw)
            logger.info("[%s] GPT Session 2 done: status=%s",
                         slot_id, result.get("status"))
            return result
        except GptSessionError:
            raise
        except Exception as e:
            raise GptSessionError(f"audit_question failed: {e}") from e

    # ── Agent 2: 求解 ──────────────────────────────────────

    async def generate_solver_code(
        self,
        slot_id: str,
        question: Dict[str, Any],
        is_sc: bool,
    ) -> str:
        """Session 3: Generate Python solver code.

        New GPT conversation. Returns raw Python code string.
        Raises GptSessionError on failure.
        """
        if not self._client:
            raise GptSessionError("WebGPT not configured")

        q_type = "single_choice" if is_sc else "comprehensive"
        content = (
            f"## 题目（{q_type}）\n{json.dumps(question, ensure_ascii=False, indent=2)}\n\n"
            "请编写完整的Python求解脚本。"
        )

        session_key = self._key(slot_id, "s3_solve")
        logger.info("[%s] GPT Session 3 (generate_solver_code): content_len=%d",
                     slot_id, len(content))
        try:
            raw = await self._client.delegate(
                agent_name="gpt_solver",
                slot_id=session_key,
                system_prompt=_SYSTEM_SOLVER,
                content=content,
            )
            code = self._extract_python_code(raw)
            logger.info("[%s] GPT Session 3 done: code_len=%d",
                         slot_id, len(code))
            return code
        except GptSessionError:
            raise
        except Exception as e:
            raise GptSessionError(f"generate_solver_code failed: {e}") from e

    # ── Agent 3: 审核 (final audit) ────────────────────────

    async def audit_final(
        self,
        slot_id: str,
        question: Dict[str, Any],
        exec_result: Dict[str, Any],
        blueprint: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Session 4: Full audit of question + computation results.

        New GPT conversation. Returns parsed audit result.
        Raises GptSessionError on failure.
        """
        if not self._client:
            raise GptSessionError("WebGPT not configured")

        stdout = exec_result.get("stdout", "")
        stderr = exec_result.get("stderr", "")
        exec_summary = f"stdout:\n{stdout[:3000]}"
        if stderr:
            exec_summary += f"\nstderr:\n{stderr[:500]}"

        content = (
            f"## 题目\n{json.dumps(question, ensure_ascii=False, indent=2)}\n\n"
            f"## 求解代码执行结果\n{exec_summary}\n\n"
            f"## 蓝图要求\n{json.dumps(blueprint, ensure_ascii=False, indent=2)}\n\n"
            "请审核：计算是否正确、答案是否自洽、所有条件是否被使用、解析是否完整。\n"
            "如果通过，简要说明。\n"
            "如果有问题，指出问题并给出纠正后的内容。"
        )

        session_key = self._key(slot_id, "s4_af")
        logger.info("[%s] GPT Session 4 (audit_final): content_len=%d",
                     slot_id, len(content))
        try:
            raw = await self._client.delegate(
                agent_name="gpt_auditor",
                slot_id=session_key,
                system_prompt=_SYSTEM_AUDITOR_FINAL,
                content=content,
            )
            result = parse_review_response(raw)
            logger.info("[%s] GPT Session 4 done: status=%s",
                         slot_id, result.get("status"))
            return result
        except GptSessionError:
            raise
        except Exception as e:
            raise GptSessionError(f"audit_final failed: {e}") from e

    # ── Cleanup ─────────────────────────────────────────────

    async def cleanup(self, slot_id: str) -> None:
        """Cleanup all sessions for a slot."""
        if not self._client:
            return
        steps = ["s1_gen", "s2_aq", "s3_solve", "s4_af"]
        for step in steps:
            key = self._key(slot_id, step)
            try:
                await self._client.cleanup(slot_id=key)
            except Exception as e:
                logger.warning("[%s] Cleanup %s error: %s", slot_id, step, e)

    # ── Parsing helpers ─────────────────────────────────────

    @staticmethod
    def _parse_design_response(raw: str, context: str = "") -> Dict[str, Any]:
        """Parse design response using unified MD/JSON parser."""
        from core_new.markdown_parser import parse_structured_output, try_parse_json_object

        # Try structured output (MD sections first, JSON fallback built-in)
        result = parse_structured_output(raw, md_sections=("题目", "设计", "题目设计"))
        if result and result.get("stem"):
            # Normalize given_conditions: semicolon-separated string → list
            gc = result.get("given_conditions")
            if isinstance(gc, str):
                result["given_conditions"] = [g.strip() for g in gc.split(";") if g.strip()]
            return result

        # Direct JSON fallback
        data = try_parse_json_object(raw)
        if data and isinstance(data, dict) and data.get("stem"):
            return data

        raise GptSessionError(
            f"Failed to parse design response ({context}): {raw[:200]}"
        )

    @staticmethod
    def _extract_python_code(raw: str) -> str:
        """Extract Python code from GPT response, stripping markdown wrappers."""
        text = raw.strip()

        # Strip markdown code block
        if text.startswith("```"):
            lines = text.split("\n")
            code_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    if in_block:
                        break
                    in_block = True
                    continue
                if in_block:
                    code_lines.append(line)
            if code_lines:
                return "\n".join(code_lines)

        return text
