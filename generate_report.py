"""Generate full experiment report from experiment_full_trace.json — no truncation."""

import json
import os

def main():
    trace_path = "docs/experiment_full_trace.json"
    if not os.path.exists(trace_path):
        print(f"ERROR: {trace_path} not found. Run run_full_trace.py first.")
        return

    with open(trace_path, encoding="utf-8") as f:
        data = json.load(f)

    # Load extraction MDs
    extractions = {}
    for item in data:
        qid = item["question_id"]
        path = f"docs/extractions/{qid}.md"
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f2:
                extractions[qid] = f2.read()

    lines = []
    L = lines.append

    L("# 实验报告 — Qwen3.6-27B 408考试题完整追踪")
    L("")
    L("> 日期: 2026-05-14 | 模型: Qwen3.6-27B-AWQ-INT4 | 推理引擎: 本地vLLM")
    L(">")
    L("> 参数: temperature=1.0, top_p=0.95, top_k=20, max_tokens=8192, thinking=chat_template_kwargs")
    L("")
    L("---")
    L("")

    # === Summary ===
    L("## 总览")
    L("")
    L("| # | 题目 | 正确答案 | S1推理 | S2推理 | S2代码 | S2代码执行 | S3推理 | S3代码 | S3代码执行 | 变化 |")
    L("|---|------|----------|--------|--------|--------|-----------|--------|--------|-----------|------|")
    for i, item in enumerate(data, 1):
        qid = item["question_id"]
        gt = item["ground_truth"]
        s1 = item["s1"]
        s2 = item["s2"]
        s3 = item["s3"]
        s1ok = "Y" if s1["correct"] else "N"
        s2rok = "Y" if s2["reason_correct"] else "N"
        s2cok = "Y" if s2.get("code_exec_success") else "-"
        s2exec = "OK" if s2.get("code_exec_success") else "FAIL"
        s3rok = "Y" if s3["reason_correct"] else "N"
        s3cok = "Y" if s3.get("code_exec_success") else "-"
        s3exec = "OK" if s3.get("code_exec_success") else "FAIL"
        # improvement
        s2_any = s2["reason_correct"] or s2.get("code_exec_success", False)
        s3_any = s3["reason_correct"] or s3.get("code_exec_success", False)
        if s3_any and not s2_any:
            ch = "IMPROVED"
        elif not s3_any and s2_any:
            ch = "REGRESSED"
        elif s3["reason_correct"] and s2["reason_correct"]:
            ch = "SAME (both ok)"
        else:
            ch = "SAME (both wrong)"
        L(f"| {i} | {qid} | {gt} | {s1ok} | {s2rok} | {s2cok} | {s2exec} | {s3rok} | {s3cok} | {s3exec} | {ch} |")
    L("")

    s1c = sum(1 for r in data if r["s1"]["correct"])
    s2rc = sum(1 for r in data if r["s2"]["reason_correct"])
    s2ec = sum(1 for r in data if r["s2"].get("code_exec_success"))
    s3rc = sum(1 for r in data if r["s3"]["reason_correct"])
    s3ec = sum(1 for r in data if r["s3"].get("code_exec_success"))
    L(f"**S1推理正确**: {s1c}/6 | **S2推理正确**: {s2rc}/6 | **S2代码执行成功**: {s2ec}/6 | **S3推理正确**: {s3rc}/6 | **S3代码执行成功**: {s3ec}/6")
    L("")
    L("---")
    L("")

    # === Per question ===
    for i, item in enumerate(data, 1):
        qid = item["question_id"]
        gt = item["ground_truth"]
        ksum = item.get("knowledge_summary", "")
        s1 = item["s1"]
        s2 = item["s2"]
        s3 = item["s3"]

        L(f"## {i}. {qid}")
        L("")
        L(f"**正确答案**: {gt}")
        L("")
        L("---")
        L("")

        # --- S1 ---
        L("### Setting 1: 纯推理")
        L("")
        L("#### 提示语")
        L("")
        L("```")
        L(s1["prompt"])
        L("```")
        L("")
        L(f"**提取答案**: `{s1['extracted_answer']}` | **正确**: {'是' if s1['correct'] else '否'} | **耗时**: {s1['time']}s")
        L("")
        L("#### 思考过程 (thinking)")
        L("")
        L(s1["thinking"])
        L("")
        L("#### 最终回答 (answer)")
        L("")
        L(s1["answer"])
        L("")
        L("---")
        L("")

        # --- S2 ---
        L("### Setting 2: 推理 + 代码 (无知识注入)")
        L("")
        L("#### 推理提示语")
        L("")
        L("```")
        L(s2["reason_prompt"])
        L("```")
        L("")
        L(f"**提取答案**: `{s2['reason_extracted']}` | **正确**: {'是' if s2['reason_correct'] else '否'}")
        L("")
        L("##### 推理思考过程")
        L("")
        L(s2["reason_thinking"])
        L("")
        L("##### 推理最终回答")
        L("")
        L(s2["reason_answer"])
        L("")
        L("---")
        L("")

        L("#### 代码提示语")
        L("")
        L("```")
        L(s2["code_prompt"])
        L("```")
        L("")
        L(f"**代码生成**: {'成功' if s2['code_extracted'] else '失败(未生成)'} | **执行**: {'成功' if s2['code_exec_success'] else '失败'}")
        L("")
        L("##### 代码思考过程")
        L("")
        L(s2["code_thinking"])
        L("")
        L("##### 代码最终回答 (含生成的代码)")
        L("")
        L(s2["code_answer"])
        L("")
        if s2["code_extracted"]:
            L("##### 提取出的代码")
            L("")
            L("```python")
            L(s2["code_extracted"])
            L("```")
            L("")
        if s2.get("code_exec_success"):
            L(f"##### 代码执行输出")
            L("")
            L("```")
            L(s2["code_exec_output"])
            L("```")
            L("")
            L(f"**代码计算答案**: `{s2.get('code_final_answer', '')}`")
        elif s2.get("code_exec_error"):
            L(f"##### 代码执行错误")
            L("")
            L("```")
            L(s2["code_exec_error"])
            L("```")
            L("")
        L("")
        L("---")
        L("")

        # --- S3 ---
        L("### Setting 3: 推理 + 代码 (有知识注入)")
        L("")
        L("#### 注入的知识摘要")
        L("")
        L("```")
        L(ksum)
        L("```")
        L("")
        L("#### 推理提示语 (带知识)")
        L("")
        L("```")
        L(s3["reason_prompt"])
        L("```")
        L("")
        L(f"**提取答案**: `{s3['reason_extracted']}` | **正确**: {'是' if s3['reason_correct'] else '否'}")
        L("")
        L("##### 推理思考过程")
        L("")
        L(s3["reason_thinking"])
        L("")
        L("##### 推理最终回答")
        L("")
        L(s3["reason_answer"])
        L("")
        L("---")
        L("")

        L("#### 代码提示语 (带知识)")
        L("")
        L("```")
        L(s3["code_prompt"])
        L("```")
        L("")
        L(f"**代码生成**: {'成功' if s3['code_extracted'] else '失败(未生成)'} | **执行**: {'成功' if s3['code_exec_success'] else '失败'}")
        L("")
        L("##### 代码思考过程")
        L("")
        L(s3["code_thinking"])
        L("")
        L("##### 代码最终回答 (含生成的代码)")
        L("")
        L(s3["code_answer"])
        L("")
        if s3["code_extracted"]:
            L("##### 提取出的代码")
            L("")
            L("```python")
            L(s3["code_extracted"])
            L("```")
            L("")
        if s3.get("code_exec_success"):
            L(f"##### 代码执行输出")
            L("")
            L("```")
            L(s3["code_exec_output"])
            L("```")
            L("")
            L(f"**代码计算答案**: `{s3.get('code_final_answer', '')}`")
        elif s3.get("code_exec_error"):
            L(f"##### 代码执行错误")
            L("")
            L("```")
            L(s3["code_exec_error"])
            L("```")
            L("")
        L("")
        L("---")
        L("")

        # --- Extraction ---
        if qid in extractions:
            L("### 结构化抽取结果 (完整)")
            L("")
            L(extractions[qid])
            L("")
            L("---")
            L("")

    # Write
    report = "\n".join(lines)
    out_path = "docs/experiment_report.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report: {len(lines)} lines, {len(report)} chars -> {out_path}")


if __name__ == "__main__":
    main()
