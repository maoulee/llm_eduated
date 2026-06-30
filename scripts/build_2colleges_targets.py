#!/usr/bin/env python3
"""为合肥师范 + 池州学院 两套构建三档审核目标（stem 文件 + T.js 索引）。"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from api.services.paper_assembler import _read_slot, clean_question  # noqa: E402

ABS = '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth'
PAPERS = [
    ('合肥师范', 'docs/test_output/kaodian_full2_nmHF/20260627T011949'),
    ('池州学院', 'docs/test_output/kaodian_full2_nmA/20260627T011949'),
]
T = []
for paper, runp in PAPERS:
    run = ROOT / runp
    qd = run / 'questions'
    h = yaml.safe_load((run / 'paper_request.yaml').read_text(encoding='utf-8'))
    for s in h['slots']:
        sid = str(s.get('slot_id'))
        qt = s.get('题型') or '综合题'
        sp = qd / sid / 'solution.md'
        gp = qd / sid / 'gen.py'
        if not sp.exists() and (qd / sid / sid / 'solution.md').exists():
            sp = qd / sid / sid / 'solution.md'
            gp = qd / sid / sid / 'gen.py'
        if not sp.exists():
            continue
        stem = clean_question(_read_slot(qd, sid, 'question')).strip()
        stemf = f'/tmp/audit_final/{paper}_{sid}.json'
        json.dump({'qtype': qt, 'stem': stem}, open(stemf, 'w'), ensure_ascii=False)
        sol_abs = str(sp.resolve())
        gen_abs = str(gp.resolve()) if gp.exists() else ''
        T.append((paper, sid, qt, stemf, sol_abs, gen_abs))

lines = []
for paper, sid, qt, stem, sol, gen in T:
    gen_field = f", gen: '{gen}'" if gen else ", gen: ''"
    lines.append(f"  {{ paper: '{paper}', slot: '{sid}', qtype: '{qt}', stem: '{stem}', sol: '{sol}'{gen_field} }},")
Path('/tmp/audit_final/_T_2colleges.js').write_text('\n'.join(lines), encoding='utf-8')
print(f'2 学院目标: {len(T)} 题')
for r in T[:3]:
    print(' ', r[0], r[1], r[2])
