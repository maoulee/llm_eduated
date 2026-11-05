"""Convert debug JSON dumps into a readable Markdown trajectory report."""
import json
import sys
from pathlib import Path


def _truncate(text: str, max_len: int = 2000) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n... (truncated, total {len(text)} chars)"


def _fmt_val(val, indent=0) -> str:
    """Format a value for markdown display."""
    prefix = "  " * indent
    if isinstance(val, dict):
        if not val:
            return "{}"
        lines = []
        for k, v in val.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{prefix}- **{k}**:")
                lines.append(_fmt_val(v, indent + 1))
            else:
                sv = _truncate(str(v), 500)
                lines.append(f"{prefix}- **{k}**: {sv}")
        return "\n".join(lines)
    elif isinstance(val, list):
        if not val:
            return "[]"
        lines = []
        for i, item in enumerate(val):
            if isinstance(item, dict):
                lines.append(f"{prefix}- [{i}]:")
                lines.append(_fmt_val(item, indent + 1))
            else:
                lines.append(f"{prefix}- {item}")
        return "\n".join(lines)
    else:
        return _truncate(str(val), 2000)


def build_report(debug_dir: Path) -> str:
    """Build markdown report from all debug JSON files in a directory."""
    files = sorted(debug_dir.glob("*.json"))
    if not files:
        return f"No debug JSON files found in {debug_dir}"

    parts = [f"# Pipeline Debug Report: {debug_dir.name}\n"]

    # Pipeline summary first
    summary_files = [f for f in files if "summary.json" in f.name and "r0" not in f.name]
    other_files = [f for f in files if f not in summary_files]

    for fp in summary_files:
        data = json.loads(fp.read_text(encoding="utf-8"))
        parts.append("## Pipeline Summary\n")
        parts.append(f"- **Slot**: {data.get('slot_id', '?')}")
        parts.append(f"- **Total Time**: {data.get('total_time_s', 0):.1f}s")
        parts.append(f"- **Rounds**: {data.get('rounds', '?')}")
        parts.append(f"- **Solver Execs**: {data.get('solver_execs', '?')}")
        parts.append(f"- **Review Status**: {data.get('review_status', 'N/A')}")
        parts.append(f"- **Review Quality**: {data.get('review_quality', 'N/A')}")
        stem = data.get('final_stem', '')
        if stem:
            parts.append(f"\n### Final Stem\n{_truncate(stem, 1000)}\n")

    for fp in other_files:
        data = json.loads(fp.read_text(encoding="utf-8"))
        slot = data.get("slot_id", "?")
        step = data.get("step", "?")
        rnd = data.get("round", "?")
        ts = data.get("timestamp", "?")

        parts.append(f"\n## {step} (round {rnd}) — {ts}\n")

        # Input
        inp = data.get("input")
        if inp:
            parts.append("### Input\n")
            parts.append(_fmt_val(inp))
            parts.append("")

        # Output
        out = data.get("output")
        if out:
            parts.append("### Output\n")
            # Special formatting for known output types
            if "structural_errors" in out:
                parts.append(f"**Structural Errors**: {out['structural_errors']}")
            elif "status" in out and "issues" in out:
                # FinalReview / Consistency style
                parts.append(f"- **Status**: {out.get('status', '?')}")
                parts.append(f"- **Quality**: {out.get('overall_quality', '?')}")
                issues = out.get("issues", "")
                if issues:
                    parts.append(f"\n**Issues:**\n{_truncate(str(issues), 1500)}")
                fix = out.get("fix_instruction")
                if fix and isinstance(fix, dict):
                    parts.append(f"\n**Fix Target**: {fix.get('fix_target', '?')}")
                    fd = fix.get('fix_detail', '')
                    if fd:
                        parts.append(f"**Fix Detail**: {_truncate(fd, 1000)}")
                conflicts = out.get("conflicts")
                if conflicts:
                    parts.append(f"\n**Conflicts** ({len(conflicts)}):")
                    for c in conflicts:
                        parts.append(f"  - {c.get('field_a','?')} vs {c.get('field_b','?')} — {c.get('severity','?')}: {_truncate(str(c.get('value_a','')),200)}")
                raw = out.get("_raw_text")
                if raw:
                    parts.append(f"\n<details><summary>Raw LLM Output ({len(raw)} chars)</summary>\n\n```\n{_truncate(raw, 3000)}\n```\n</details>")
            elif "fix_applied" in out:
                # Fixer output
                parts.append(f"- **Status**: {out.get('status', '?')}")
                parts.append(f"- **Fix Applied**: {_truncate(str(out.get('fix_applied', '')), 500)}")
            else:
                parts.append(_fmt_val(out))
            parts.append("")

    return "\n".join(parts)


if __name__ == "__main__":
    debug_dir = sys.argv[1] if len(sys.argv) > 1 else "debug/Q43_20260531_135019"
    report = build_report(Path(debug_dir))
    out_path = Path(debug_dir) / "trajectory_report.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"Report written to: {out_path}")
    print(report)
