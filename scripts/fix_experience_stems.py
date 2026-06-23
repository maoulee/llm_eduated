"""Fix experience files: supplement missing options and incomplete stems from structured_questions.

For each question experience file:
1. Check if 题干原文 section is missing options (A/B/C/D)
2. Check if stem is truncated or contains embedded answer text
3. Find matching entry in structured_questions by file ID
4. Clean stem (remove answer/noise), append options if missing
"""

import json
import os
import re
from pathlib import Path


def load_structured() -> dict:
    """Load all structured questions indexed by ID."""
    structured = {}

    for fname in ["real_exam_all.json", "simulation_all.json"]:
        fpath = Path(f"data/structured_questions/{fname}")
        if fpath.exists():
            with open(fpath, encoding="utf-8") as f:
                for q in json.load(f):
                    structured[q["id"]] = q

    return structured


def extract_stem_section(text: str) -> tuple[str, int, int]:
    """Extract 题干原文 section boundaries. Returns (content, start, end)."""
    match = re.search(r"(## 题干原文\s*\n)(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if not match:
        return "", -1, -1
    return match.group(2), match.start(2), match.end(2)


def has_options(stem: str) -> bool:
    """Check if stem already has option markers like A. B. etc."""
    return bool(re.search(r"[A-D][.．、：:]\s*\S", stem))


def format_options(options: dict) -> str:
    """Format options dict into markdown lines."""
    lines = []
    for key in ["A", "B", "C", "D", "E", "F"]:
        if key in options and options[key]:
            val = options[key].strip()
            if val:
                lines.append(f"{key}. {val}")
    return "\n".join(lines)


def clean_stem(text: str) -> str:
    """Extract question-only portion from stem, strip answer and noise tags."""
    lines = text.split("\n")
    q_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            q_lines.append("")
            continue

        # Answer starts with numbered solutions after sub-questions already listed
        if re.match(r"^[1-9][）\)．.]", stripped):
            prev = "\n".join(q_lines)
            if re.search(r"[\(（][1-9][\)）]", prev):
                break

        # Score markers = answer
        if re.search(r"（\d+\s*分）", stripped) and "？" not in stripped:
            break

        # 评分说明
        if stripped.startswith("【评分") or stripped.startswith("【说明"):
            break

        # Summary lines like '本题综合涉及...'
        if re.match(r"^本题", stripped):
            break

        q_lines.append(line)

    # Strip trailing noise: short standalone lines without punctuation (tag noise)
    while q_lines:
        last = q_lines[-1].strip()
        if not last:
            q_lines.pop()
            continue
        if len(last) < 20 and not re.search(r"[。？！；：\.\?\!]", last) and not re.match(r"^[\(（]", last):
            q_lines.pop()
        else:
            break

    return "\n".join(q_lines).strip()


def has_answer_in_stem(stem: str) -> bool:
    """Check if stem contains embedded answer text (score markers, etc)."""
    return bool(re.search(r"（\d+\s*分）", stem))


def fix_file(filepath: Path, sq: dict) -> bool:
    """Fix a single experience file. Returns True if modified."""
    text = filepath.read_text(encoding="utf-8")
    stem_content, stem_start, stem_end = extract_stem_section(text)

    if stem_start < 0:
        # No 题干原文 section — add one before ## K1-K5
        k15_match = re.search(r"\n## K1-K5", text)
        if not k15_match:
            return False

        sq_stem = clean_stem(sq.get("stem", ""))
        options_text = format_options(sq.get("options", {}))

        parts = [f"\n## 题干原文\n{sq_stem}"]
        if options_text:
            parts.append(f"\n\n{options_text}")
        parts.append("\n\n")
        text = text[:k15_match.start()] + "".join(parts) + text[k15_match.start():]
        filepath.write_text(text, encoding="utf-8")
        return True

    already_has = has_options(stem_content)
    sq_stem_raw = sq.get("stem", "").strip()
    sq_stem = clean_stem(sq_stem_raw)
    options_text = format_options(sq.get("options", {}))

    stem_trimmed = stem_content.strip()

    # Case 1: current stem has answer mixed in — replace with cleaned version
    if has_answer_in_stem(stem_trimmed) and sq_stem:
        new_stem = sq_stem
        if options_text:
            new_stem += f"\n\n{options_text}"
        new_stem += "\n"
        text = text[:stem_start] + new_stem + text[stem_end:]
        filepath.write_text(text, encoding="utf-8")
        return True

    # Case 2: stem is truncated — replace with structured version
    is_truncated = (
        stem_trimmed
        and not stem_trimmed.endswith(("。", "）", ")", ".", "？", "!", "：", "】"))
        and sq_stem
        and len(sq_stem) > len(stem_trimmed) * 1.2
    )
    if is_truncated:
        new_stem = sq_stem + "\n"
        if options_text:
            new_stem += f"\n{options_text}\n"
        text = text[:stem_start] + new_stem + text[stem_end:]
        filepath.write_text(text, encoding="utf-8")
        return True

    # Case 3: stem ok but missing options
    if already_has or not options_text:
        return False

    new_stem = f"{stem_trimmed}\n\n{options_text}\n"
    text = text[:stem_start] + new_stem + text[stem_end:]
    filepath.write_text(text, encoding="utf-8")
    return True


def main():
    structured = load_structured()
    print(f"Loaded {len(structured)} structured questions")

    exp_dir = Path("data/question_experiences")
    total = 0
    fixed = 0
    no_match = 0
    already_ok = 0

    for filepath in sorted(exp_dir.glob("*.md")):
        total += 1
        fid = filepath.stem

        text = filepath.read_text(encoding="utf-8")
        stem_content, _, _ = extract_stem_section(text)

        if stem_content and has_options(stem_content) and not has_answer_in_stem(stem_content):
            already_ok += 1
            continue

        sq = structured.get(fid)
        if not sq:
            no_match += 1
            continue

        if fix_file(filepath, sq):
            fixed += 1
            if fixed <= 15:
                print(f"  Fixed: {fid}")

    print(f"\nResults: {total} files")
    print(f"  Already OK: {already_ok}")
    print(f"  Fixed from structured: {fixed}")
    print(f"  No structured match: {no_match}")
    print(f"  Remaining incomplete: {total - already_ok - fixed - no_match}")


if __name__ == "__main__":
    main()
