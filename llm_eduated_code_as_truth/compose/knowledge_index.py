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
    k_radar: dict[str, int] = field(default_factory=dict)  # K1-K5 难度向量，供难度锚定检索
    snippet: str = ""


@dataclass
class SearchHit:
    """A search result with score."""

    file_name: str
    file_path: str
    score: float
    snippet: str
    matched_tags: list[str] = field(default_factory=list)
    subject: str = ""
    question_type: str = ""
    year: int = 0
    slot_id: str = ""
    k_radar: dict[str, int] = field(default_factory=dict)


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
        question_type: str | None = None,
    ) -> list[SearchHit]:
        """Search by knowledge point keywords.

        Args:
            query: Single keyword or list of keywords
            max_results: Maximum results to return
            subject: Optional subject filter (e.g. "数据结构")
            question_type: Optional type filter (e.g. "选择题" / "综合题")

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
        if question_type:
            candidates = {
                fname for fname in candidates
                if _question_type_matches(
                    self._files.get(fname).question_type if self._files.get(fname) else "",
                    question_type,
                )
            }

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
                subject=meta.subject,
                question_type=meta.question_type,
                year=meta.year,
                slot_id=meta.slot_id,
                k_radar=meta.k_radar,
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

        # Extract K1-K5 radar (for difficulty-anchored retrieval)
        k_radar = self._extract_k_radar(text)

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
            k_radar=k_radar,
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

    @staticmethod
    def _extract_k_radar(text: str) -> dict[str, int]:
        """Parse K1-K5 from the 'K1-K5 评分与解析' section (fallback: whole text).

        Pattern reuses artifact_store._extract_k_values (K{i}\\s*=\\s*(\\d)).
        Returns {} when no K-values are present.
        """
        section = re.search(r"##\s*K1[-\s]*K5\s*评分与解析\n(.*?)(?=\n##\s|\Z)", text, re.DOTALL)
        body = section.group(1) if section else text
        radar: dict[str, int] = {}
        for i in range(1, 6):
            m = re.search(rf"\*?\*?K{i}\s*=\s*(\d+)\*?\*?", body)
            if m:
                radar[f"K{i}"] = int(m.group(1))
        return radar


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
    question_type: str | None = None,
    data_dir: str = "data/question_experiences",
) -> list[SearchHit]:
    """Convenience function: search questions by knowledge point keywords."""
    idx = get_index(data_dir)
    return idx.search(
        query,
        max_results=max_results,
        subject=subject,
        question_type=question_type,
    )


def retrieve_anchored_references(
    target_k_radar: dict[str, int],
    query: str | list[str],
    subject: str | None = None,
    question_type: str | None = None,
    epsilon: int = 2,
    max_results: int = 8,
    data_dir: str = "data/question_experiences",
) -> list[dict]:
    """K值锚定检索（code-as-truth：难度门 + MAE 由代码算，不让 LLM 脑算）。

    流程：知识关键词命中 → 难度门 D(c) ≤ D(t)+ε（候选不许比目标更难）
          → MAE(c, t) 升序（难度档+认知形状最接近者排前）→ 截断 max_results。
    target_k_radar 形如 {"K1":3,"K2":1,"K3":2,"K4":2,"K5":1}。
    返回 [{"file","k_radar","d_sum","mae","score"}, ...]。
    """
    idx = get_index(data_dir)
    hits = idx.search(
        query, max_results=max(max_results * 5, 40),
        subject=subject, question_type=question_type,
    )
    t = {f"K{i}": int(target_k_radar.get(f"K{i}", 0) or 0) for i in range(1, 6)}
    t_sum = sum(t.values())
    gated: list[dict] = []
    for h in hits:
        if not h.k_radar:
            continue
        c = {f"K{i}": int(h.k_radar.get(f"K{i}", 0) or 0) for i in range(1, 6)}
        c_sum = sum(c.values())
        if c_sum <= t_sum + epsilon:
            mae = sum(abs(c[f"K{i}"] - t[f"K{i}"]) for i in range(1, 6)) / 5.0
            gated.append({
                "file": h.file_name, "k_radar": c,
                "d_sum": c_sum, "mae": mae, "score": h.score,
            })
    gated.sort(key=lambda x: (x["mae"], -x["score"]))
    return gated[:max_results]


def _normalize_question_type(value: str | None) -> str:
    """Normalize common Chinese/English question type labels."""
    text = (value or "").strip().lower()
    if not text:
        return ""
    if text in {"single_choice", "sc", "choice", "选择", "选择题", "单选", "单选题"}:
        return "single_choice"
    if text in {"comprehensive", "comp", "综合", "综合题", "综合应用题", "大题"}:
        return "comprehensive"
    if "选择题" in text or "单选" in text:
        return "single_choice"
    if "综合" in text or "大题" in text:
        return "comprehensive"
    return text


def _question_type_matches(actual: str | None, expected: str | None) -> bool:
    expected_norm = _normalize_question_type(expected)
    if not expected_norm:
        return True
    return _normalize_question_type(actual) == expected_norm
