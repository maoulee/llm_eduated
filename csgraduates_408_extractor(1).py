#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract text-based 408 questions from csgraduates.com.

Outputs:
  - questions.jsonl: one JSON object per extracted question
  - questions.csv: flattened CSV version
  - skipped.jsonl: skipped questions, mainly those containing img/svg/canvas/picture

Usage:
  pip install requests beautifulsoup4 lxml pandas tqdm
  python csgraduates_408_extractor.py --out ./408_export

Notes:
  - This script skips question blocks containing images/SVG/canvas/picture.
  - It attempts to attach knowledge tags from in-question tag links and, for real exams,
    from /study_methods/tags/408quiz/ reverse mappings.
  - Use the exported content responsibly and respect the website's copyright/robots policy.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup, Tag
from tqdm import tqdm

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "http://www.csgraduates.com"
ROOT = f"{BASE}/study_methods/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


@dataclass
class Question:
    source_type: str          # real_exam | simulation | exercise
    source_title: str
    source_url: str
    year_or_volume: str
    subject: str
    question_no: str
    question_type: str        # choice | open | unknown
    stem: str
    options: dict
    correct_answer: str
    explanation: str
    knowledge_tags: list[str]


@dataclass
class Skipped:
    source_type: str
    source_title: str
    source_url: str
    question_no: str
    reason: str


def fetch(session: requests.Session, url: str, sleep: float = 0.4, retries: int = 8) -> str:
    for attempt in range(retries):
        time.sleep(sleep)
        try:
            r = session.get(url, timeout=25, verify=False)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
            status = getattr(getattr(e, 'response', None), 'status_code', 0)
            if attempt < retries - 1 and (status in (502, 503, 429) or isinstance(e, requests.exceptions.ConnectionError)):
                wait = min((attempt + 1) * 8, 60)  # 8s, 16s, 24s, ... max 60s
                print(f"  Retry {attempt+1}/{retries} for {url} (status={status}, wait {wait}s)...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries")


def clean_text(s: str) -> str:
    s = re.sub(r"\r", "", s)
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def node_text(nodes: Iterable[Tag]) -> str:
    parts = []
    for n in nodes:
        if isinstance(n, Tag):
            parts.append(n.get_text("\n", strip=True))
    return clean_text("\n".join(parts))


def discover_links(session: requests.Session) -> list[tuple[str, str, str]]:
    """Return (source_type, title, url)."""
    soup = BeautifulSoup(fetch(session, ROOT), "lxml")
    out = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(ROOT, a["href"])
        path = urlparse(href).path
        title = clean_text(a.get_text(" ", strip=True))
        source_type = None
        if re.fullmatch(r"/study_methods/408quiz/\d{4}/?", path):
            source_type = "real_exam"
        elif re.fullmatch(r"/study_methods/408simulate/\d+/?", path):
            source_type = "simulation"
        elif "/study_methods/exercise/" in path and not path.rstrip("/").endswith("/exercise"):
            # keep leaf exercise pages, not just category hubs when possible
            source_type = "exercise"
        if source_type and href not in seen:
            seen.add(href)
            out.append((source_type, title, href))
    return out


def build_real_exam_tag_map(session: requests.Session) -> dict[tuple[str, str], list[str]]:
    """Map (year, no) -> tags from the 408 tags page."""
    url = f"{ROOT}tags/408quiz/"
    soup = BeautifulSoup(fetch(session, url), "lxml")
    mapping: dict[tuple[str, str], list[str]] = defaultdict(list)
    current_subject = ""
    current_tag = ""
    for el in soup.find_all(["h3", "h4", "a"]):
        if el.name == "h3":
            current_subject = clean_text(el.get_text(" ", strip=True))
        elif el.name == "h4":
            current_tag = clean_text(el.get_text(" ", strip=True))
        elif el.name == "a" and current_tag:
            txt = clean_text(el.get_text(" ", strip=True))
            m = re.search(r"(20\d{2}) 年 408 真题第\s*(\d+)\s*题", txt)
            if m:
                year, no = m.group(1), m.group(2)
                label = f"{current_subject}>{current_tag}" if current_subject else current_tag
                if label not in mapping[(year, no)]:
                    mapping[(year, no)].append(label)
    return dict(mapping)


def infer_volume(source_type: str, title: str, url: str) -> str:
    if source_type == "real_exam":
        m = re.search(r"(20\d{2})", title) or re.search(r"/(20\d{2})/", url)
        return m.group(1) if m else ""
    if source_type == "simulation":
        m = re.search(r"(\d+)", title) or re.search(r"/408simulate/(\d+)/", url)
        return m.group(1) if m else ""
    return title


def block_has_visual(nodes: list[Tag]) -> bool:
    visual_tags = {"img", "svg", "canvas", "picture", "object"}
    for n in nodes:
        if isinstance(n, Tag) and (n.name in visual_tags or n.find(visual_tags)):
            return True
    # Some math/diagrams are injected as mermaid/svg source blocks.
    text = "\n".join(str(n) for n in nodes)
    return bool(re.search(r"<svg|mermaid|\.svg|<img|data:image", text, re.I))


def parse_options(text: str) -> tuple[str, dict]:
    """Split options if they appear as A. ... B. ... C. ... D. ..."""
    # Remove answer/explanation region before option parsing confusion.
    head = re.split(r"正确答案[:：]", text, maxsplit=1)[0]
    head = re.sub(r"查看答案与解析\s*收藏", "", head)
    pattern = re.compile(r"(?:(?<=\n)|^)([A-D])\s*[\.．、]\s*")
    matches = list(pattern.finditer(head))
    if len(matches) < 2:
        return clean_text(head), {}
    stem = clean_text(head[: matches[0].start()])
    opts = {}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(head)
        opts[m.group(1)] = clean_text(head[start:end])
    return stem, opts


def parse_answer_explanation(text: str) -> tuple[str, str]:
    m = re.search(r"正确答案[:：]\s*([A-D]+|[^\n]+)", text)
    ans = clean_text(m.group(1)) if m else ""
    exp = ""
    if m:
        exp = clean_text(text[m.end():])
    return ans, exp


def local_tags(nodes: list[Tag]) -> list[str]:
    tags = []
    for a in [x for n in nodes if isinstance(n, Tag) for x in n.find_all("a", href=True)]:
        txt = clean_text(a.get_text(" ", strip=True))
        href = a.get("href", "")
        if txt and ("tag" in href or "tags" in href or len(txt) <= 20):
            if txt not in {"查看答案与解析", "收藏"} and txt not in tags:
                tags.append(txt)
    return tags


def parse_page(html: str, source_type: str, source_title: str, source_url: str,
               real_tag_map: dict[tuple[str, str], list[str]]) -> tuple[list[Question], list[Skipped]]:
    soup = BeautifulSoup(html, "lxml")
    volume = infer_volume(source_type, source_title, source_url)
    title_h1 = soup.find("h1")
    if title_h1:
        source_title = clean_text(title_h1.get_text(" ", strip=True)) or source_title

    questions: list[Question] = []
    skipped: list[Skipped] = []
    subject = ""
    qtype = "unknown"

    # We use headings because pages are rendered with h3=section, h4=subject, h5=question no.
    headings = soup.find_all(re.compile("^h[3-5]$"))
    for h in headings:
        text = clean_text(h.get_text(" ", strip=True))
        if h.name == "h3":
            if "选择" in text:
                qtype = "choice"
            elif "解答" in text or "综合" in text:
                qtype = "open"
        elif h.name == "h4":
            subject = text
        elif h.name == "h5" and re.fullmatch(r"\d+", text):
            qno = text
            nodes = []
            for sib in h.next_siblings:
                if isinstance(sib, Tag) and sib.name in {"h3", "h4", "h5"}:
                    break
                if isinstance(sib, Tag):
                    nodes.append(sib)
            if block_has_visual(nodes):
                skipped.append(Skipped(source_type, source_title, source_url, qno, "contains_image_or_svg"))
                continue
            raw = node_text(nodes)
            if not raw or len(raw) < 8:
                continue
            stem, opts = parse_options(raw)
            ans, exp = parse_answer_explanation(raw)
            tags = local_tags(nodes)
            if source_type == "real_exam" and volume:
                for t in real_tag_map.get((volume, qno), []):
                    if t not in tags:
                        tags.append(t)
            # For exercise pages, inherit page/category title when no explicit tag found.
            if source_type == "exercise" and not tags:
                tags = [source_title]
            questions.append(Question(
                source_type=source_type,
                source_title=source_title,
                source_url=source_url,
                year_or_volume=volume,
                subject=subject,
                question_no=qno,
                question_type=qtype,
                stem=stem,
                options=opts,
                correct_answer=ans,
                explanation=exp,
                knowledge_tags=tags,
            ))
    return questions, skipped


def write_outputs(out_dir: Path, questions: list[Question], skipped: list[Skipped]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "questions.jsonl").open("w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(asdict(q), ensure_ascii=False) + "\n")
    with (out_dir / "skipped.jsonl").open("w", encoding="utf-8") as f:
        for s in skipped:
            f.write(json.dumps(asdict(s), ensure_ascii=False) + "\n")
    rows = []
    for q in questions:
        d = asdict(q)
        for k in list("ABCD"):
            d[f"option_{k}"] = q.options.get(k, "")
        d["options"] = json.dumps(q.options, ensure_ascii=False)
        d["knowledge_tags"] = "；".join(q.knowledge_tags)
        rows.append(d)
    fieldnames = [
        "source_type", "source_title", "source_url", "year_or_volume", "subject",
        "question_no", "question_type", "stem", "option_A", "option_B", "option_C", "option_D",
        "correct_answer", "explanation", "knowledge_tags", "options"
    ]
    with (out_dir / "questions.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="408_export", help="output directory")
    ap.add_argument("--sleep", type=float, default=0.4, help="delay between requests")
    ap.add_argument("--limit", type=int, default=0, help="debug: only crawl first N pages")
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    links = discover_links(session)
    # Deduplicate and sort by source type/title/url for reproducibility.
    links = sorted(set(links), key=lambda x: (x[0], x[1], x[2]))
    if args.limit:
        links = links[: args.limit]

    print(f"Discovered {len(links)} candidate pages")
    real_tag_map = build_real_exam_tag_map(session)
    print(f"Built real-exam tag mappings: {sum(len(v) for v in real_tag_map.values())} tag links")

    all_q: list[Question] = []
    all_skipped: list[Skipped] = []
    for source_type, title, url in tqdm(links):
        try:
            html = fetch(session, url, sleep=args.sleep)
            qs, sk = parse_page(html, source_type, title, url, real_tag_map)
            all_q.extend(qs)
            all_skipped.extend(sk)
        except Exception as e:
            all_skipped.append(Skipped(source_type, title, url, "", f"page_error: {type(e).__name__}: {e}"))

    out_dir = Path(args.out)
    write_outputs(out_dir, all_q, all_skipped)
    print(f"Extracted questions: {len(all_q)}")
    print(f"Skipped blocks/pages: {len(all_skipped)}")
    print(f"Wrote: {out_dir / 'questions.jsonl'}")
    print(f"Wrote: {out_dir / 'questions.csv'}")
    print(f"Wrote: {out_dir / 'skipped.jsonl'}")


if __name__ == "__main__":
    main()
