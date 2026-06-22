#!/usr/bin/env python3
"""
Extract exercise and simulation questions from cleaned data.
Task #2 of question extraction pipeline.
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

# Paths
CLEANED_JSONL = Path("/zhaoshu/llm_eduated/408_export/questions_cleaned.jsonl")
TAG_MAP_PATH = Path("/zhaoshu/llm_eduated/data/statistics/tag_normalization_map.json")
OUTPUT_DIR = Path("/zhaoshu/llm_eduated/data/structured_questions")
REAL_EXAM_PATH = Path("/zhaoshu/llm_eduated/data/structured_questions/real_exam_all.json")

# Subject mapping from knowledge tag prefixes
SUBJECT_MAPPING = {
    "数据结构": "数据结构",
    "组成原理": "计算机组成原理",
    "计算机组成原理": "计算机组成原理",
    "操作系统": "操作系统",
    "计算机网络": "计算机网络",
}

def load_tag_normalization_map(path: Path) -> dict:
    """Load tag normalization map."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("normalization_map", {})

def normalize_tags(tags: list, norm_map: dict) -> list:
    """Normalize knowledge tags using the normalization map."""
    normalized = []
    for tag in tags:
        if tag in norm_map:
            normalized.append(norm_map[tag])
        else:
            normalized.append(tag)
    return normalized

def infer_subject(tags: list) -> str:
    """Infer subject from knowledge tags."""
    for tag in tags:
        for prefix, subject in SUBJECT_MAPPING.items():
            if tag.startswith(prefix):
                return subject
    return "Unknown"

def determine_question_type(question: dict) -> str:
    """Determine if question is choice or open based on options."""
    options = question.get("options")
    if options and isinstance(options, dict) and len(options) > 0:
        return "choice"
    return "open"

def get_knowledge_domain(tags: list) -> str:
    """
    Infer knowledge domain from normalized tags.
    Uses pattern matching to determine domain.
    """
    if not tags:
        return "Unknown"

    # Try to extract domain from first tag
    for tag in tags:
        if "/" in tag:
            parts = tag.split("/")
            if len(parts) >= 2:
                # Format: subject/topic or subject/topic/subtopic
                return f"{parts[0].replace('计算机组成原理', 'CO').replace('组成原理', 'CO').replace('操作系统', 'OS').replace('数据结构', 'DS').replace('计算机网络', 'CN')}-1"
        elif tag.startswith("DS") or tag.startswith("OS") or tag.startswith("CO") or tag.startswith("CN"):
            # Already in domain format
            return tag

    # Fallback: generate from subject
    subject = infer_subject(tags)
    subject_map = {
        "数据结构": "DS",
        "计算机组成原理": "CO",
        "操作系统": "OS",
        "计算机网络": "CN",
    }
    return f"{subject_map.get(subject, 'Unknown')}-1"

def question_to_structured(q: dict, norm_map: dict, idx: int, source_type: str) -> dict:
    """Convert a raw question to structured format."""
    # Normalize knowledge tags
    raw_tags = q.get("knowledge_tags", [])
    normalized_tags = normalize_tags(raw_tags, norm_map)

    # Infer subject if missing
    subject = q.get("subject")
    if not subject or subject == "Unknown":
        subject = infer_subject(normalized_tags)

    # Determine question type
    question_type = q.get("question_type")
    if not question_type:
        question_type = determine_question_type(q)

    # Get knowledge domain
    knowledge_domain = q.get("knowledge_domain")
    if not knowledge_domain or knowledge_domain == "Unknown":
        knowledge_domain = get_knowledge_domain(normalized_tags)

    # Generate ID
    qid = q.get("id", f"{source_type}_{idx:05d}")

    return {
        "id": qid,
        "source_type": source_type,
        "subject": subject,
        "question_type": question_type,
        "knowledge_tags": normalized_tags,
        "knowledge_domain": knowledge_domain,
        "stem": q.get("stem", ""),
        "options": q.get("options", {}),
        "correct_answer": q.get("correct_answer", ""),
        "explanation": q.get("explanation", ""),
        "difficulty_level": q.get("difficulty_level", None),
    }

def main():
    print("Loading tag normalization map...")
    norm_map = load_tag_normalization_map(TAG_MAP_PATH)

    print("Loading cleaned questions...")
    exercise_questions = []
    simulation_questions = []

    with open(CLEANED_JSONL, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                q = json.loads(line)
                source_type = q.get("source_type", "")

                if source_type == "exercise":
                    exercise_questions.append(q)
                elif source_type == "simulation":
                    simulation_questions.append(q)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse line {line_num}: {e}")
                continue

    print(f"Found {len(exercise_questions)} exercise questions")
    print(f"Found {len(simulation_questions)} simulation questions")

    # Convert to structured format
    print("Converting exercise questions to structured format...")
    structured_exercise = []
    for idx, q in enumerate(exercise_questions, 1):
        try:
            structured = question_to_structured(q, norm_map, idx, "exercise")
            structured_exercise.append(structured)
        except Exception as e:
            print(f"Warning: Failed to process exercise question {idx}: {e}")

    print("Converting simulation questions to structured format...")
    structured_simulation = []
    for idx, q in enumerate(simulation_questions, 1):
        try:
            structured = question_to_structured(q, norm_map, idx, "simulation")
            structured_simulation.append(structured)
        except Exception as e:
            print(f"Warning: Failed to process simulation question {idx}: {e}")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save structured questions
    print("Saving exercise questions...")
    with open(OUTPUT_DIR / "exercise_all.json", 'w', encoding='utf-8') as f:
        json.dump(structured_exercise, f, ensure_ascii=False, indent=2)

    print("Saving simulation questions...")
    with open(OUTPUT_DIR / "simulation_all.json", 'w', encoding='utf-8') as f:
        json.dump(structured_simulation, f, ensure_ascii=False, indent=2)

    # Load real_exam for summary stats
    print("Loading real_exam questions for summary...")
    with open(REAL_EXAM_PATH, 'r', encoding='utf-8') as f:
        real_exam_data = json.load(f)

    # Generate summary statistics
    print("Generating extraction summary...")
    summary = {
        "total_questions": len(real_exam_data) + len(structured_exercise) + len(structured_simulation),
        "by_source_type": {
            "real_exam": len(real_exam_data),
            "exercise": len(structured_exercise),
            "simulation": len(structured_simulation),
        },
        "subject_distribution": {
            "real_exam": dict(Counter(q.get("subject", "Unknown") for q in real_exam_data)),
            "exercise": dict(Counter(q.get("subject", "Unknown") for q in structured_exercise)),
            "simulation": dict(Counter(q.get("subject", "Unknown") for q in structured_simulation)),
        },
        "question_type_distribution": {
            "real_exam": dict(Counter(q.get("question_type", "Unknown") for q in real_exam_data)),
            "exercise": dict(Counter(q.get("question_type", "Unknown") for q in structured_exercise)),
            "simulation": dict(Counter(q.get("question_type", "Unknown") for q in structured_simulation)),
        },
        "knowledge_tag_coverage": {
            "real_exam": len(set(tag for q in real_exam_data for tag in q.get("knowledge_tags", []))),
            "exercise": len(set(tag for q in structured_exercise for tag in q.get("knowledge_tags", []))),
            "simulation": len(set(tag for q in structured_simulation for tag in q.get("knowledge_tags", []))),
        },
    }

    print("Saving extraction summary...")
    with open(OUTPUT_DIR / "extraction_summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Print summary
    print("\n" + "="*50)
    print("EXTRACTION SUMMARY")
    print("="*50)
    print(f"Total questions: {summary['total_questions']}")
    print(f"  - real_exam: {summary['by_source_type']['real_exam']}")
    print(f"  - exercise: {summary['by_source_type']['exercise']}")
    print(f"  - simulation: {summary['by_source_type']['simulation']}")
    print("\nSubject distribution:")
    for source, subjects in summary['subject_distribution'].items():
        print(f"  {source}:")
        for subj, count in sorted(subjects.items()):
            print(f"    - {subj}: {count}")
    print("\nQuestion type distribution:")
    for source, types in summary['question_type_distribution'].items():
        print(f"  {source}:")
        for qtype, count in sorted(types.items()):
            print(f"    - {qtype}: {count}")
    print("\nKnowledge tag coverage:")
    for source, count in summary['knowledge_tag_coverage'].items():
        print(f"  - {source}: {count} unique tags")
    print("="*50)

    print("\n✅ Task #2 completed successfully!")
    print(f"Output files:")
    print(f"  - {OUTPUT_DIR / 'exercise_all.json'}")
    print(f"  - {OUTPUT_DIR / 'simulation_all.json'}")
    print(f"  - {OUTPUT_DIR / 'extraction_summary.json'}")

if __name__ == "__main__":
    main()
