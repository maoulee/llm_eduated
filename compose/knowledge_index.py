"""Knowledge point index — replaces grep with structured tag-based lookup.

Parses metadata from question experience files and builds a reverse index:
  knowledge_point_substring → [files]

Faster and more precise than full-text grep since data is already structured.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class QuestionMeta:
    """Parsed metadata from a question experience file."""

    file_name: str
    file_path: str
    knowledge_points: list[str]  # raw tags/names from 知识点 field
    subject: str = ""
    question_type: str = ""
    year: int = 0
    slot_id: str = ""
    examination_mode: str = ""
    snippet: str = ""


@dataclass
class SearchHit:
    """A search result with score."""

    file_name: str
    file_path: str
    score: float
    snippet: str
    matched_tags: list[str] = field(default_factory=list)


class KnowledgeIndex:
    """Pre-built index for knowledge-point-based file lookup."""

    def __init__(self, data_dir: str = "data/question_experiences"):
        self._data_dir = Path(data_dir)
        self._files: dict[str, QuestionMeta] = {}  # file_name → meta
        self._by_tag_segment: dict[str, list[str]] = {}  # segment → [file_names]
        self._by_subject: dict[str, list[str]] = {}  # subject → [file_names]
        self._built = False

    def build(self) -> None:
        """Scan all experience files and build the index."""
        if self._built:
            return

        if not self._data_dir.exists():
            return

        for md_file in sorted(self._data_dir.glob("*.md")):
            meta = self._parse_file(md_file)
            if meta:
                self._files[meta.file_name] = meta
                self._index_meta(meta)

        self._built = True

    def search(
        self,
        query: str | list[str],
        max_results: int = 30,
        subject: str | None = None,
    ) -> list[SearchHit]:
        """Search by knowledge point keywords.

        Args:
            query: Single keyword or list of keywords
            max_results: Maximum results to return
            subject: Optional subject filter (e.g. "数据结构")

        Returns:
            List of SearchHit sorted by score descending
        """
        self.build()

        if isinstance(query, str):
            keywords = [query]
        else:
            keywords = [k for k in query if k.strip()]

        if not keywords:
            return []

        scores: dict[str, float] = {}
        matched: dict[str, list[str]] = {}

        # Candidate files: either subject-filtered or all
        if subject:
            candidates = set(self._by_subject.get(subject, []))
        else:
            candidates = set(self._files.keys())

        for kw in keywords:
            kw_lower = kw.lower()
            for fname in candidates:
                meta = self._files.get(fname)
                if not meta:
                    continue

                score = self._score_keyword(kw_lower, meta)
                if score > 0:
                    scores[fname] = scores.get(fname, 0) + score
                    if fname not in matched:
                        matched[fname] = []
                    # Track which tags matched
                    for kp in meta.knowledge_points:
                        if kw_lower in kp.lower():
                            matched[fname].append(kp)

        # Sort by score desc
        ranked = sorted(scores.keys(), key=lambda f: scores[f], reverse=True)
        results = []
        for fname in ranked[:max_results]:
            meta = self._files[fname]
            results.append(SearchHit(
                file_name=meta.file_name,
                file_path=meta.file_path,
                score=scores[fname],
                snippet=meta.snippet,
                matched_tags=matched.get(fname, []),
            ))

        return results

    def get_by_file(self, file_name: str) -> QuestionMeta | None:
        """Get metadata for a specific file."""
        self.build()
        return self._files.get(file_name)

    def get_all_tags(self) -> list[str]:
        """Get all unique tag segments."""
        self.build()
        return sorted(self._by_tag_segment.keys())

    def list_subjects(self) -> dict[str, int]:
        """Get subject → file count."""
        self.build()
        return {s: len(fs) for s, fs in self._by_subject.items()}

    # ── Internal ──

    def _score_keyword(self, kw_lower: str, meta: QuestionMeta) -> float:
        """Score a single keyword against a file's metadata."""
        score = 0.0

        # 1. Exact/partial knowledge point match (highest)
        for kp in meta.knowledge_points:
            kp_lower = kp.lower()
            if kw_lower == kp_lower:
                score += 10.0
            elif kw_lower in kp_lower:
                score += 5.0
            parts = [p.strip() for p in kp.split(">")]
            if parts and kw_lower in parts[-1].lower():
                score += 5.0

        # 2. Tag segment index match — check only this file's segments
        for kp in meta.knowledge_points:
            for seg in (s.strip() for s in kp.split(">")):
                if seg and kw_lower in seg.lower():
                    score += 3.0
                    break
            else:
                continue
            break

        # 3. Title match
        if kw_lower in meta.file_name.lower():
            score += 2.0

        return score

    def _index_meta(self, meta: QuestionMeta) -> None:
        """Add a file's metadata to the reverse index."""
        # Index by knowledge point segments
        for kp in meta.knowledge_points:
            # Split structured tags: "DS-3 > 3.1 栈 > 栈的基本概念"
            segments = [s.strip() for s in kp.split(">")]
            for seg in segments:
                if seg:
                    if seg not in self._by_tag_segment:
                        self._by_tag_segment[seg] = []
                    if meta.file_name not in self._by_tag_segment[seg]:
                        self._by_tag_segment[seg].append(meta.file_name)

            # Also index the full tag as-is (for free-text knowledge points)
            if kp:
                if kp not in self._by_tag_segment:
                    self._by_tag_segment[kp] = []
                if meta.file_name not in self._by_tag_segment[kp]:
                    self._by_tag_segment[kp].append(meta.file_name)

        # Index by subject
        if meta.subject:
            if meta.subject not in self._by_subject:
                self._by_subject[meta.subject] = []
            self._by_subject[meta.subject].append(meta.file_name)

    def _parse_file(self, md_file: Path) -> QuestionMeta | None:
        """Parse a question experience file into structured metadata."""
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            return None

        # Extract 知识点 field
        kp_match = re.search(r"\*\*知识点\*\*[：:]\s*(.+)", text)
        knowledge_points = []
        if kp_match:
            raw = kp_match.group(1).strip()
            knowledge_points = [k.strip() for k in raw.split(",") if k.strip()]

        # Extract 科目
        subject_match = re.search(r"\*\*科目\*\*[：:]\s*(.+)", text)
        subject = subject_match.group(1).strip() if subject_match else ""

        # Extract 题型
        type_match = re.search(r"\*\*题型\*\*[：:]\s*(.+)", text)
        question_type = type_match.group(1).strip() if type_match else ""

        # Extract year and slot
        year_match = re.search(r"\*\*年份\*\*[：:]\s*(\d+)", text)
        year = int(year_match.group(1)) if year_match else 0

        slot_match = re.search(r"\*\*题位\*\*[：:]\s*(\S+)", text)
        slot_id = slot_match.group(1) if slot_match else ""

        # Extract examination mode
        mode_match = re.search(r"\*\*模式\*\*[：:]\s*(.+)", text)
        examination_mode = mode_match.group(1).strip() if mode_match else ""

        # Build snippet from 题干原文 section
        snippet = self._extract_snippet(text)

        return QuestionMeta(
            file_name=md_file.name,
            file_path=str(md_file),
            knowledge_points=knowledge_points,
            subject=subject,
            question_type=question_type,
            year=year,
            slot_id=slot_id,
            examination_mode=examination_mode,
            snippet=snippet,
        )

    @staticmethod
    def _extract_snippet(text: str) -> str:
        """Extract a short snippet from the question body."""
        snippet_match = re.search(r"## 题干原文\s*\n(.+?)(?=\n## |\Z)", text, re.DOTALL)
        if snippet_match:
            body = snippet_match.group(1).strip()
            return body[:300]
        return ""


# ── Module-level singleton ──

_default_index: KnowledgeIndex | None = None


def get_index(data_dir: str = "data/question_experiences") -> KnowledgeIndex:
    """Get or create the default knowledge index.

    If the data_dir differs from the cached index, rebuilds automatically.
    """
    global _default_index
    if _default_index is None or _default_index._data_dir != Path(data_dir):
        _default_index = KnowledgeIndex(data_dir)
        _default_index.build()
    return _default_index


def search_questions(
    query: str | list[str],
    max_results: int = 30,
    subject: str | None = None,
    data_dir: str = "data/question_experiences",
) -> list[SearchHit]:
    """Convenience function: search questions by knowledge point keywords."""
    idx = get_index(data_dir)
    return idx.search(query, max_results=max_results, subject=subject)
