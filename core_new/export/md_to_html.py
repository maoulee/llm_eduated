"""Convert exam paper markdown to styled HTML for PDF printing.

Handles:
- $$...$$ display math (preserved before markdown processing)
- $...$ inline math
- ```...``` code blocks (converted to HTML early)
- &emsp;&emsp; options on separate lines
- Ensures list items render on separate lines
"""
import html as html_mod
import re
import sys
from pathlib import Path

import markdown


# Placeholder templates for protecting blocks from markdown processing
_MATH_BLOCK_PH = "<!--MATH_BLOCK_{}-->"
_MATH_INLINE_PH = "<!--MATH_INLINE_{}-->"
_CODE_BLOCK_PH = "<!--CODE_BLOCK_{}-->"
_RAW_HTML_PH = "<!--RAW_HTML_{}-->"


def _preprocess(md_text: str) -> tuple[str, dict[str, str]]:
    """Extract and protect math/code blocks, fix formatting before markdown."""
    saved: dict[str, str] = {}
    counter = [0]

    def _save(content: str, prefix: str) -> str:
        idx = counter[0]
        key = f"{prefix}_{idx}"
        saved[key] = content
        counter[0] += 1
        return f"<!--{prefix}_{idx}-->"

    # 1. Protect fenced code blocks - convert to HTML immediately
    def _code_to_html(m):
        lang = m.group(1) or ""
        code = m.group(2)
        escaped = html_mod.escape(code)
        lang_attr = f' class="language-{lang}"' if lang else ""
        return _save(
            f'<pre><code{lang_attr}>{escaped}</code></pre>',
            "RAW_HTML",
        )

    md_text = re.sub(
        r"```(\w*)\n(.*?)```",
        _code_to_html,
        md_text,
        flags=re.DOTALL,
    )

    # 2. Protect $$...$$ display math (multi-line)
    md_text = re.sub(
        r"\$\$(.*?)\$\$",
        lambda m: _save(
            f'<div class="math-display">\\[{m.group(1)}\\]</div>',
            "MATH_BLOCK",
        ),
        md_text,
        flags=re.DOTALL,
    )

    # 3. Protect $...$ inline math (single line, not $$)
    md_text = re.sub(
        r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)",
        lambda m: _save(f"\\({m.group(1)}\\)", "MATH_INLINE"),
        md_text,
    )

    # 4. Convert &emsp;&emsp; option lines to HTML divs
    md_text = re.sub(
        r"^&emsp;&emsp;(A|B|C|D)\.\s*(.+)$",
        r'<div class="option-line"><strong>\1.</strong> \2</div>',
        md_text,
        flags=re.MULTILINE,
    )

    # 5. Ensure blank line before list items that follow non-blank lines
    # This fixes "- A选项：..." being merged with "**选项分析：**"
    md_text = re.sub(
        r"([^\n])\n(- \w)",
        r"\1\n\n\2",
        md_text,
    )

    return md_text, saved


def _postprocess(html_body: str, saved: dict[str, str]) -> str:
    """Restore protected blocks after markdown processing."""
    for key, content in saved.items():
        placeholder = f"<!--{key}-->"
        # Markdown may wrap placeholders in <p> tags
        html_body = html_body.replace(f"<p>{placeholder}</p>", content)
        html_body = html_body.replace(placeholder, content)
    return html_body


def convert(md_path: str, html_path: str | None = None):
    src = Path(md_path)
    if html_path is None:
        html_path = src.with_suffix(".html")

    md_text = src.read_text(encoding="utf-8")

    # Preprocess: protect math, fix options, ensure list spacing
    md_text, saved = _preprocess(md_text)

    # Convert markdown to HTML
    body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code"],
    )

    # Restore protected blocks
    body = _postprocess(body, saved)

    html = HTML_TEMPLATE.replace("{{BODY}}", body)
    Path(html_path).write_text(html, encoding="utf-8")
    print(f"Generated: {html_path}")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>408 计算机组成原理 模拟试卷</title>
<script>
window.MathJax = {
  tex: {
    inlineMath: [['\\(','\\)']],
    displayMath: [['\\[','\\]']],
    processEscapes: true
  },
  svg: { fontCache: 'global' },
  startup: {
    pageReady: function() {
      MathJax.startup.defaultPageReady().then(function() {
        document.body.classList.add('math-ready');
      });
    }
  }
};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
<style>
@page {
  size: A4;
  margin: 2cm 2.5cm;
}
* { box-sizing: border-box; }
body {
  font-family: "SimSun", "Songti SC", "Noto Serif CJK SC", serif;
  font-size: 12pt;
  line-height: 1.8;
  color: #000;
  max-width: 210mm;
  margin: 0 auto;
  padding: 2cm 2.5cm;
  background: #fff;
}

/* Hide raw latex before MathJax renders */
body:not(.math-ready) .math-display { visibility: hidden; }

/* Headings */
h1 {
  text-align: center;
  font-size: 20pt;
  font-weight: bold;
  border-bottom: 2px solid #000;
  padding-bottom: 10px;
  margin-bottom: 20px;
  font-family: "SimHei", "Heiti SC", sans-serif;
}
h2 {
  font-size: 14pt;
  font-weight: bold;
  margin-top: 28px;
  padding-bottom: 4px;
  border-bottom: 1px solid #999;
  font-family: "SimHei", "Heiti SC", sans-serif;
}
h3 {
  font-size: 13pt;
  font-weight: bold;
  margin-top: 20px;
  font-family: "SimHei", "Heiti SC", sans-serif;
}

/* Blockquote */
blockquote {
  border-left: 3px solid #ccc;
  padding-left: 12px;
  color: #444;
  font-style: italic;
  margin: 12px 0;
}
strong { font-weight: bold; }

/* Inline code */
code {
  font-family: "Consolas", "Courier New", monospace;
  background: #f5f5f5;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 10.5pt;
}

/* Code blocks */
pre {
  background: #f8f8f8;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 12px 16px;
  overflow-x: auto;
  font-size: 10pt;
  line-height: 1.5;
  margin: 12px 0;
}
pre code { background: none; padding: 0; }

/* Tables */
table {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
  font-size: 11pt;
}
th, td {
  border: 1px solid #666;
  padding: 6px 10px;
  text-align: center;
}
th {
  background: #eee;
  font-weight: bold;
}

/* Lists - ensure each item is visually separate */
ul, ol { padding-left: 24px; }
li {
  margin-bottom: 6px;
  line-height: 1.8;
}

/* Options - each on its own line with indent */
.option-line {
  margin: 2px 0 2px 2em;
  line-height: 1.8;
}

/* Math display blocks */
.math-display {
  text-align: center;
  margin: 16px 0;
  overflow-x: auto;
}

/* Paragraphs */
p { margin: 6px 0; }

/* HR */
hr {
  border: none;
  border-top: 1px solid #999;
  margin: 24px 0;
}

/* Print optimization */
@media print {
  body { padding: 0; margin: 0; }
  h2, h3 { page-break-after: avoid; }
  tr, pre, .math-display { page-break-inside: avoid; }
  .no-print { display: none; }
}
</style>
</head>
<body>
{{BODY}}
</body>
</html>
"""


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "docs/exam_paper_clean.md"
    convert(src)
