export const meta = {
  name: 'paper-audit-blind-resolve',
  description: '对抗审核：盲解复算+对照官解，验场景规则，抓 2MB 类事实错',
  phases: [
    { title: '盲解', detail: 'fresh agent 只读题干独立求解' },
    { title: '对照', detail: '读官解+gen.py 比答案+验场景规则' },
  ],
}

const T = [
  { paper: '计组1卷', slot: 'Q21', key: '计组1卷_Q21', qtype: '简答题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q21/Q21/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q21/Q21/gen.py' },
  { paper: '计组1卷', slot: 'Q22', key: '计组1卷_Q22', qtype: '简答题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q22/Q22/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q22/Q22/gen.py' },
  { paper: '计组1卷', slot: 'Q23', key: '计组1卷_Q23', qtype: '简答题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q23/Q23/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q23/Q23/gen.py' },
  { paper: '计组1卷', slot: 'Q24', key: '计组1卷_Q24', qtype: '简答题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q24/Q24/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q24/Q24/gen.py' },
  { paper: '计组1卷', slot: 'Q25', key: '计组1卷_Q25', qtype: '简答题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q25/Q25/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q25/Q25/gen.py' },
  { paper: '计组1卷', slot: 'Q26', key: '计组1卷_Q26', qtype: '简答题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q26/Q26/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q26/Q26/gen.py' },
  { paper: '计组1卷', slot: 'Q27', key: '计组1卷_Q27', qtype: '简答题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q27/Q27/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q27/Q27/gen.py' },
  { paper: '计组1卷', slot: 'Q28', key: '计组1卷_Q28', qtype: '设计题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q28/Q28/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q28/Q28/gen.py' },
  { paper: '试卷A卷', slot: 'Q1', key: '试卷A卷_Q1', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q1/solution.md', gen_abs: '' },
  { paper: '试卷A卷', slot: 'Q2', key: '试卷A卷_Q2', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q2/solution.md', gen_abs: '' },
  { paper: '试卷A卷', slot: 'Q3', key: '试卷A卷_Q3', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q3/solution.md', gen_abs: '' },
  { paper: '试卷A卷', slot: 'Q4', key: '试卷A卷_Q4', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q4/solution.md', gen_abs: '' },
  { paper: '试卷A卷', slot: 'Q5', key: '试卷A卷_Q5', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q5/Q5/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q5/Q5/gen.py' },
  { paper: '试卷A卷', slot: 'Q6', key: '试卷A卷_Q6', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q6/Q6/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q6/Q6/gen.py' },
  { paper: '试卷A卷', slot: 'Q7', key: '试卷A卷_Q7', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q7/Q7/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q7/Q7/gen.py' },
  { paper: '试卷A卷', slot: 'Q8', key: '试卷A卷_Q8', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q8/Q8/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q8/Q8/gen.py' },
  { paper: '试卷A卷', slot: 'Q11', key: '试卷A卷_Q11', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q11/Q11/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q11/Q11/gen.py' },
  { paper: '试卷A卷', slot: 'Q12', key: '试卷A卷_Q12', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q12/Q12/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_试卷A卷/20260626T221639/questions/Q12/Q12/gen.py' },
  { paper: '皖西', slot: 'W01', key: '皖西_W01', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W01/solution.md', gen_abs: '' },
  { paper: '皖西', slot: 'W02', key: '皖西_W02', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W02/solution.md', gen_abs: '' },
  { paper: '皖西', slot: 'W03', key: '皖西_W03', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W03/solution.md', gen_abs: '' },
  { paper: '皖西', slot: 'W04', key: '皖西_W04', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W04/solution.md', gen_abs: '' },
  { paper: '皖西', slot: 'W05', key: '皖西_W05', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W05/W05/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W05/W05/gen.py' },
  { paper: '皖西', slot: 'W06', key: '皖西_W06', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W06/W06/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W06/W06/gen.py' },
  { paper: '皖西', slot: 'W07', key: '皖西_W07', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W07/W07/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W07/W07/gen.py' },
  { paper: '皖西', slot: 'W08', key: '皖西_W08', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W08/W08/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W08/W08/gen.py' },
  { paper: '皖西', slot: 'W11', key: '皖西_W11', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W11/W11/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W11/W11/gen.py' },
  { paper: '皖西', slot: 'W12', key: '皖西_W12', qtype: '计算题', sol_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W12/W12/solution.md', gen_abs: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W12/W12/gen.py' },]

const SOLVE_SCHEMA = {
  type: 'object',
  properties: {
    derived_answer: { type: 'string', description: '独立求得的最终答案' },
    method: { type: 'string', description: '关键求解步骤' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    ambiguous: { type: 'boolean', description: '题干是否有歧义/多解' },
  },
  required: ['derived_answer', 'method', 'confidence', 'ambiguous'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    official_correct: { type: 'boolean', description: '官解答案是否正确' },
    scenario_rules_ok: { type: 'boolean', description: '场景规则是否参数约束(非答案配方)' },
    discrepancy: { type: 'string' },
    severity: { type: 'string', enum: ['none', 'minor', 'major'] },
    note: { type: 'string' },
  },
  required: ['official_correct', 'scenario_rules_ok', 'severity', 'discrepancy', 'note'],
}

const results = await pipeline(
  T,
  // Stage 1: 盲解（只读题干文件，不接触官解）
  (t) => agent(
    `你是 408 考试阅卷专家。先用 Read 工具读取题干文件 /tmp/audit_q/${t.key}.stem.json（只含题型与题干，不含答案）。然后独立求解这道${t.qtype}：一步步算/推导，不要猜。若题干有歧义或条件不足导致多解，必须指出。返回你的最终答案与关键步骤。禁止读取任何 solution.md / gen.py，只依据题干。`,
    { label: `盲解:${t.paper}/${t.slot}`, phase: '盲解', schema: SOLVE_SCHEMA }
  ).then((r) => ({ ...t, solve: r })),
  // Stage 2: 对照官解 + 验场景规则
  async (prev, t) => {
    const s = prev.solve
    const verify = await agent(
      `你是对抗审核员。一道${t.qtype}（${t.paper}/${t.slot}）刚由独立求解得到：\n独立答案=${s.derived_answer}\n方法=${s.method}\n独立求解认为${s.ambiguous ? '题干有歧义/多解' : '题干明确'}\n\n用 Read 工具读取官方解答（绝对路径）：${t.sol_abs}${t.gen_abs ? `，以及 gen.py 数据流建模（绝对路径）：${t.gen_abs}` : ''}。做两件事：\n1. 答案核对：官解答案是否正确？与独立答案是否一致？不一致时判断谁对（独立解或官解都可能错，给出你的判断依据）。\n2. 场景规则审核：官解/题干里"场景规则/通过条件"是【参数约束】（参数间必须成立的关系，换参数仍成立）还是【答案配方】（只对当前答案成立，如"答案=2MB"）？答案配方=不合格。\n给出裁决。`,
      { label: `对照:${t.paper}/${t.slot}`, phase: '对照', schema: VERIFY_SCHEMA }
    )
    return { paper: t.paper, slot: t.slot, qtype: t.qtype,
             derived: s.derived_answer, ambiguous: s.ambiguous,
             official_correct: verify.official_correct, scenario_rules_ok: verify.scenario_rules_ok,
             severity: verify.severity, discrepancy: verify.discrepancy, note: verify.note }
  }
)

const clean = results.filter(Boolean)
const flags = clean.filter(r => !r.official_correct || !r.scenario_rules_ok || r.severity === 'major')
log(`审核完成: ${clean.length}/${T.length} 题；标记 ${flags.length} 题待查`)
return { total: clean.length, flagged: flags.length, flags, all: clean }
