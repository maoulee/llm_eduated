#!/usr/bin/env python3
"""整体兜底格式修复智能体：读整张 试卷.md，识别并精确删除一切"非题面"内容。

设计要点（LLM 全卷重写会改题面，不安全；故采用"LLM 列要删片段 + 确定性精确删除"）：
  - LLM 阅读全卷，把所有"非题面"内容（设计脚手架/解题提示/元数据/解析的整行整段）
    【逐字复制】出来，每条用 <DEL> ... </DEL> 包裹。LLM 只识别、不改写。
  - 脚本对每条 <DEL> 片段在原文里做**精确字符串匹配**——命中才删，不命中跳过。
    => 删除是确定性的，LLM 无法改写/新增题面内容（最坏情况是漏删，不会误改）。
  - 命中并删除的片段若疑似新泄漏模式，可回填到 stem_contract.py（让确定性 clean_question
    以后也能拦），形成"LLM 发现 → 契约沉淀"的闭环。

用法:
  python scripts/format_fix_paper.py docs/.../questions/试卷.md          # 原地修
  python scripts/format_fix_paper.py docs/.../questions/试卷.md --dry    # 只看会删什么
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core_new.llm_gateway import get_gateway  # noqa: E402
from core_new.doc_pipeline.stem_contract import STEM_FORMAT_RULES  # noqa: E402

PROMPT = (
    "你是试卷格式最终修复者。下面给你一张完整试卷（markdown）。其中可能混入「非题面」内容"
    "（设计脚手架/解题提示/元数据/答案解析）。请按下列契约，把所有该删除的内容"
    "**逐字原样复制**出来，每一条用 <DEL> 开头、</DEL> 结尾包裹。\n\n"
    f"{STEM_FORMAT_RULES}\n\n"
    "要求（极重要）：\n"
    "1) 只输出要【删除】的片段，每条 <DEL>原文逐字片段</DEL>。多行片段就把多行整段包在一条 <DEL>里。\n"
    "2) 片段必须与原文**逐字一致**（含空白、标点、全半角）——你会被精确匹配，改一个字就删不掉。\n"
    "3) **绝不**输出题干、选项、子问、题内表格、大题标题、题号——这些是题面，保留。\n"
    "4) 题干行内的括注（如（von Neumann）、（IEEE 754））、公式、英文——一律**保留**，不要列。\n"
    "5) 若全卷已无任何非题面内容，直接输出一行：<NONE>\n"
    "6) 不要解释、不要额外文字，只输出 <DEL>...</DEL> 条目（或 <NONE>）。\n\n"
    "【试卷原文】\n\n"
)
_DEL_RE = re.compile(r"<DEL>(.*?)</DEL>", re.S)


async def _llm_list_deletions(paper_text: str) -> list[str]:
    gw = get_gateway("glm5.2_anthropic")
    msgs = [{"role": "user", "content": PROMPT + paper_text}]
    res = await gw.stream_chat(
        msgs, role="final_review", max_tokens=16000, enable_thinking=False,
    )
    content = (res.get("content") or "").strip()
    if content == "<NONE>" or "<DEL>" not in content:
        return []
    return [m.group(1) for m in _DEL_RE.finditer(content)]


def fix_paper(md_path: Path, *, dry: bool = False) -> dict:
    original = md_path.read_text(encoding="utf-8")
    deletions = asyncio.run(_llm_list_deletions(original))
    removed, not_found = [], []
    for snip in deletions:
        s = snip.strip("\n")
        if s and s in original:
            removed.append(s)
            original = original.replace(s, "", 1)
        elif s:
            not_found.append(s[:70])
    info = {
        "listed": len(deletions), "removed": len(removed),
        "not_found": len(not_found), "not_found_samples": not_found[:5],
    }
    if dry:
        info["action"] = "dry-run (未写)"
        info["removed_samples"] = [r[:70] for r in removed[:5]]
        return info
    # 只在确实有删除时写回；清理多余空行
    if removed:
        cleaned = re.sub(r"\n{4,}", "\n\n\n", original).rstrip() + "\n"
        md_path.write_text(cleaned, encoding="utf-8")
        info["action"] = f"已写入 {md_path.name}（删 {len(removed)} 处）"
    else:
        info["action"] = "无需修改"
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("md", help="试卷.md 路径")
    ap.add_argument("--dry", action="store_true", help="只列不写")
    args = ap.parse_args()
    info = fix_paper(Path(args.md), dry=args.dry)
    print(f"listed={info['listed']} removed={info['removed']} not_found={info['not_found']} action={info['action']}")
    if info.get("removed_samples"):
        print("删除样本:")
        for s in info["removed_samples"]:
            print(f"  - {s}")
    if info["not_found_samples"]:
        print("未命中(LLM 复制走样, 跳过):")
        for s in info["not_found_samples"]:
            print(f"  - {s}")


if __name__ == "__main__":
    main()
