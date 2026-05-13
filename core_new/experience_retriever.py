"""
ExperienceRetriever: Converts extraction results to natural language "experience cards"

This module transforms structured extraction results into natural language summaries
that can be injected into model prompts without confusion.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import re


@dataclass
class ExperienceCard:
    """A natural language summary of a learning experience"""
    experience_id: str
    target: str  # e.g. "CRC校验"
    card_type: str  # "reasoning_pattern" | "mechanism" | "knowledge"
    summary: str  # 1-3 sentence natural language summary
    common_errors: List[str] = field(default_factory=list)
    applicable_signals: List[str] = field(default_factory=list)


class ExperienceRetriever:
    """
    Converts extraction results to natural language experience cards
    and retrieves relevant cards based on question keywords.
    """

    def __init__(self, extraction_results: List[Dict[str, Any]]):
        """
        Initialize with extraction results.

        Args:
            extraction_results: List of extraction result dictionaries
                               (from extraction_deep_v4.json schema)
        """
        self.extraction_results = extraction_results
        self._cards: List[ExperienceCard] = []
        self._build_cards()

    def _build_cards(self) -> None:
        """Build experience cards from all extraction results."""
        for result in self.extraction_results:
            question_id = result.get("question_id", "unknown")
            self._add_knowledge_cards(result, question_id)
            self._add_mechanism_cards(result, question_id)
            self._add_reasoning_pattern_cards(result, question_id)

    def _add_knowledge_cards(self, result: Dict, question_id: str) -> None:
        """Extract cards from knowledge_units.knowledge_units."""
        knowledge_units = result.get("knowledge_units", {}).get("knowledge_units", [])
        for ku in knowledge_units:
            name = ku.get("name", "")
            description = ku.get("description", "")
            if not name:
                continue

            card_id = f"{question_id}_knowledge_{name}"
            summary = f"{name}：{description}"

            # Extract signals from the knowledge unit name and description
            signals = self._extract_signals(name + " " + description)

            card = ExperienceCard(
                experience_id=card_id,
                target=name,
                card_type="knowledge",
                summary=summary,
                applicable_signals=signals
            )
            self._cards.append(card)

    def _add_mechanism_cards(self, result: Dict, question_id: str) -> None:
        """Extract cards from knowledge_units.mechanisms."""
        mechanisms = result.get("knowledge_units", {}).get("mechanisms", [])
        for mech in mechanisms:
            name = mech.get("name", "")
            description = mech.get("description", "")
            if not name:
                continue

            card_id = f"{question_id}_mechanism_{name}"
            summary = f"{name}：{description}"

            # Extract common errors from common_misunderstanding
            errors = []
            common_misunderstanding = mech.get("common_misunderstanding", "")
            if common_misunderstanding:
                errors.append(common_misunderstanding)

            # Extract signals
            signals = self._extract_signals(name + " " + description)

            card = ExperienceCard(
                experience_id=card_id,
                target=name,
                card_type="mechanism",
                summary=summary,
                common_errors=errors,
                applicable_signals=signals
            )
            self._cards.append(card)

    def _add_reasoning_pattern_cards(self, result: Dict, question_id: str) -> None:
        """Extract cards from reasoning_pattern.steps."""
        reasoning_pattern = result.get("reasoning_pattern", {})
        pattern_name = reasoning_pattern.get("pattern_name", "")
        steps = reasoning_pattern.get("steps", [])

        if not steps:
            return

        # Build summary from steps
        step_descriptions = []
        all_errors = []
        all_signals = []

        for step in steps:
            description = step.get("description", "")
            if description:
                step_descriptions.append(description)

            error = step.get("common_error_at_this_step", "")
            if error:
                all_errors.append(error)

            # Extract signals from step name and description
            step_name = step.get("name", "")
            signals = self._extract_signals(step_name + " " + description)
            all_signals.extend(signals)

        if not step_descriptions:
            return

        # Create a concise summary from steps
        summary = f"{pattern_name}：{'; '.join(step_descriptions[:3])}"

        card_id = f"{question_id}_reasoning_{pattern_name}"

        card = ExperienceCard(
            experience_id=card_id,
            target=pattern_name,
            card_type="reasoning_pattern",
            summary=summary,
            common_errors=all_errors[:3],  # Limit to top 3 errors
            applicable_signals=list(set(all_signals))  # Deduplicate
        )
        self._cards.append(card)

    def _extract_signals(self, text: str) -> List[str]:
        """Extract keywords/signals from text for matching."""
        # Important technical terms that should always be extracted
        # These are common in the domain and useful for matching
        key_terms = {
            'int', 'unsigned', 'char', 'float', 'double',
            '32位', '64位', '16位',
            '溢出', '补码', '反码', '原码',
            '模2', '模运算',
            '类型转换', '整型提升',
            '有符号', '无符号',
            '赋值', '运算',
            '寄存器', '位宽',
            'Cache', '主存',
            'CRC', '校验',
            '多边形', '多项式',
        }

        # Extract key terms that appear in the text
        found_signals = []
        for term in key_terms:
            if term in text:
                found_signals.append(term)

        # Also extract common patterns like "X型", "X机制", "X规则"
        # These capture domain-specific concepts
        patterns = [
            r'(\w+型)',  # Capture types like "int型", "unsigned型"
            r'(\w+机制)',  # Capture mechanisms
            r'(\w+规则)',  # Capture rules
            r'(\w+概念)',  # Capture concepts
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            found_signals.extend(matches)

        # Remove duplicates while preserving order
        seen = set()
        unique_signals = []
        for signal in found_signals:
            if signal not in seen and len(signal) >= 2:
                seen.add(signal)
                unique_signals.append(signal)

        return unique_signals

    def retrieve(self, question_stem: str, top_k: int = 3) -> List[ExperienceCard]:
        """
        Retrieve relevant experience cards based on question keywords.

        Args:
            question_stem: The question text to match against
            top_k: Maximum number of cards to return

        Returns:
            List of most relevant ExperienceCard objects
        """
        # Extract signals from the question
        question_signals = set(self._extract_signals(question_stem))

        # Score each card by matching signals
        scored_cards = []
        for card in self._cards:
            card_signals = set(card.applicable_signals)
            # Simple overlap scoring
            overlap = len(question_signals & card_signals)
            if overlap > 0:
                scored_cards.append((card, overlap))

        # Sort by score and return top_k
        scored_cards.sort(key=lambda x: x[1], reverse=True)
        return [card for card, _ in scored_cards[:top_k]]

    def format_cards(self, cards: List[ExperienceCard]) -> str:
        """
        Format experience cards as natural language text.

        Args:
            cards: List of ExperienceCard objects

        Returns:
            Formatted natural language string
        """
        if not cards:
            return "【相关经验】暂无相关经验"

        lines = ["【相关经验】"]
        for i, card in enumerate(cards, 1):
            # Determine Chinese card type label
            type_labels = {
                "reasoning_pattern": "推理模式",
                "mechanism": "机制",
                "knowledge": "知识点"
            }
            type_label = type_labels.get(card.card_type, card.card_type)

            lines.append(f"{i}. {card.target} ({type_label})")
            lines.append(f"   {card.summary}")

            if card.common_errors:
                error_text = "；".join(card.common_errors[:2])  # Limit to 2 errors
                lines.append(f"   常见错误：{error_text}")

            lines.append("")  # Empty line between cards

        return "\n".join(lines)

    @property
    def all_cards(self) -> List[ExperienceCard]:
        """Return all experience cards."""
        return self._cards

    def get_cards_by_type(self, card_type: str) -> List[ExperienceCard]:
        """Get all cards of a specific type."""
        return [c for c in self._cards if c.card_type == card_type]
