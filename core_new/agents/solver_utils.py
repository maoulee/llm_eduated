"""Shared utilities for CodeAct and FileCode solver agents."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional


# ── Explanation cleaning ──────────────────────────────────────

_THINKING_PATTERNS = [
    # Self-correction phrases
    r"等等[，,。].*?(?=[。\n])",
    r"不对[，,！!].*?(?=[。\n])",
    r"让我们重新审视.*?(?=[。\n])",
    r"让我们?重新.*?(?=[。\n])",
    r"仔细再算一次.*?(?=[。\n])",
    r"再来?看.*?(?=[。\n])",
    r"重新审视.*?(?=[。\n])",
    r"重新审视题目.*?(?=\n)",
    r"修正.*?题干.*?(?=[。\n])",
    r"如果我们将.*?(?=[。\n])",
    r"如果必须选.*?(?=[。\n])",
    r"但为了满足.*?(?=[。\n])",
    r"但等一下.*?(?=[。\n])",
    r"但若按.*?(?=[。\n])",
    r"为了确保.*?的逻辑.*?(?=\n)",
    r"为了.*?适配.*?(?=\n)",
    r"鉴于本题为.*?(?=[。\n])",
    r"此处以.*?为准.*?(?=[。\n])",
    # Meta-commentary
    r"\*\(注：.*?\)\*",
    r"修正最终题干.*?(?=\n)",
    r"选项设计[：:].*?(?=\n)",
    r"完美符合.*?(?=[。\n])",
    r"恰好匹配.*?(?=[。\n])",
    # Self-doubt markers
    r"[？?]\s*(不对|错误|不)[，,]?(.*?)$",
    r"^\d+\.\s*\*?\*?注[：:]",
]


def clean_explanation(text: str) -> str:
    """Remove raw LLM thinking chains from explanation text.

    Strips self-correction, meta-commentary, and reasoning artifacts
    that leak into generated explanations.
    """
    if not text:
        return text

    result = text

    # Remove parenthetical meta-notes spanning multiple lines
    result = re.sub(
        r"\*?\*?\(注[：:].*?\)\*?\*?",
        "", result, flags=re.DOTALL
    )

    # Remove lines that start with self-correction markers
    lines = result.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Strip leading markdown bold markers for pattern matching
        check_text = re.sub(r"^\*+\s*", "", stripped).strip()
        skip = False
        for pattern in _THINKING_PATTERNS:
            if re.search(pattern, stripped) or re.search(pattern, check_text):
                skip = True
                break
        # Also skip lines that look like option design notes
        if re.match(r"^(选项设计|修正最终|完美符合|恰好匹配|重新审视题目|为了确保|为了.*适配|鉴于本题|此处以)", check_text):
            skip = True
        if not skip:
            cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)

    # Collapse multiple blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def extract_python_code(text: str) -> Optional[str]:
    """Extract Python code block from model output."""
    m = re.search(r"```[Pp]ython\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if m:
        content = m.group(1).strip()
        if any(kw in content for kw in ["print(", "import ", "def ", "=", "for ", "if "]):
            return content
    return None


def is_final_answer(text: str) -> bool:
    """Check if the model output contains a final_answer section."""
    return bool(
        re.search(r"#\s*final_answer", text, re.IGNORECASE)
        or re.search(r"FINAL_ANSWER:", text, re.IGNORECASE)
    )


def parse_exec_result(raw: str) -> Dict[str, Any]:
    """Parse python_exec JSON output."""
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"ok": False, "stderr": raw}
    except json.JSONDecodeError:
        return {"ok": False, "stderr": raw}


def extract_results_from_output(output: str) -> Dict[str, Any]:
    """Try to extract structured results from script output."""
    results: Dict[str, Any] = {}
    try:
        m = re.search(r"\{[^{}]+\}", output, re.DOTALL)
        if m:
            results = json.loads(m.group())
    except json.JSONDecodeError:
        pass
    for m in re.finditer(r"(?:结果|result|answer|答案)[：:]\s*(.+)", output, re.IGNORECASE):
        key = f"result_{len(results)}"
        results[key] = m.group(1).strip()
    return results


def parse_final_json(text: str) -> Dict[str, Any]:
    """Parse final answer JSON from model output."""
    m = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    results = {}
    for m in re.finditer(r"\*\*(sub_q\d+)\*\*:\s*(.+)", text):
        results[m.group(1)] = m.group(2).strip()
    return results
