#!/usr/bin/env python3
"""Knowledge alignment pipeline: tag questions with knowledge points from 4 subject docs.

Uses local vLLM (Qwen3.6-27B-FP8) to identify which knowledge point(s)
each question covers, aligned against the official knowledge documents.

Usage:
    python scripts/knowledge_aligner.py --source simulation   # tag simulation questions
    python scripts/knowledge_aligner.py --source exercise     # tag exercise questions
    python scripts/knowledge_aligner.py --source real_exam    # re-tag real_exam questions
    python scripts/knowledge_aligner.py --source all          # tag everything
"""

import json
import os
import re
import time
import argparse
from pathlib import Path
from openai import OpenAI

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
STRUCTURED_DIR = DATA_DIR / "structured_questions"
VLLM_URL = "http://localhost:8000/v1"
MODEL = "/zhaoshu/llm/Qwen3.6-27B-FP8"

# ── Domain maps (from knowledge docs) ──────────────────────────

DOMAIN_MAP = {
    "CO": {
        "CO-1": "计算机系统概述",
        "CO-2": "数据的表示和运算",
        "CO-3": "存储系统",
        "CO-4": "指令系统",
        "CO-5": "中央处理器",
        "CO-6": "总线",
        "CO-7": "输入输出系统",
    },
    "DS": {
        "DS-1": "数据结构基本概念与算法评价",
        "DS-2": "线性表",
        "DS-3": "栈、队列和数组",
        "DS-4": "串",
        "DS-5": "树与二叉树",
        "DS-6": "图",
        "DS-7": "查找",
        "DS-8": "排序",
    },
    "OS": {
        "OS-1": "操作系统概述",
        "OS-2": "进程与线程管理",
        "OS-3": "内存管理",
        "OS-4": "文件管理",
        "OS-5": "输入输出管理",
    },
    "CN": {
        "CN-1": "计算机网络体系结构",
        "CN-2": "物理层",
        "CN-3": "数据链路层",
        "CN-4": "网络层",
        "CN-5": "传输层",
        "CN-6": "应用层",
    },
}

SUBJECT_TO_PREFIX = {
    "计算机组成原理": "CO",
    "组成原理": "CO",
    "数据结构": "DS",
    "操作系统": "OS",
    "计算机网络": "CN",
}

DOC_FILES = {
    "CO": DATA_DIR / "computer_organization.md",
    "DS": DATA_DIR / "data_structure.md",
    "OS": DATA_DIR / "operating_system_knowledge.md",
    "CN": DATA_DIR / "computer_network.md",
}


def parse_knowledge_tree(doc_path: Path, prefix: str) -> dict:
    """Parse a knowledge document into a hierarchical tree with domain codes."""
    with open(doc_path, encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    tree = {}
    current_domain = None
    current_section = None
    current_subsection = None

    for line in lines:
        # CO format: ## CO-N Name
        m = re.match(r"^## (" + prefix + r"-\d+)\s+(.+)$", line)
        if m:
            current_domain = m.group(1)
            tree[current_domain] = {"name": m.group(2), "sections": {}}
            current_section = None
            current_subsection = None
            continue

        # DS/OS format: ## N. Name
        m = re.match(r"^## (\d+)\.\s+(.+)$", line)
        if m and prefix != "CO":
            code = f"{prefix}-{m.group(1)}"
            current_domain = code
            tree[code] = {"name": m.group(2), "sections": {}}
            current_section = None
            current_subsection = None
            continue

        # CN format: ## N. Name
        m = re.match(r"^## (\d+)\.\s+(.+)$", line)
        if m and prefix == "CN":
            code = f"CN-{m.group(1)}"
            current_domain = code
            tree[code] = {"name": m.group(2), "sections": {}}
            continue

        # Sub-section: ### N.N or ### Name
        m = re.match(r"^###\s+(.+)$", line)
        if m and current_domain:
            current_section = m.group(1).strip()
            if current_section not in tree[current_domain]["sections"]:
                tree[current_domain]["sections"][current_section] = []
            continue

        # Knowledge point (leaf): - Name / #### Name / ##### Name
        m = re.match(r"^(?:#{4,6})\s+(.+)$", line)
        if not m:
            m = re.match(r"^-\s+(.+)$", line)
            if m and "属性:" in line:
                continue
        if m and current_domain:
            point = m.group(1).strip()
            if point and not point.startswith("属性"):
                target = (
                    tree[current_domain]["sections"].get(current_section)
                    if current_section
                    else None
                )
                if target is not None:
                    target.append(point)
                else:
                    if "_points" not in tree[current_domain]:
                        tree[current_domain]["_points"] = []
                    tree[current_domain]["_points"].append(point)

    return tree


def build_domain_summary(prefix: str, tree: dict) -> str:
    """Build a compact text summary of the domain tree for the prompt."""
    lines = []
    for code, info in tree.items():
        lines.append(f"{code}: {info['name']}")
        for sec, points in info.get("sections", {}).items():
            if points:
                points_str = "、".join(points[:10])
                if len(points) > 10:
                    points_str += f" 等{len(points)}个知识点"
                lines.append(f"  {sec}: {points_str}")
            else:
                lines.append(f"  {sec}")
        if info.get("_points"):
            pts = "、".join(info["_points"][:10])
            lines.append(f"  知识点: {pts}")
    return "\n".join(lines)


def build_prompt(question: dict, domain_summary: str, prefix: str) -> str:
    """Build the LLM prompt for a single question."""
    stem = question.get("stem", "")[:300]
    options = question.get("options", {})
    opts_text = ""
    if isinstance(options, dict) and options:
        opts_text = "\n".join(f"  {k}: {v}" for k, v in options.items())
    elif isinstance(options, list) and options:
        opts_text = "\n".join(f"  {o}" for o in options)

    existing_tags = question.get("knowledge_tags", [])
    tags_note = ""
    if existing_tags:
        tags_note = f"\n已有标签（可能不准确，需重新评估）: {existing_tags}"

    return f"""你是一个408考研题目知识点标注专家。请根据题目内容，从以下知识域结构中选择最匹配的知识点。

## 知识域结构（{prefix}）

{domain_summary}

## 题目

题干: {stem}
{opts_text}{tags_note}

## 要求

请输出严格的JSON格式（不要输出其他内容）:
```json
{{
  "knowledge_domain": "{prefix}-N",
  "knowledge_tags": ["{prefix}-N > 章节名 > 知识点名"],
  "confidence": "high/medium/low"
}}
```

规则:
1. knowledge_domain 必须是上面列出的域代码之一（如 {prefix}-1, {prefix}-2 等）
2. knowledge_tags 使用层级路径格式: "域代码 > 章节 > 具体知识点"
3. 可以有多个 knowledge_tags（如果题目涉及多个知识点）
4. 如果无法确定具体知识点，至少给出正确的 domain"""


def call_vllm(client: OpenAI, messages: list[dict]) -> str | None:
    """Call vLLM with thinking disabled for fast, deterministic responses."""
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=800,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            content = resp.choices[0].message.content
            if content and content.strip():
                return content.strip()
            print(f"  Warning: empty response, tokens={resp.usage.completion_tokens}")
        except Exception as e:
            print(f"  vLLM error (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return None


def extract_json(text: str) -> dict | None:
    """Extract JSON from LLM output, handling markdown code blocks."""
    # Try to find JSON in code block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Try direct JSON parse
    m = re.search(r"\{[^{}]*\"knowledge_domain\"[^{}]*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def load_questions(source: str) -> list[dict]:
    """Load questions from structured JSON files."""
    files = {
        "real_exam": STRUCTURED_DIR / "real_exam_all.json",
        "exercise": STRUCTURED_DIR / "exercise_all.json",
        "simulation": STRUCTURED_DIR / "simulation_all.json",
    }

    if source == "all":
        all_q = []
        for src, path in files.items():
            if path.exists():
                with open(path) as f:
                    qs = json.load(f)
                for q in qs:
                    q["_source_file"] = str(path)
                all_q.extend(qs)
        return all_q

    path = files.get(source)
    if not path or not path.exists():
        print(f"File not found: {path}")
        return []
    with open(path) as f:
        qs = json.load(f)
    for q in qs:
        q["_source_file"] = str(path)
    return qs


def needs_tagging(q: dict) -> bool:
    """Check if a question needs knowledge tagging."""
    tags = q.get("knowledge_tags", [])
    domain = q.get("knowledge_domain", "")

    # Empty or Unknown tags/domain
    if not tags or tags == []:
        return True
    if domain in ("Unknown", "Unknown-1", ""):
        return True
    # Tags contain non-knowledge content (like URLs)
    for t in tags:
        if "www." in t or ".com" in t:
            return True
    return False


def save_questions(questions: list[dict], source: str):
    """Save updated questions back to their source files."""
    by_file = {}
    for q in questions:
        fpath = q.pop("_source_file", None)
        if fpath:
            by_file.setdefault(fpath, []).append(q)

    for fpath, qs in by_file.items():
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(qs, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(qs)} questions to {fpath}")


def main():
    parser = argparse.ArgumentParser(description="Knowledge alignment pipeline")
    parser.add_argument("--source", choices=["real_exam", "exercise", "simulation", "all"],
                        default="simulation", help="Which source to process")
    parser.add_argument("--batch-size", type=int, default=1, help="Questions per batch")
    parser.add_argument("--limit", type=int, default=0, help="Max questions to process (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Don't save, just print")
    args = parser.parse_args()

    # Init vLLM client
    client = OpenAI(base_url=VLLM_URL, api_key="dummy")

    # Parse knowledge trees and build summaries
    trees = {}
    summaries = {}
    for prefix, doc_path in DOC_FILES.items():
        trees[prefix] = parse_knowledge_tree(doc_path, prefix)
        summaries[prefix] = build_domain_summary(prefix, trees[prefix])
        domain_count = len(trees[prefix])
        print(f"Parsed {prefix}: {domain_count} domains")

    # Load questions
    questions = load_questions(args.source)
    to_tag = [q for q in questions if needs_tagging(q)]

    print(f"\nTotal questions: {len(questions)}")
    print(f"Needing tagging: {len(to_tag)}")

    if args.limit > 0:
        to_tag = to_tag[:args.limit]
        print(f"Processing first {args.limit} questions")

    if not to_tag:
        print("Nothing to tag!")
        return

    # Process
    tagged = 0
    failed = 0

    for i, q in enumerate(to_tag):
        subject = q.get("subject", "")
        prefix = SUBJECT_TO_PREFIX.get(subject)

        if not prefix:
            # Try to infer from stem
            stem = q.get("stem", "")
            for sub, pfx in SUBJECT_TO_PREFIX.items():
                if sub in subject or sub in stem:
                    prefix = pfx
                    break

        if not prefix:
            print(f"  [{i+1}/{len(to_tag)}] {q['id']}: Cannot determine subject ({subject}), skipping")
            failed += 1
            continue

        summary = summaries.get(prefix, "")
        if not summary:
            print(f"  [{i+1}/{len(to_tag)}] {q['id']}: No knowledge doc for {prefix}, skipping")
            failed += 1
            continue

        prompt = build_prompt(q, summary, prefix)
        response = call_vllm(client, [{"role": "user", "content": prompt}])

        if not response:
            print(f"  [{i+1}/{len(to_tag)}] {q['id']}: vLLM call failed")
            failed += 1
            continue

        result = extract_json(response)
        if not result:
            print(f"  [{i+1}/{len(to_tag)}] {q['id']}: Could not parse JSON from response")
            failed += 1
            continue

        # Apply results
        domain = result.get("knowledge_domain", "")
        tags = result.get("knowledge_tags", [])
        confidence = result.get("confidence", "low")

        if domain:
            q["knowledge_domain"] = domain
        if tags:
            q["knowledge_tags"] = tags

        q["tagging_confidence"] = confidence

        tagged += 1
        status = "OK" if confidence == "high" else f"({confidence})"
        print(f"  [{i+1}/{len(to_tag)}] {q['id']}: {domain} | {tags[:2]}... {status}")

        # Rate limit
        if (i + 1) % 50 == 0:
            print(f"\n  --- Progress: {tagged} tagged, {failed} failed ---\n")

    print(f"\nDone! Tagged: {tagged}, Failed: {failed}, Total: {len(to_tag)}")

    if not args.dry_run:
        save_questions(questions, args.source)
        print("Files saved.")
    else:
        print("Dry run - no files saved.")


if __name__ == "__main__":
    main()
