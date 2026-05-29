"""Slot data structures — markdown-based examination philosophy.

A Slot is a markdown document capturing the examination philosophy (考察理念)
of a question position. It tells the Architecture Agent how to design questions,
regardless of which specific knowledge point is being tested.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


SLOT_DEFAULTS = {
    "Q43": {"score": 10, "subject": "计算机组成原理", "question_type": "comprehensive"},
    "Q44": {"score": 13, "subject": "计算机组成原理", "question_type": "comprehensive"},
    "Q45": {"score": 9, "subject": "操作系统/计算机网络", "question_type": "comprehensive"},
}


@dataclass
class SlotMeta:
    """Lightweight metadata for a question position slot.

    The actual content lives in a markdown file (考察理念 document).
    """

    slot_id: str          # e.g., "Q44"
    score: int            # e.g., 13
    subject: str          # e.g., "计算机组成原理"
    question_type: str = "single_choice"  # "single_choice" or "comprehensive"
    content_md: str = ""  # the full markdown content
    file_path: str = ""   # where the markdown file lives

    @classmethod
    def load(cls, slot_id: str, slots_dir: str = "data/slots") -> SlotMeta | None:
        """Load a slot from its markdown file."""
        path = os.path.join(slots_dir, f"{slot_id}_slot.md")
        if not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        meta = SLOT_DEFAULTS.get(slot_id)

        # Derive defaults from slot_id when not in SLOT_DEFAULTS
        if meta is None:
            num = int(slot_id[1:]) if slot_id.startswith("Q") and slot_id[1:].isdigit() else 0
            if num >= 43:
                meta = {"score": 10, "subject": "计算机组成原理", "question_type": "comprehensive"}
            else:
                meta = {"score": 2, "subject": "计算机组成原理", "question_type": "single_choice"}

        q_type = meta.get("question_type", "single_choice")
        if q_type == "single_choice" and meta["score"] > 2:
            q_type = "comprehensive"

        return cls(
            slot_id=slot_id,
            score=meta["score"],
            subject=meta["subject"],
            question_type=q_type,
            content_md=content,
            file_path=path,
        )

    def get_philosophy_section(self) -> str:
        """Extract the 考察理念 section."""
        return _extract_section(self.content_md, "考察理念")

    def get_design_section(self) -> str:
        """Extract the 设计理念 section."""
        return _extract_section(self.content_md, "设计理念")

    def get_cases_section(self) -> str:
        """Extract the 往年案例 section."""
        return _extract_section(self.content_md, "往年案例")


def _extract_section(md: str, heading: str) -> str:
    """Extract content under a ## heading until the next ## or end of file."""
    lines = md.split("\n")
    capturing = False
    result = []

    for line in lines:
        if line.startswith("## ") and heading in line:
            capturing = True
            continue
        if capturing and line.startswith("## "):
            break
        if capturing:
            result.append(line)

    return "\n".join(result).strip()
