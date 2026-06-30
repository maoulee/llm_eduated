export const meta = {
  name: 'paper-audit-batch3',
  description: 'nmA+nmHF 18题对抗审核(单agent全上下文)',
  phases: [{ title: '核验' }],
}
const T = [
  { paper: '正常A卷', slot: 'A11', key: '正常A卷_A11', qtype: '计算题', stem: '/tmp/audit_q2/正常A卷_A11.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A11/A11/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A11/A11/gen.py' },
  { paper: '正常A卷', slot: 'A12', key: '正常A卷_A12', qtype: '计算题', stem: '/tmp/audit_q2/正常A卷_A12.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A12/A12/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A12/A12/gen.py' },
  { paper: '正常A卷', slot: 'A13', key: '正常A卷_A13', qtype: '计算题', stem: '/tmp/audit_q2/正常A卷_A13.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A13/A13/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A13/A13/gen.py' },
  { paper: '正常A卷', slot: 'A14', key: '正常A卷_A14', qtype: '计算题', stem: '/tmp/audit_q2/正常A卷_A14.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A14/A14/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A14/A14/gen.py' },
  { paper: '正常A卷', slot: 'A15', key: '正常A卷_A15', qtype: '计算题', stem: '/tmp/audit_q2/正常A卷_A15.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A15/A15/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A15/A15/gen.py' },
  { paper: '正常A卷', slot: 'A16', key: '正常A卷_A16', qtype: '计算题', stem: '/tmp/audit_q2/正常A卷_A16.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A16/A16/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A16/A16/gen.py' },
  { paper: '正常A卷', slot: 'A17', key: '正常A卷_A17', qtype: '综合题', stem: '/tmp/audit_q2/正常A卷_A17.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A17/A17/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A17/A17/gen.py' },
  { paper: '正常A卷', slot: 'A18', key: '正常A卷_A18', qtype: '综合题', stem: '/tmp/audit_q2/正常A卷_A18.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A18/A18/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A18/A18/gen.py' },
  { paper: '正常A卷', slot: 'A19', key: '正常A卷_A19', qtype: '综合题', stem: '/tmp/audit_q2/正常A卷_A19.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A19/A19/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A19/A19/gen.py' },
  { paper: '正常A卷', slot: 'A20', key: '正常A卷_A20', qtype: '综合题', stem: '/tmp/audit_q2/正常A卷_A20.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A20/A20/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A20/A20/gen.py' },
  { paper: '合肥师范', slot: 'Q17', key: '合肥师范_Q17', qtype: '简答题', stem: '/tmp/audit_q2/合肥师范_Q17.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q17/Q17/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q17/Q17/gen.py' },
  { paper: '合肥师范', slot: 'Q18', key: '合肥师范_Q18', qtype: '简答题', stem: '/tmp/audit_q2/合肥师范_Q18.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q18/Q18/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q18/Q18/gen.py' },
  { paper: '合肥师范', slot: 'Q19', key: '合肥师范_Q19', qtype: '简答题', stem: '/tmp/audit_q2/合肥师范_Q19.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q19/Q19/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q19/Q19/gen.py' },
  { paper: '合肥师范', slot: 'Q20', key: '合肥师范_Q20', qtype: '简答题', stem: '/tmp/audit_q2/合肥师范_Q20.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q20/Q20/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q20/Q20/gen.py' },
  { paper: '合肥师范', slot: 'Q21', key: '合肥师范_Q21', qtype: '简答题', stem: '/tmp/audit_q2/合肥师范_Q21.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q21/Q21/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q21/Q21/gen.py' },
  { paper: '合肥师范', slot: 'Q22', key: '合肥师范_Q22', qtype: '应用题', stem: '/tmp/audit_q2/合肥师范_Q22.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q22/Q22/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q22/Q22/gen.py' },
  { paper: '合肥师范', slot: 'Q23', key: '合肥师范_Q23', qtype: '设计题', stem: '/tmp/audit_q2/合肥师范_Q23.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q23/Q23/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q23/Q23/gen.py' },
  { paper: '合肥师范', slot: 'Q24', key: '合肥师范_Q24', qtype: '设计题', stem: '/tmp/audit_q2/合肥师范_Q24.stem.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q24/Q24/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q24/Q24/gen.py' },
]
const SCHEMA = {
  type: 'object',
  properties: {
    official_correct: { type: 'boolean' },
    scenario_rules_ok: { type: 'boolean' },
    your_answer: { type: 'string' },
    discrepancy: { type: 'string' },
    severity: { type: 'string', enum: ['none','minor','major'] },
    note: { type: 'string' },
  },
  required: ['official_correct','scenario_rules_ok','severity','discrepancy','note'],
}
const results = await parallel(T.map((t) => () =>
  agent(
    '你是 408 对抗审核员。依次用 Read 读取后独立核验：\n'+
    '1) 题干(含全部表格/参数)：'+t.stem+'\n'+
    '2) 官方解答：'+t.sol+(t.gen ? '\n3) gen.py 数据流：'+t.gen : '')+'\n\n'+
    '任务：A. 自己依据题干独立求解（表格/参数都要看清，别漏），再与官解逐项比对。\n'+
    'B. 判断官解答案是否正确（不一致先判谁对，给依据）。\n'+
    'C. 场景规则/通过条件是【参数约束】(换参仍成立) 还是【答案配方】(只对当前答案成立)。\n'+
    '注意：题干表格/参数必须完整读取后再判，不可凭片段下结论。给裁决。',
    { label: '核验:'+t.paper+'/'+t.slot, phase: '核验', schema: SCHEMA }
  ).then((v) => ({ paper: t.paper, slot: t.slot, qtype: t.qtype, ...v }))
))
const clean = results.filter(Boolean)
const flags = clean.filter(r => !r.official_correct || !r.scenario_rules_ok || r.severity==='major')
log('batch3 审核 '+clean.length+'/'+T.length+'；标记 '+flags.length)
return { total: clean.length, flagged: flags.length, flags, all: clean }
