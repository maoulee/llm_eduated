"""Format generated questions into clean 408 exam paper using PaperFormatterAgent.

Usage:
  python format_paper.py                          # rule-based only
  python format_paper.py --polish                  # with LLM content polishing
  python format_paper.py --polish --export         # also export HTML + PDF
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def _load_questions() -> tuple[list[dict], dict, dict]:
    """Load and merge questions from test + slot composition results."""
    questions = []
    blueprint = {}
    review = {}

    for path in ("docs/test_composition_result.json", "docs/slot_composition_result.json"):
        p = Path(path)
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            data = json.load(f)

        if not blueprint:
            blueprint = data.get("paper_blueprint", {})
        if not review:
            review = data.get("final_review", {})

        for q in data.get("final_questions", []):
            if not q.get("stem"):
                continue
            for i, existing in enumerate(questions):
                if existing.get("slot_id") == q.get("slot_id"):
                    questions[i] = q
                    break
            else:
                questions.append(q)

    return questions, blueprint, review


async def main(polish: bool = False, export: bool = False):
    from core_new.agents.paper_formatter import PaperFormatterAgent

    gateway = None
    if polish:
        from config import get_llm_gateway
        gateway = get_llm_gateway()

    questions, blueprint, review = _load_questions()

    agent = PaperFormatterAgent(gateway=gateway)
    md = await agent.format(questions, blueprint, review)

    out_path = Path("docs/exam_paper_clean.md")
    out_path.write_text(md, encoding="utf-8")
    print(f"Formatted: {out_path} ({len(questions)} questions)")

    if export:
        paths = agent.export(out_path)
        for fmt, p in paths.items():
            print(f"  {fmt}: {p}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--polish", action="store_true", help="Use LLM to polish content")
    parser.add_argument("--export", action="store_true", help="Export HTML + PDF")
    args = parser.parse_args()
    asyncio.run(main(polish=args.polish, export=args.export))
