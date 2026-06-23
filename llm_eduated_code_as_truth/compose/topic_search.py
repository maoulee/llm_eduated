"""Route 2: Single-topic search — grep + classify for a given knowledge point.

Given a topic name (e.g. "AVL树旋转操作"), this module:
1. LLM generates grep keywords
2. Python grep searches question_experiences
3. LLM classifies results into topic_mode_cards
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ModeEntry:
    name: str
    count: int = 0
    description: str = ""
    suitable_types: list[str] = field(default_factory=list)
    difficulty: str = "medium"
    examples: list[str] = field(default_factory=list)


@dataclass
class TopicModeCard:
    id: str
    title: str
    knowledge: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    modes: list[ModeEntry] = field(default_factory=list)
    teacher_actions: list[str] = field(default_factory=lambda: ["select_mode", "combine_modes", "change_knowledge"])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "knowledge": self.knowledge,
            "sources": self.sources,
            "modes": [
                {
                    "name": m.name,
                    "count": m.count,
                    "description": m.description,
                    "suitable_types": m.suitable_types,
                    "difficulty": m.difficulty,
                    "examples": m.examples,
                }
                for m in self.modes
            ],
            "teacher_actions": self.teacher_actions,
        }


@dataclass
class GrepHit:
    file_path: str
    file_name: str
    score: float
    snippet: str  # first ~500 chars of relevant section


async def generate_grep_keywords(
    topic_name: str,
    kg_context: str,
    gateway,
    model_routing: dict[str, str] | None = None,
) -> list[str]:
    """LLM generates 3-5 grep keywords for searching question bank.

    Args:
        topic_name: Knowledge point name (e.g. "AVL树旋转操作")
        kg_context: Relevant KG section (trimmed to ~500 chars)
        gateway: LLMGateway instance
        model_routing: Optional model routing override

    Returns:
        List of grep keyword strings
    """
    prompt = f"""给定知识点"{topic_name}"，生成3-5个grep关键词用于搜索相关题目。

知识点上下文:
{kg_context[:500]}

要求:
- 关键词应覆盖该知识点的不同表述和考察角度
- 每个关键词单独一行
- 只输出关键词，不要编号、不要解释

示例（知识点"栈与队列"）:
栈
队列
后进先出
先进先出
压栈"""

    messages = [{"role": "user", "content": prompt}]
    result = await gateway.generate_text(messages, max_tokens=200)

    if not result.content:
        # Fallback: use topic name itself
        return [topic_name]

    keywords = []
    for line in result.content.strip().split("\n"):
        line = line.strip().lstrip("0123456789.-) ")
        if line and len(line) <= 20:
            keywords.append(line)

    return keywords[:5] if keywords else [topic_name]


def grep_question_bank(
    keywords: list[str],
    data_dir: str = "data/question_experiences",
    max_results: int = 30,
) -> list[GrepHit]:
    """Knowledge-point-based search across question experience files.

    Uses structured tag index instead of full-text grep.
    Delegates to knowledge_index.search_questions() and converts to GrepHit.

    Args:
        keywords: Search keywords from LLM
        data_dir: Directory containing question experience .md files
        max_results: Maximum number of results to return

    Returns:
        List of GrepHit sorted by score descending
    """
    from .knowledge_index import search_questions

    if not keywords:
        return []

    hits = search_questions(keywords, max_results=max_results, data_dir=data_dir)
    return [
        GrepHit(
            file_path=h.file_path,
            file_name=h.file_name,
            score=h.score,
            snippet=h.snippet,
        )
        for h in hits
    ]


async def classify_by_modes(
    hits: list[GrepHit],
    topic_name: str,
    gateway,
    model_routing: dict[str, str] | None = None,
) -> TopicModeCard:
    """LLM classifies grep results into examination modes.

    Args:
        hits: Grep results from grep_question_bank
        topic_name: Original topic name
        gateway: LLMGateway instance
        model_routing: Optional model routing override

    Returns:
        TopicModeCard with classified modes
    """
    if not hits:
        return TopicModeCard(
            id=_slugify(topic_name),
            title=topic_name,
            knowledge=topic_name,
            sources=[],
            modes=[],
        )

    # Build context from hits (limited to ~3K chars)
    context_parts = []
    char_budget = 3000
    for hit in hits[:15]:
        entry = f"[{hit.file_name} (score={hit.score:.0f})]\n{hit.snippet[:300]}\n"
        if sum(len(p) for p in context_parts) + len(entry) > char_budget:
            break
        context_parts.append(entry)

    search_context = "\n---\n".join(context_parts)
    total_count = len(hits)

    prompt = f"""将以下{total_count}道关于"{topic_name}"的题目按考察模式分类。

检索结果:
{search_context}

要求:
1. 每个模式给：名称、数量、一句话描述（不超过30字）、适用题型、难度(easy/medium/hard)、1-2个代表题文件名
2. 模式名称要精确，能区分考察角度
3. 按数量从多到少排列
4. 只输出YAML，不要解释

输出格式:
```yaml
modes:
  - name: 旋转类型判断型
    count: 7
    description: 给定插入序列或局部结构，判断旋转类型
    suitable_types: [single_choice, comprehensive]
    difficulty: medium
    examples: [2009_Q5.md, 2011_Q14.md]
```"""

    messages = [{"role": "user", "content": prompt}]
    result = await gateway.generate_text(messages, max_tokens=2000)

    return _parse_topic_mode_card(result.content or "", topic_name, hits)


def _parse_topic_mode_card(raw: str, topic_name: str, hits: list[GrepHit]) -> TopicModeCard:
    """Parse LLM classification output into TopicModeCard."""
    import yaml

    card_id = _slugify(topic_name)
    modes: list[ModeEntry] = []
    sources = []

    # Extract YAML block
    yaml_match = re.search(r"```yaml\s*\n(.*?)```", raw, re.DOTALL)
    if yaml_match:
        try:
            data = yaml.safe_load(yaml_match.group(1))
            if isinstance(data, dict) and "modes" in data:
                for m in data["modes"]:
                    if isinstance(m, dict) and m.get("name"):
                        modes.append(ModeEntry(
                            name=m["name"],
                            count=m.get("count", 0),
                            description=m.get("description", ""),
                            suitable_types=m.get("suitable_types", ["single_choice"]),
                            difficulty=m.get("difficulty", "medium"),
                            examples=m.get("examples", []),
                        ))
        except Exception:
            pass

    # Fallback: if no YAML parsed, create a single "通用" mode
    if not modes and hits:
        modes.append(ModeEntry(
            name=f"{topic_name}综合型",
            count=len(hits),
            description=f"涵盖{topic_name}相关知识点的综合考察",
            suitable_types=["single_choice"],
            difficulty="medium",
            examples=[h.file_name for h in hits[:2]],
        ))

    # Build sources
    top_hits = hits[:5]
    for h in top_hits:
        sources.append({
            "file": h.file_name,
            "score": round(h.score, 1),
        })

    return TopicModeCard(
        id=card_id,
        title=topic_name,
        knowledge=topic_name,
        sources=sources,
        modes=modes,
    )


def _slugify(text: str) -> str:
    """Convert topic name to URL-safe slug."""
    slug = re.sub(r"[^\w一-鿿]+", "_", text.strip())
    return slug[:50].strip("_") or "topic"


async def run_topic_search(
    topic_name: str,
    slot_id: str,
    template: dict,
    gateway,
    model_routing: dict[str, str] | None = None,
    data_dir: str = "data/question_experiences",
) -> dict:
    """Run full Route 2 pipeline for a single topic.

    Args:
        topic_name: Knowledge point name
        slot_id: Target slot ID
        template: Slot template {type, score, ...}
        gateway: LLMGateway for interaction model
        model_routing: Optional model routing config
        data_dir: Question experience directory

    Returns:
        Dict with topic_mode_card and outline section
    """
    # Step 1: LLM generates grep keywords
    print(f"  [Route 2] 生成 grep 关键词: {topic_name}")
    kg_context = topic_name  # Minimal context for keyword generation
    keywords = await generate_grep_keywords(topic_name, kg_context, gateway, model_routing)
    print(f"  [Route 2] 关键词: {keywords}")

    # Step 2: Python grep search
    print(f"  [Route 2] grep 检索题库...")
    hits = grep_question_bank(keywords, data_dir)
    print(f"  [Route 2] 命中: {len(hits)} 道题")

    # Step 3: LLM classify
    print(f"  [Route 2] 按考察模式分类...")
    topic_card = await classify_by_modes(hits, topic_name, gateway, model_routing)
    print(f"  [Route 2] 分类完成: {len(topic_card.modes)} 个模式")
    for m in topic_card.modes:
        print(f"    - {m.name}: {m.count}题 ({m.difficulty})")

    # Step 4: Generate outline section
    from compose.outline_yaml_generator import generate_from_topic_mode
    outline_section = generate_from_topic_mode(topic_card.to_dict(), slot_id, template)

    return {
        "topic_card": topic_card.to_dict(),
        "outline_section": outline_section,
        "grep_hits": len(hits),
        "keywords": keywords,
    }
