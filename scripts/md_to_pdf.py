#!/usr/bin/env python3
"""MD → PDF 渲染器（weasyprint + markdown）。

将 试卷.md / 答案解析.md 渲染成排版良好的 PDF：
- CJK：Noto Serif CJK SC（正文）/ Noto Sans CJK SC（标题），fontconfig 自动取用。
- 轻量 LaTeX 数学：$...$ 内 ^{}→<sup>、_{}→<sub>、\\overline{x}→CSS 上划线、
  \\times→×、\\leq→≤ 等，不做完整 MathJax（够 408 试卷用）。
- 打印 CSS：A4、页码、题号/选项/表格/代码块样式、答题留白。

用法:
  python scripts/md_to_pdf.py 试卷.md 试卷.pdf
  python scripts/md_to_pdf.py 答案解析.md 答案解析.pdf --title "答案与解析"
  python scripts/md_to_pdf.py --dir docs/test_output/kaodian_full_计组1卷/20260626T221639
"""
import argparse
import re
import sys
from pathlib import Path

import markdown
from weasyprint import HTML

# ---- 轻量 LaTeX → HTML（仅处理 $...$ / $$...$$ 内的常见符号） ----
_TEX_SYMBOLS = {
    r"\times": "×", r"\cdot": "·", r"\leq": "≤", r"\geq": "≥", r"\neq": "≠",
    r"\leql": "≦", r"\geql": "≧", r"\approx": "≈", r"\equiv": "≡",
    r"\pm": "±", r"\mp": "∓", r"\to": "→", r"\rightarrow": "→",
    r"\leftarrow": "←", r"\infty": "∞", r"\sum": "∑", r"\Sigma": "Σ",
    r"\Pi": "Π", r"\prod": "∏", r"\partial": "∂", r"\sqrt": "√",
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\theta": "θ", r"\lambda": "λ", r"\mu": "μ", r"\pi": "π",
    r"\sigma": "σ", r"\omega": "ω", r"\Delta": "Δ", r"\Omega": "Ω",
    r"\in": "∈", r"\notin": "∉", r"\subset": "⊂", r"\supset": "⊃",
    r"\cup": "∪", r"\cap": "∩", r"\forall": "∀", r"\exists": "∃",
    r"\neg": "¬", r"\land": "∧", r"\lor": "∨", r"\bullet": "•",
    r"\degree": "°", r"\ldots": "…", r"\cdots": "⋯",
}


def _tex_to_html(inner: str) -> str:
    """把一段 LaTeX 数学正文转成 HTML 片段（非完整渲染，覆盖常见 408 用法）。"""
    s = inner
    for cmd, sym in _TEX_SYMBOLS.items():
        s = s.replace(cmd, sym)
    # \overline{...} / \bar{...} → CSS 上划线
    s = re.sub(r"\\(?:overline|bar)\{([^{}]*)\}", r'<span class="ol">\1</span>', s)
    # \frac{a}{b} → a/b（分数，竖排太重，用斜线）
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", s)
    # \text{...} → 去命令留内容
    s = re.sub(r"\\(?:text|mathrm|mathit|mathbf)\{([^{}]*)\}", r"\1", s)
    # ^{...} / ^x → 上标；_{...} / _x → 下标
    s = re.sub(r"\^\{([^{}]+)\}", r"<sup>\1</sup>", s)
    s = re.sub(r"\^([0-9A-Za-z+\-])", r"<sup>\1</sup>", s)
    s = re.sub(r"_\{([^{}]+)\}", r"<sub>\1</sub>", s)
    s = re.sub(r"_([0-9A-Za-z])", r"<sub>\1</sub>", s)
    # 残留的反斜杠命令（如 \, \; 间距）去掉
    s = re.sub(r"\\[,;:!]", " ", s)
    return s


def _render_math(md_text: str) -> str:
    """把全文 $...$ / $$...$$ 数学段替换为 HTML（在 markdown 之前处理）。"""
    def repl(m: re.Match) -> str:
        return _tex_to_html(m.group(1))
    # $$...$$ 先（display），再 $...$（inline）
    out = re.sub(r"\$\$([^$]+)\$\$", lambda m: f"\n\n{_tex_to_html(m.group(1))}\n\n", md_text)
    out = re.sub(r"\$([^$\n]+)\$", repl, out)
    return out


CSS = """
@page {
  size: A4;
  margin: 20mm 18mm 20mm 18mm;
  @bottom-center { content: counter(page) " / " counter(pages); font-size: 9pt; color: #888; }
}
* { box-sizing: border-box; }
body {
  font-family: "Noto Serif CJK SC", "Source Han Serif SC", "SimSun", serif;
  font-size: 11pt; line-height: 1.75; color: #1a1a1a;
}
h1, h2, h3, h4 { font-family: "Noto Sans CJK SC", "Source Han Sans SC", sans-serif; font-weight: 600; line-height: 1.35; }
h1 { font-size: 19pt; text-align: center; margin: 0 0 4pt; padding-bottom: 8pt; border-bottom: 2px solid #333; }
h2 { font-size: 13.5pt; margin: 18pt 0 6pt; padding: 3pt 0 3pt 8pt; border-left: 4px solid #c96442; background: #f7f1ec; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; color: #333; }
h3::before { content: ""; }
p { margin: 4pt 0; text-align: justify; }
ul, ol { margin: 4pt 0 4pt 0; padding-left: 1.6em; }
li { margin: 2pt 0; }
/* 大题序号（## 一、…）整段加重 */
h2 { page-break-after: avoid; }
h3, h4 { page-break-after: avoid; }
/* 表格 */
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 10pt; }
th, td { border: 1px solid #999; padding: 4pt 7pt; text-align: left; vertical-align: top; }
th { background: #efe7e0; font-family: "Noto Sans CJK SC", sans-serif; }
tr:nth-child(even) td { background: #faf7f4; }
/* 代码块（公式/数据流） */
pre { background: #f5f3f0; border: 1px solid #e0dad3; border-radius: 4px; padding: 7pt 9pt;
      font-family: "DejaVu Sans Mono", "Noto Sans Mono CJK SC", monospace; font-size: 9.5pt;
      white-space: pre-wrap; word-wrap: break-word; line-height: 1.5; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 9.5pt; background: #f5f3f0; padding: 0 2pt; border-radius: 2px; }
pre code { background: none; padding: 0; }
/* 数学：上标/下标/上划线 */
sup { font-size: 0.72em; vertical-align: super; line-height: 0; }
sub { font-size: 0.72em; vertical-align: sub; line-height: 0; }
.ol { text-decoration: overline; text-decoration-thickness: 1px; }
/* 分隔线 */
hr { border: none; border-top: 1px solid #ccc; margin: 10pt 0; }
/* 选项行（A. B. C. D.）微调 */
strong { font-weight: 600; }
blockquote { border-left: 3px solid #c96442; margin: 6pt 0; padding: 2pt 10pt; color: #555; background: #faf7f4; }
"""


def md_to_pdf(md_path: Path, pdf_path: Path, *, title: str | None = None) -> dict:
    md_text = md_path.read_text(encoding="utf-8")
    if title:  # 覆盖/前置标题
        md_text = f"# {title}\n\n" + md_text
    md_text = _render_math(md_text)
    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "md_in_html", "attr_list"],
    )
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html_body}</body></html>"
    HTML(string=html).write_pdf(str(pdf_path))
    return {"pdf": str(pdf_path), "bytes": pdf_path.stat().st_size}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("md", nargs="?")
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--title", default=None)
    ap.add_argument("--dir", help="装订目录：渲染其中的 试卷.md + 答案解析.md")
    args = ap.parse_args()

    if args.dir:
        d = Path(args.dir)
        out = []
        for name in ("试卷.md", "答案解析.md"):
            src = d / name
            if src.exists():
                dst = d / (src.stem + ".pdf")
                r = md_to_pdf(src, dst)
                out.append(r)
                print(f"[OK] {src.name} -> {dst.name} ({r['bytes']//1024} KB)")
        print(f"=== 渲染 {len(out)} 份 ===")
        return

    if not args.md or not args.pdf:
        ap.error("需要 md pdf，或 --dir")
    md_to_pdf(Path(args.md), Path(args.pdf), title=args.title)
    print(f"[OK] {args.md} -> {args.pdf}")


if __name__ == "__main__":
    sys.exit(main() or 0)
