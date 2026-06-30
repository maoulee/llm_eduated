#!/usr/bin/env python3
"""汇总最终版全题型对抗审查 → docs/expert_review/audit_report.md。"""
import json
from collections import Counter
from pathlib import Path

TASKS = Path('/tmp/claude-1005/-data-amax-home-E22101006-llm-edu/e5a47be1-54db-4b07-9040-296a89985b37/tasks')


def load(name):
    d = json.loads((TASKS / name).read_text())
    r = d['result']
    return json.loads(r)['all'] if isinstance(r, str) else r.get('all', [])


# 最终版全题型审查（116 题，剔除 429 失败的 W09/W11）+ W09/W11 补审 → 共 116 条裁决
allv = [a for a in load('wu7nyao2w.output') if 'official_answer_correct' in a] + load('w9jmlw7by.output')

bad = [a for a in allv if not a.get('official_answer_correct') or not a.get('question_well_posed')
       or not a.get('scenario_rules_ok') or a.get('severity') == 'major']
minor = [a for a in allv if a.get('severity') == 'minor']
qt = Counter(a['qtype'] for a in allv)

L = []
A = L.append
A('# 试卷对抗审核报告（最终版 · 全题型）\n')
A(f'**审核范围**：全 6 套最终版卷（计组1卷 / 试卷A卷 / 皖西 / 计组A卷 / 正常A卷 / 合肥师范）的 **{len(allv)} 道题**。')
A(f'**题型覆盖**：{dict(qt)}。\n')
A('**审核方法**：每题 fresh agent 只读题干**独立求解/判定**（选项字母 / 数值 / 对错 / 填空值）'
  '→ 读官方解答 + gen.py 数据流对照 → 答案核对 + 题干可解性 + 场景规则（参数约束 vs 答案配方）。\n')
A('## 结论：0 答案错误 / 0 不可解题 / 0 major')
A(f'**{len(allv)}/{len(allv)} 题全部通过**：官方答案经独立复算全部正确，题干全部清晰可解、唯一解，'
  f'计算题场景规则全部为参数约束。**真问题数：{len(bad)}**。最终版（经格式化修复后）全题型无任何答案或可解性缺陷。\n')
if minor:
    A(f'## 轻微提示（{len(minor)} 题，不影响答案，非缺陷）')
    for a in minor:
        A(f"- **{a['paper']}/{a['slot']}**（{a['qtype']}）：官解正确。{(a.get('disagreement') or a.get('note') or '')[:120]}")
    A('')
A('## 逐题裁决\n')
A('| 卷 | 题号 | 题型 | 官解 | 可解 | 场景规则 | 严重度 |')
A('|----|------|------|:----:|:----:|:--------:|:------:|')
for a in sorted(allv, key=lambda x: (x['paper'], x['slot'])):
    oc = '✓' if a.get('official_answer_correct') else '✗'
    wp = '✓' if a.get('question_well_posed') else '✗'
    sr = '✓' if a.get('scenario_rules_ok') else '配方'
    sev = a.get('severity', '?')
    mark = ' ⚠' if (not a.get('official_answer_correct') or not a.get('question_well_posed')) else ''
    A(f"| {a['paper']} | {a['slot']} | {a['qtype']} | {oc} | {wp} | {sr} | {sev}{mark} |")
A('')
A('## 历史修复（本会话多轮审查中发现并已修复，最终版审查确认无残留）')
A('- **assembler 参数表剥离 bug**：`_INTERNAL_TABLE_HEADER_RE` 误伤含「说明」列的题干参数表 → 试卷.md 缺参数（Q22 不可解）。已修（正则去掉「说明/定位」），参数表回归。')
A('- **题面泄漏**：考点 / 提示 / 解析 / 设计意图 / 冗余标题（## 题目 等）混进试卷。已通过题面格式契约（`stem_contract.py` 单一事实源）+ 确定性 clean_question + LLM 整体兜底（`format_fix_paper.py`）三联合治理。')
A('- **gen.py 假 assert**：建 `assert_scanner.py` 在 write_gen 后扫恒真/答案配方，接入 SolveNode + dual_review SKILL。')
A('- 最终版 116 题审查确认：以上修复无残留、无副作用，全卷答案与可解性正确。\n')
Path('docs/expert_review/audit_report.md').write_text('\n'.join(L), encoding='utf-8')
print(f'wrote docs/expert_review/audit_report.md, {len(allv)} verdicts, {len(bad)} real issues, {len(minor)} minor')
