#!/usr/bin/env python3
"""Per-question experience extraction using local vLLM.

Generates detailed experience files for each question, aligned with
the format in data/question_experiences/*.md.

Usage:
    python scripts/experience_extractor.py --source real_exam
    python scripts/experience_extractor.py --source exercise
    python scripts/experience_extractor.py --source simulation
    python scripts/experience_extractor.py --source all
    python scripts/experience_extractor.py --source real_exam --workers 8 --limit 50
"""

import json
import os
import re
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
EXP_DIR = DATA_DIR / "question_experiences"
STRUCTURED_DIR = DATA_DIR / "structured_questions"
VLLM_URL = "http://localhost:8000/v1"
MODEL = "/zhaoshu/llm/Qwen3.6-27B-FP8"

SUBJECT_MAP = {
    "计算机组成原理": "CO", "组成原理": "CO",
    "数据结构": "DS",
    "操作系统": "OS",
    "计算机网络": "CN",
}

K_RADAR = """K1 基础认知需求（需要调用概念/术语/公式记忆的程度）:
  1=微弱 2=较低 3=标准 4=较高 5=极高
  锚点：不记忆408知识能否入题 → 能则1，需一个核心定义则3，需辨析两个以上易混概念则4-5
K2 单步代入需求（需要执行单次直接计算/转换的程度）:
  1=微弱 2=较低 3=标准 4=较高 5=极高
  锚点：最复杂的单步计算是否可能算错 → 2的幂友好则2，非2幂次则3，多级换算则4-5
K3 机制推演需求（需要在明确规则下多步串行推演的程度）:
  1=微弱 2=较低 3=标准 4=较高 5=极高
  锚点：从输入到输出需几步 → 1-2步则1-2，3-5步则3，>5步或需记忆中间状态则4-5
K4 条件路由需求（需要识别隐含前提/避开暗坑/切换机制的程度）:
  1=微弱 2=较低 3=标准 4=较高 5=极高
  锚点：有没有"题面没说但解题必须意识到的条件" → 无则1，常规注意点则2，陷阱词则3，隐含前提深则4，反直觉则5
K5 跨域联动需求（需要跨越不同子系统/模块传递状态的程度）:
  1=微弱 2=较低 3=标准 4=较高 5=极高
  锚点：是否需在不同子系统间传递数据或状态 → 单系统则1，提及无关则2，单向传数据则3，状态互影响则4，深度耦合则5"""


def build_choice_prompt(q: dict) -> str:
    """Build prompt for choice questions."""
    stem = q.get("stem", "")[:500]
    opts = q.get("options", {})
    opts_text = ""
    if isinstance(opts, dict) and opts:
        opts_text = "\n".join(f"  {k}: {v}" for k, v in opts.items())
    answer = q.get("correct_answer", "")
    explanation = clean_explanation(q.get("explanation", ""))[:300]
    tags = q.get("knowledge_tags", [])
    domain = q.get("knowledge_domain", "")
    subject = q.get("subject", "")

    basic_info = build_basic_info(q)

    return f"""你是408考研题目深度分析专家。请对以下选择题进行全方位分析。

## 基本信息
{basic_info}

## 题目数据
- 题干: {stem}
- 选项:
{opts_text}
- 正确答案: {answer}
- 解析（参考）: {explanation}
- 知识标签: {tags}
- 知识域: {domain}

## K难度雷达标准
{K_RADAR}

## 输出要求

请直接输出markdown格式的分析报告（不要用代码块标记），严格按照以下章节顺序输出。

第一行标题格式: # XXXX年 QXX — 知识点核心概括（注意"年"字不能少）

## 基本信息
直接复用上面给出的基本信息内容

## 题干原文
完整题干原文

## K1-K5 评分与解析
对每个K维度评分（1-5）并给出理由，格式:
- **K1 = N**: 评分理由。不是X分因为...
- **K2 = N**: 评分理由
- **K3 = N**: 评分理由
- **K4 = N**: 评分理由
- **K5 = N**: 评分理由
- **雷达形状**: 描述形状特征（如K4陷阱型、均衡型、K2计算型等）

## 考察模式
- **模式**: 概念型/计算型/推理型/综合型
- **理由**: 为什么属于这个模式

## 选项级分析
对每个选项逐一分析:
- **选项X**: [干扰/正确] — 针对什么错误认知，这类学生为什么会选这个
- 最后给出 **干扰策略**: 渐进陷阱/概念混淆/计算陷阱等

## 核心陷阱
- **核心陷阱**: 最关键的陷阱是什么

## 考察能力
一句话概括本题核心考察的能力"""


def build_comprehensive_prompt(q: dict) -> str:
    """Build prompt for comprehensive/open questions."""
    stem = q.get("stem", "")[:800]
    answer = q.get("correct_answer", "")
    explanation = clean_explanation(q.get("explanation", ""))[:400]
    tags = q.get("knowledge_tags", [])
    domain = q.get("knowledge_domain", "")

    basic_info = build_basic_info(q)

    return f"""你是408考研题目深度分析专家。请对以下综合题进行全方位分析。

## 基本信息
{basic_info}

## 题目数据
- 题干: {stem}
- 参考答案: {answer}
- 解析（参考）: {explanation}
- 知识标签: {tags}
- 知识域: {domain}

## K难度雷达标准
{K_RADAR}

## 输出要求

请直接输出markdown格式的分析报告（不要用代码块标记），严格按照以下章节顺序输出。

第一行标题格式: # 年份 Q题号 — 知识点核心概括

## 基本信息
直接复用上面给出的基本信息内容

## 题干原文
完整题干原文

## K1-K5 评分与解析
对每个K维度评分（1-5）并给出理由，格式:
- **K1 = N**: 评分理由。不是X分因为...
- **K2 = N**: 评分理由
- **K3 = N**: 评分理由
- **K4 = N**: 评分理由
- **K5 = N**: 评分理由
- **雷达形状**: 描述形状特征

## 考察模式
- **模式**: 算法设计型/分析论证型/计算推导型/综合型
- **理由**: 为什么属于这个模式

## 解题思路分析
- **核心思路**: 整体解题策略
- **关键步骤**: 分步解析
- **易错点**: 学生容易犯的错误

## 核心陷阱
- **核心陷阱**: 最关键的难点或陷阱

## 考察能力
一句话概括本题核心考察的能力"""


def build_basic_info(q: dict) -> str:
    """Build basic info section based on question source and type."""
    source = q.get("source_type", "") or ("real_exam" if q.get("year") else "")
    qtype = q.get("question_type", "")
    tags = q.get("knowledge_tags", [])

    if source == "real_exam" or q.get("year"):
        year = q.get("year", "")
        qno = q.get("question_no", "")
        slot = q.get("slot_id", "")
        subject = q.get("subject", "")
        return (
            f"- **年份**: {year}  **题位**: Q{qno}  **题型**: {'选择题' if qtype == 'choice' else '综合题'}\n"
            f"- **知识点**: {', '.join(tags[:5]) if tags else '待标注'}\n"
            f"- **题位域**: {slot or '待标注'}  **科目**: {subject}"
        )
    else:
        subject = q.get("subject", "")
        difficulty = q.get("difficulty_level", "")
        return (
            f"- **来源**: {'练习题' if source == 'exercise' else '模拟题'}  **题型**: {'选择题' if qtype == 'choice' else '综合题'}\n"
            f"- **科目**: {subject}\n"
            f"- **知识点**: {', '.join(tags[:5]) if tags else '待标注'}\n"
            f"- **难度**: {difficulty or '待评估'}"
        )


def clean_explanation(text: str) -> str:
    """Remove JS garbage from explanation."""
    if not text:
        return ""
    # Remove indexedDB / class / constructor / async patterns
    text = re.sub(r'class\s+\w+.*', '', text, flags=re.DOTALL)
    text = re.sub(r'async\s+\w+.*', '', text, flags=re.DOTALL)
    text = re.sub(r'const\s+\w+.*', '', text, flags=re.DOTALL)
    # Remove remaining JS patterns
    text = re.sub(r'\{.*?\.prototype.*?\}', '', text)
    text = re.sub(r'(function|var|let|new |return |=>).*', '', text)
    return text.strip()[:300]


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
                    q["_source"] = src
                all_q.extend(qs)
        return all_q

    path = files.get(source)
    if not path or not path.exists():
        print(f"File not found: {path}")
        return []
    with open(path) as f:
        qs = json.load(f)
    for q in qs:
        q["_source"] = source
    return qs


def needs_extraction(q: dict) -> bool:
    """Check if question needs experience extraction."""
    fpath = EXP_DIR / f"{q['id']}.md"
    return not fpath.exists()


def call_vllm(client: OpenAI, prompt: str) -> str | None:
    """Call vLLM with thinking disabled."""
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.15,
                max_tokens=3000,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            content = resp.choices[0].message.content
            if content and content.strip():
                return content.strip()
        except Exception as e:
            print(f"    vLLM error (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return None


def extract_one(client: OpenAI, q: dict) -> tuple[str, str | None]:
    """Extract experience for one question. Returns (id, content or None)."""
    qid = q["id"]
    qtype = q.get("question_type", "")

    if qtype == "choice":
        prompt = build_choice_prompt(q)
    else:
        prompt = build_comprehensive_prompt(q)

    content = call_vllm(client, prompt)
    return (qid, content)


def clean_output(content: str, q: dict) -> str:
    """Clean and normalize the LLM output."""
    # Remove code block markers if present
    content = re.sub(r'^```(?:markdown)?\s*\n?', '', content)
    content = re.sub(r'\n?```\s*$', '', content)

    # Ensure title starts with # (not ##)
    if not content.startswith('#'):
        # Try to find the first # line
        m = re.search(r'^#\s+', content, re.MULTILINE)
        if m:
            content = content[m.start():]
        else:
            # Generate a basic title
            year = q.get("year", "")
            qno = q.get("question_no", "")
            tags = q.get("knowledge_tags", [])
            tag_str = tags[0].split(">")[-1].strip() if tags else q.get("subject", "")
            content = f"# {year}年 Q{qno} — {tag_str}\n\n{content}"

    return content.strip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="Per-question experience extraction")
    parser.add_argument("--source", choices=["real_exam", "exercise", "simulation", "all"],
                        default="real_exam", help="Which source to process")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers")
    parser.add_argument("--limit", type=int, default=0, help="Max questions (0=all)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    EXP_DIR.mkdir(parents=True, exist_ok=True)
    client = OpenAI(base_url=VLLM_URL, api_key="dummy")

    # Load and filter
    questions = load_questions(args.source)
    if not args.overwrite:
        questions = [q for q in questions if needs_extraction(q)]

    if args.limit > 0:
        questions = questions[:args.limit]

    print(f"Source: {args.source}")
    print(f"To extract: {len(questions)} questions")
    print(f"Workers: {args.workers}")

    if not questions:
        print("Nothing to extract!")
        return

    # Process with thread pool
    done = 0
    failed = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for q in questions:
            f = pool.submit(extract_one, client, q)
            futures[f] = q

        for f in as_completed(futures):
            q = futures[f]
            qid = q["id"]
            try:
                qid, content = f.result()
                if content:
                    content = clean_output(content, q)
                    fpath = EXP_DIR / f"{qid}.md"
                    fpath.write_text(content, encoding="utf-8")
                    done += 1
                else:
                    failed += 1
                    print(f"  FAIL {qid}: empty response")
            except Exception as e:
                failed += 1
                print(f"  FAIL {qid}: {e}")

            # Progress
            total = done + failed
            if total % 20 == 0 or total == len(questions):
                elapsed = time.time() - start
                rate = total / elapsed if elapsed > 0 else 0
                eta = (len(questions) - total) / rate if rate > 0 else 0
                print(f"  Progress: {total}/{len(questions)} done={done} fail={failed} "
                      f"rate={rate:.1f}/s eta={eta/60:.1f}min")

    elapsed = time.time() - start
    print(f"\nDone! Extracted: {done}, Failed: {failed}, Time: {elapsed/60:.1f}min")


if __name__ == "__main__":
    main()
