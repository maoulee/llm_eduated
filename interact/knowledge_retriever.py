"""Knowledge-point-based retrieval for question generation support.

Wraps artifact_store functions and knowledge_registry.json to provide
pure-Python lookups for knowledge subgraphs, question experiences,
profiles, and statistics. No LLM calls.
"""

import json
import os
import re
from dataclasses import dataclass, field

from compose.artifact_store import (
    _extract_knowledge_graph_section,
    _KG_DOMAIN_ALIASES,
)


@dataclass
class KnowledgeStatistics:
    k_distributions: dict[str, list[int]]  # K1-K5 historical values
    mode_frequencies: dict[str, int]       # examination mode -> count
    question_count: int
    slot_distribution: dict[str, int]      # slot_id -> count


@dataclass
class QuestionExperience:
    question_id: str
    year: str
    slot: str
    content: str  # raw markdown from question_experiences/


class KnowledgeRetriever:
    """Retrieve knowledge subgraphs, question experiences, and statistics."""

    def __init__(self, data_root: str = "data"):
        self._data_root = data_root
        self._registry_path = os.path.join(data_root, "knowledge_registry.json")
        self._experiences_dir = os.path.join(data_root, "question_experiences")
        self._profiles_dir = os.path.join(data_root, "knowledge_profiles")

        with open(self._registry_path, encoding="utf-8") as f:
            self._registry: dict = json.load(f)

        # Build lookup index: stripped tag segments -> full tag
        self._tag_index: list[str] = list(self._registry.keys())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_knowledge_tag(self, query: str) -> str | None:
        """Map a user query (e.g. 'TCP拥塞控制') to a knowledge_registry tag.

        Uses substring matching against tag names.
        Returns None if ambiguous (multiple matches) or not found.
        """
        matches = self.search(query)
        if len(matches) == 1:
            return matches[0]
        return None

    def retrieve_knowledge_subtree(self, knowledge_tag: str) -> str:
        """Extract the relevant subtree from the knowledge graph.

        Reuses artifact_store._extract_knowledge_graph_section().
        Input: tag like 'CN-5 > 传输控制协议 TCP > 拥塞控制'
        Output: raw markdown subtree
        """
        # The registry tag format is "DOMAIN-chapter > ... > leaf"
        # which maps directly to target_family used by artifact_store.
        # Extract the top-level family portion: "DOMAIN-chapter > section"
        parts = [p.strip() for p in knowledge_tag.split(">")]
        if not parts:
            return ""

        # _extract_knowledge_graph_section expects "DOMAIN-chapter > section" style
        # It only uses the first two levels for navigation.
        target_family = knowledge_tag if len(parts) <= 2 else "> ".join(parts[:2])

        result = _extract_knowledge_graph_section(target_family)

        # If the tag has a deeper sub-level, try to narrow within the result
        if result and len(parts) > 2:
            sub_level = parts[-1].strip()
            sub_pattern = re.compile(
                rf"^(#{2,6})\s+.*{re.escape(sub_level)}", re.MULTILINE
            )
            sub_match = sub_pattern.search(result)
            if sub_match:
                heading_level = len(sub_match.group(1))
                sub_start = sub_match.start()
                sub_end = len(result)
                end_pattern = re.compile(
                    rf"^(#{2,{heading_level}})\s+", re.MULTILINE
                )
                for hm in end_pattern.finditer(result[sub_match.end():]):
                    sub_end = sub_match.end() + hm.start()
                    break
                result = result[sub_start:sub_end].strip()

        return result

    def retrieve_question_experiences(
        self, knowledge_tag: str, max_count: int = 15
    ) -> list[QuestionExperience]:
        """Load relevant question experience files.

        Query knowledge_registry.json for question IDs,
        load from data/question_experiences/.
        Return raw markdown content -- no summarization.
        """
        entry = self._registry.get(knowledge_tag)
        if not entry:
            return []

        question_ids = entry.get("questions", [])[:max_count]
        results: list[QuestionExperience] = []

        for qid in question_ids:
            # qid format: "2011_Q20"
            parts = qid.split("_", 1)
            if len(parts) != 2:
                continue
            year, slot = parts

            exp_path = os.path.join(self._experiences_dir, f"{qid}.md")
            content = ""
            if os.path.exists(exp_path):
                with open(exp_path, encoding="utf-8") as f:
                    content = f.read()

            if content:
                results.append(
                    QuestionExperience(
                        question_id=qid,
                        year=year,
                        slot=slot,
                        content=content,
                    )
                )

        return results

    def retrieve_knowledge_profile(self, knowledge_tag: str) -> dict | None:
        """Load pre-computed knowledge profile from data/knowledge_profiles/.

        The profile filename is derived from the leaf segment of the tag.
        """
        # Extract leaf name from tag: "CO-3 > 高速缓冲存储器 Cache > Cache地址映射" -> "Cache地址映射"
        parts = [p.strip() for p in knowledge_tag.split(">")]
        leaf_name = parts[-1] if parts else knowledge_tag

        # Try direct filename
        profile_path = os.path.join(self._profiles_dir, f"{leaf_name}.md")
        if os.path.exists(profile_path):
            return self._parse_profile(profile_path)

        # Try slugified variants
        slug = self._slugify(leaf_name)
        profile_path = os.path.join(self._profiles_dir, f"{slug}.md")
        if os.path.exists(profile_path):
            return self._parse_profile(profile_path)

        return None

    def compute_statistics(self, knowledge_tag: str) -> KnowledgeStatistics:
        """Compute statistics from knowledge_registry + historical data.

        K-value distributions, examination mode frequencies, slot distribution.
        Pure calculation, no LLM.
        """
        entry = self._registry.get(knowledge_tag, {})

        slot_distribution: dict[str, int] = dict(entry.get("slots", {}))
        question_ids: list[str] = entry.get("questions", [])
        question_count = entry.get("frequency", len(question_ids))

        # Compute K-value distributions from question experience files
        k_distributions: dict[str, list[int]] = {}
        mode_frequencies: dict[str, int] = {}

        for qid in question_ids:
            exp_path = os.path.join(self._experiences_dir, f"{qid}.md")
            if not os.path.exists(exp_path):
                continue

            with open(exp_path, encoding="utf-8") as f:
                content = f.read()

            # Extract K values
            for i in range(1, 6):
                m = re.search(
                    rf"\*?\*?K{i}\s*=\s*(\d+)\*?\*?[:：]", content
                )
                if m:
                    k_distributions.setdefault(f"K{i}", []).append(int(m.group(1)))

            # Extract examination mode
            mode_match = re.search(
                r"\*?\*?模式\*?\*?[:：]\s*(.+?)(?:\n|$)", content
            )
            if mode_match:
                mode = mode_match.group(1).strip()
                mode_frequencies[mode] = mode_frequencies.get(mode, 0) + 1

        return KnowledgeStatistics(
            k_distributions=k_distributions,
            mode_frequencies=mode_frequencies,
            question_count=question_count,
            slot_distribution=slot_distribution,
        )

    def search(self, query: str) -> list[str]:
        """Search knowledge registry for matching tags.

        Returns list of matching tag strings for disambiguation.
        Uses substring matching supporting Chinese text.
        """
        query = query.strip()
        if not query:
            return []

        # Normalize: strip domain prefix codes for matching
        # so "TCP拥塞控制" can match "CN-5 > 传输控制协议 TCP > 拥塞控制"
        matches: list[str] = []
        for tag in self._tag_index:
            # Check if query is a substring of any segment of the tag
            segments = [s.strip() for s in tag.split(">")]
            # Match against full tag and each segment
            if query.lower() in tag.lower():
                matches.append(tag)
                continue
            # Also check if query matches any individual segment
            for segment in segments:
                if query.lower() in segment.lower() or segment.lower() in query.lower():
                    matches.append(tag)
                    break

        return matches

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert Chinese/mixed name to filesystem-safe slug."""
        slug = name.strip()
        slug = re.sub(r"[^\w一-鿿-]", "_", slug)
        slug = re.sub(r"_+", "_", slug)
        slug = slug.strip("_")
        return slug

    @staticmethod
    def _parse_profile(path: str) -> dict:
        """Parse a knowledge profile markdown file into a dict."""
        with open(path, encoding="utf-8") as f:
            text = f.read()

        result: dict = {}
        # Extract K value distributions
        k_dist: dict[str, dict[str, str]] = {}
        for m in re.finditer(
            r"\*?\*?(K\d)\*?\*?:\s*(.+?)(?:\n|$)", text
        ):
            k_key = m.group(1)
            dist_str = m.group(2).strip()
            k_dist[k_key] = dist_str
        if k_dist:
            result["k_distributions"] = k_dist

        # Extract examination mode distribution
        mode_section = re.search(
            r"## 考察模式分布\n(.*?)(?=\n## |\Z)", text, re.DOTALL
        )
        if mode_section:
            modes: dict[str, str] = {}
            for line in mode_section.group(1).strip().split("\n"):
                line = line.strip().lstrip("- ")
                if ": " in line or "：" in line:
                    sep = ": " if ": " in line else "："
                    k, v = line.split(sep, 1)
                    modes[k.strip()] = v.strip()
            if modes:
                result["mode_distribution"] = modes

        # Extract sample count
        sample_match = re.search(r"\*?\*?样本数\*?\*?[:：]\s*(\d+)", text)
        if sample_match:
            result["sample_count"] = int(sample_match.group(1))

        result["raw"] = text
        return result
