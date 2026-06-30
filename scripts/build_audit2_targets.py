#!/usr/bin/env python3
"""为 nmA + nmHF 计算题构建审核目标（stem 文件 + T.js 索引）。"""
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from api.services.paper_assembler import _read_slot, clean_question  # noqa: E402

PAPERS = [
    ('正常A卷', 'docs/test_output/kaodian_full2_nmA/20260627T011949'),
    ('合肥师范', 'docs/test_output/kaodian_full2_nmHF/20260627T011949'),
]
os.makedirs('/tmp/audit_q2', exist_ok=True)
T = []
for paper, runp in PAPERS:
    run = ROOT / runp
    qd = run / 'questions'
    h = yaml.safe_load((run / 'paper_request.yaml').read_text(encoding='utf-8'))
    for s in h['slots']:
        sid = str(s.get('slot_id'))
        qt = s.get('题型') or ''
        if not any(k in qt for k in ('计算', '设计', '应用', '综合', '简答')):
            continue
        stem = clean_question(_read_slot(qd, sid, 'question')).strip()
        if len(stem) < 20:
            continue
        sp = qd / sid / 'solution.md'
        gp = qd / sid / 'gen.py'
        if not sp.exists() and (qd / sid / sid / 'solution.md').exists():
            sp = qd / sid / sid / 'solution.md'
            gp = qd / sid / sid / 'gen.py'
        if not sp.exists():
            continue
        key = f'{paper}_{sid}'
        json.dump({'qtype': qt, 'stem': stem}, open(f'/tmp/audit_q2/{key}.stem.json', 'w'), ensure_ascii=False)
        sol_abs = str(sp.resolve())
        gen_abs = str(gp.resolve()) if gp.exists() else ''
        T.append((paper, sid, key, qt, f'/tmp/audit_q2/{key}.stem.json', sol_abs, gen_abs))

lines = []
for paper, sid, key, qt, stem, sol, gen in T:
    gen_field = f", gen: '{gen}'" if gen else ", gen: ''"
    lines.append(f"  {{ paper: '{paper}', slot: '{sid}', key: '{key}', qtype: '{qt}', stem: '{stem}', sol: '{sol}'{gen_field} }},")
Path('/tmp/audit_q2/_T.js').write_text('\n'.join(lines), encoding='utf-8')
print(f'nmA+nmHF calc targets: {len(T)}')
for r in T[:4]:
    print(' ', r[0], r[1], r[3])
