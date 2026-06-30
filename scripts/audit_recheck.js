export const meta = {
  name: 'paper-audit-recheck3',
  description: '3题补审(单agent全上下文): Q22/Q28/W08',
  phases: [{ title: '核验' }],
}
const T = [
  { paper: '计组1卷', slot: 'Q22', qtype: '简答题',
    stem: '/tmp/audit_q/计组1卷_Q22.stem.json',
    sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q22/Q22/solution.md',
    gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q22/Q22/gen.py' },
  { paper: '计组1卷', slot: 'Q28', qtype: '设计题',
    stem: '/tmp/audit_q/计组1卷_Q28.stem.json',
    sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q28/Q28/solution.md',
    gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q28/Q28/gen.py' },
  { paper: '皖西', slot: 'W08', qtype: '计算题',
    stem: '/tmp/audit_q/皖西_W08.stem.json',
    sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W08/W08/solution.md',
    gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W08/W08/gen.py' },
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
    '你是 408 对抗审核员。请依次用 Read 读取三份文件后独立核验：\n'+
    '1) 题干(含表格)：'+t.stem+'\n'+
    '2) 官方解答：'+t.sol+'\n'+
    '3) gen.py 数据流建模：'+t.gen+'\n\n'+
    '核验任务：\n'+
    'A. 自己依据题干独立求解（题干里的表格/参数都要看清，别漏），再把你的答案与官解逐项比对。\n'+
    'B. 判断官解答案是否正确（不一致时先判断谁对，给出依据）。\n'+
    'C. 场景规则/通过条件是否为【参数约束】（参数间关系，换参数仍成立）而非【答案配方】（只对当前答案成立）。\n'+
    '注意：题干若含定义表/参数表，必须完整读取后再判断，不可凭片段下结论。给出裁决。',
    { label: '核验:'+t.paper+'/'+t.slot, phase: '核验', schema: SCHEMA }
  ).then((v) => ({ paper: t.paper, slot: t.slot, qtype: t.qtype, ...v }))
))
const clean = results.filter(Boolean)
const flags = clean.filter(r => !r.official_correct || !r.scenario_rules_ok || r.severity==='major')
log('补审 '+clean.length+'/'+T.length+'；标记 '+flags.length)
return { total: clean.length, flagged: flags.length, flags, all: clean }
