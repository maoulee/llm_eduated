"""
ConsistencyChecker: Compare dual-path results and determine consistency.

This module implements rule-based comparison between reasoning and code results
from the DualPathSolver, determining whether answers match and which answer to accept.
"""

import re
from typing import Dict, Optional


class ConsistencyChecker:
    """
    Checks consistency between reasoning and code path results.

    Uses simple rule-based matching (exact and fuzzy) to compare answers,
    avoiding expensive LLM calls for obvious matches or disagreements.
    """

    @staticmethod
    def check(reasoning_result: Dict, code_result: Dict) -> Dict:
        """
        Compare dual-path results and determine consistency.

        Args:
            reasoning_result: Result from reasoning path with keys:
                - answer: str (the answer string)
                - reasoning: str (reasoning text)
                - confidence: str or float (confidence score)
                - thinking: str (optional, from reasoning_content)
            code_result: Result from code path with keys:
                - computed_answer: str (answer from code execution)
                - explanation: str (code explanation)
                - code_applicable: bool (whether code was applicable)
                - exec_success: bool (whether code executed successfully)
                - exec_output: str (code execution output)

        Returns:
            Dict with keys:
            - matched: bool (whether answers matched)
            - need_glm: bool (whether GLM arbitration is needed)
            - reasoning_answer: str (extracted reasoning answer)
            - code_answer: str (extracted code answer)
            - final_answer: str (accepted answer if matched)
            - match_method: str (how the match was determined)
            - confidence: float (max of both confidences)
        """
        # Extract answers
        reasoning_answer = reasoning_result.get("answer", "").strip()
        code_answer = code_result.get("computed_answer", "").strip()
        code_applicable = code_result.get("code_applicable", False)
        exec_success = code_result.get("exec_success", False)

        # Extract confidence scores
        reasoning_conf = ConsistencyChecker._parse_confidence(
            reasoning_result.get("confidence", "0.0")
        )
        # Code path confidence is implicit in exec_success
        code_conf = 0.8 if (code_applicable and exec_success and code_answer) else 0.0

        # Initialize result
        result = {
            "matched": False,
            "need_glm": True,
            "reasoning_answer": reasoning_answer,
            "code_answer": code_answer,
            "final_answer": "",
            "match_method": "no_match",
            "confidence": max(reasoning_conf, code_conf),
        }

        # Rule 1: If code not applicable and reasoning has high confidence, accept reasoning
        if not code_applicable and reasoning_conf > 0.7 and reasoning_answer:
            result.update({
                "matched": True,
                "need_glm": False,
                "final_answer": reasoning_answer,
                "match_method": "reasoning_only"
            })
            return result

        # Rule 2: If code execution failed and reasoning has high confidence, accept reasoning
        if not exec_success and reasoning_conf > 0.7 and reasoning_answer:
            result.update({
                "matched": True,
                "need_glm": False,
                "final_answer": reasoning_answer,
                "match_method": "reasoning_only"
            })
            return result

        # Rule 3: If both answers exist, try to match them
        if reasoning_answer and code_answer:
            match_result = ConsistencyChecker._try_match(reasoning_answer, code_answer)
            if match_result["matched"]:
                result.update({
                    "matched": True,
                    "need_glm": False,
                    "final_answer": match_result["final_answer"],
                    "match_method": match_result["method"]
                })
                return result

        # Rule 4: If only code answer exists and it's reliable, accept code
        if code_answer and code_applicable and exec_success and not reasoning_answer:
            result.update({
                "matched": True,
                "need_glm": False,
                "final_answer": code_answer,
                "match_method": "code_only"
            })
            return result

        # Default: no match, need GLM arbitration
        return result

    @staticmethod
    def _try_match(answer1: str, answer2: str) -> Dict:
        """
        Try to match two answers using exact and fuzzy matching.

        Args:
            answer1: First answer string
            answer2: Second answer string

        Returns:
            Dict with keys:
            - matched: bool
            - final_answer: str
            - method: str
        """
        # Normalize for comparison
        a1_norm = ConsistencyChecker._normalize_answer(answer1)
        a2_norm = ConsistencyChecker._normalize_answer(answer2)

        # Try exact match first
        if a1_norm == a2_norm:
            return {
                "matched": True,
                "final_answer": answer1.strip(),
                "method": "exact"
            }

        # Try fuzzy letter match (for option letters A, B, C, D)
        letter1 = ConsistencyChecker._extract_letter(answer1)
        letter2 = ConsistencyChecker._extract_letter(answer2)
        if letter1 and letter2 and letter1 == letter2:
            return {
                "matched": True,
                "final_answer": letter1,
                "method": "fuzzy_letter"
            }

        # Try fuzzy number match
        num1 = ConsistencyChecker._extract_number(answer1)
        num2 = ConsistencyChecker._extract_number(answer2)
        if num1 is not None and num2 is not None and num1 == num2:
            return {
                "matched": True,
                "final_answer": str(num1),
                "method": "fuzzy_number"
            }

        # No match
        return {
            "matched": False,
            "final_answer": "",
            "method": "no_match"
        }

    @staticmethod
    def _normalize_answer(answer: str) -> str:
        """
        Normalize answer for comparison.

        Removes common prefixes, whitespace, and standardizes format.
        """
        if not answer:
            return ""

        # Remove common prefixes
        prefixes_to_remove = [
            r"答案[：:]?\s*",
            r"选项[？]?\s*",
            r"选择[：:]?\s*",
            r"正确答案[：:]?\s*",
            r"最终答案[：:]?\s*",
            r"Answer[：:]?\s*",
            r"[A-D][.、：:]\s*",  # Remove "A." or "A、" prefix
        ]

        normalized = answer
        for prefix in prefixes_to_remove:
            normalized = re.sub(prefix, "", normalized, flags=re.IGNORECASE)

        # Remove whitespace
        normalized = normalized.strip()

        # Uppercase for option letters
        if len(normalized) == 1 and normalized.isalpha():
            normalized = normalized.upper()

        return normalized

    @staticmethod
    def _extract_letter(text: str) -> Optional[str]:
        """
        Extract a single option letter (A, B, C, D) from text.

        Handles formats like "A", "选项A", "A.", "答案A", etc.
        """
        if not text:
            return None

        # Pattern for option letter
        # Match A, B, C, D (case insensitive) as a standalone letter
        # or preceded by common Chinese/English prefixes
        patterns = [
            r"[选项选择答案答案Answer]?[？:：]?\s*([A-D])[.、）)]?\s*$",  # "A", "选项A", "A."
            r"\b([A-D])\b",  # standalone A, B, C, D
            r"([A-D])[选项选择]",  # "A选项"
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        return None

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        """
        Extract numeric value from text.

        Handles integers, decimals, negative numbers, and numbers with prefixes.
        For binary/hex results, converts to decimal for comparison.
        """
        if not text:
            return None

        # Try to extract a number (integer or float, possibly with sign)
        # Look for patterns like "8", "+8", "-8", "0.5", "A: 8", "Result: 8.5"
        patterns = [
            r"[-+]?\d+\.?\d*",  # Signed number with optional decimal
            r"[A-Za-z]+[：:]\s*([-+]?\d+\.?\d*)",  # "A: 8", "Result: 8.5"
            r"答案[：:]?\s*([-+]?\d+\.?\d*)",  # "答案: 8"
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    num_str = match.group(1) if match.lastindex else match.group(0)
                    return float(num_str)
                except (ValueError, IndexError):
                    continue

        return None

    @staticmethod
    def _parse_confidence(confidence) -> float:
        """
        Parse confidence value to float.

        Args:
            confidence: Could be str or float

        Returns:
            float between 0.0 and 1.0
        """
        if isinstance(confidence, float):
            return max(0.0, min(1.0, confidence))

        if isinstance(confidence, int):
            return max(0.0, min(1.0, float(confidence)))

        if isinstance(confidence, str):
            confidence = confidence.strip()
            try:
                val = float(confidence)
                # If value is > 1, assume it's a percentage (e.g., 80 -> 0.8)
                if val > 1.0:
                    val = val / 100.0
                return max(0.0, min(1.0, val))
            except ValueError:
                return 0.0

        return 0.0
