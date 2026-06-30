export const meta = {
  name: 'tier-audit-2colleges',
  description: '合肥师范+池州学院 三档对抗审核(歧义/仅表述/出错)',
  phases: [{ title: '三档审核' }],
}
const T = [
  { paper: '合肥师范', slot: 'Q01', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q01.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q01/Q01/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q01/Q01/gen.py' },
  { paper: '合肥师范', slot: 'Q02', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q02.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q02/Q02/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q02/Q02/gen.py' },
  { paper: '合肥师范', slot: 'Q03', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q03.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q03/solution.md', gen: '' },
  { paper: '合肥师范', slot: 'Q04', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q04.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q04/Q04/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q04/Q04/gen.py' },
  { paper: '合肥师范', slot: 'Q05', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q05.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q05/solution.md', gen: '' },
  { paper: '合肥师范', slot: 'Q06', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q06.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q06/solution.md', gen: '' },
  { paper: '合肥师范', slot: 'Q07', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q07.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q07/Q07/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q07/Q07/gen.py' },
  { paper: '合肥师范', slot: 'Q08', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q08.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q08/solution.md', gen: '' },
  { paper: '合肥师范', slot: 'Q09', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q09.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q09/solution.md', gen: '' },
  { paper: '合肥师范', slot: 'Q10', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q10.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q10/Q10/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q10/Q10/gen.py' },
  { paper: '合肥师范', slot: 'Q11', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q11.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q11/solution.md', gen: '' },
  { paper: '合肥师范', slot: 'Q12', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q12.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q12/Q12/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q12/Q12/gen.py' },
  { paper: '合肥师范', slot: 'Q13', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q13.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q13/solution.md', gen: '' },
  { paper: '合肥师范', slot: 'Q14', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q14.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q14/solution.md', gen: '' },
  { paper: '合肥师范', slot: 'Q15', qtype: '单项选择题', stem: '/tmp/audit_final/合肥师范_Q15.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q15/solution.md', gen: '' },
  { paper: '合肥师范', slot: 'Q16', qtype: '填空题', stem: '/tmp/audit_final/合肥师范_Q16.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q16/Q16/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q16/Q16/gen.py' },
  { paper: '合肥师范', slot: 'Q17', qtype: '简答题', stem: '/tmp/audit_final/合肥师范_Q17.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q17/Q17/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q17/Q17/gen.py' },
  { paper: '合肥师范', slot: 'Q18', qtype: '简答题', stem: '/tmp/audit_final/合肥师范_Q18.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q18/Q18/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q18/Q18/gen.py' },
  { paper: '合肥师范', slot: 'Q19', qtype: '简答题', stem: '/tmp/audit_final/合肥师范_Q19.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q19/Q19/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q19/Q19/gen.py' },
  { paper: '合肥师范', slot: 'Q20', qtype: '简答题', stem: '/tmp/audit_final/合肥师范_Q20.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q20/Q20/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q20/Q20/gen.py' },
  { paper: '合肥师范', slot: 'Q21', qtype: '简答题', stem: '/tmp/audit_final/合肥师范_Q21.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q21/Q21/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q21/Q21/gen.py' },
  { paper: '合肥师范', slot: 'Q22', qtype: '应用题', stem: '/tmp/audit_final/合肥师范_Q22.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q22/Q22/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q22/Q22/gen.py' },
  { paper: '合肥师范', slot: 'Q23', qtype: '设计题', stem: '/tmp/audit_final/合肥师范_Q23.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q23/Q23/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q23/Q23/gen.py' },
  { paper: '合肥师范', slot: 'Q24', qtype: '设计题', stem: '/tmp/audit_final/合肥师范_Q24.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q24/Q24/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q24/Q24/gen.py' },
  { paper: '池州学院', slot: 'A01', qtype: '单项选择题', stem: '/tmp/audit_final/池州学院_A01.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A01/A01/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A01/A01/gen.py' },
  { paper: '池州学院', slot: 'A02', qtype: '单项选择题', stem: '/tmp/audit_final/池州学院_A02.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A02/A02/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A02/A02/gen.py' },
  { paper: '池州学院', slot: 'A03', qtype: '单项选择题', stem: '/tmp/audit_final/池州学院_A03.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A03/solution.md', gen: '' },
  { paper: '池州学院', slot: 'A04', qtype: '单项选择题', stem: '/tmp/audit_final/池州学院_A04.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A04/solution.md', gen: '' },
  { paper: '池州学院', slot: 'A05', qtype: '单项选择题', stem: '/tmp/audit_final/池州学院_A05.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A05/solution.md', gen: '' },
  { paper: '池州学院', slot: 'A06', qtype: '判断题', stem: '/tmp/audit_final/池州学院_A06.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A06/solution.md', gen: '' },
  { paper: '池州学院', slot: 'A07', qtype: '判断题', stem: '/tmp/audit_final/池州学院_A07.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A07/solution.md', gen: '' },
  { paper: '池州学院', slot: 'A08', qtype: '判断题', stem: '/tmp/audit_final/池州学院_A08.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A08/solution.md', gen: '' },
  { paper: '池州学院', slot: 'A09', qtype: '判断题', stem: '/tmp/audit_final/池州学院_A09.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A09/solution.md', gen: '' },
  { paper: '池州学院', slot: 'A10', qtype: '判断题', stem: '/tmp/audit_final/池州学院_A10.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A10/solution.md', gen: '' },
  { paper: '池州学院', slot: 'A11', qtype: '计算题', stem: '/tmp/audit_final/池州学院_A11.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A11/A11/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A11/A11/gen.py' },
  { paper: '池州学院', slot: 'A12', qtype: '计算题', stem: '/tmp/audit_final/池州学院_A12.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A12/A12/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A12/A12/gen.py' },
  { paper: '池州学院', slot: 'A13', qtype: '计算题', stem: '/tmp/audit_final/池州学院_A13.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A13/A13/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A13/A13/gen.py' },
  { paper: '池州学院', slot: 'A14', qtype: '计算题', stem: '/tmp/audit_final/池州学院_A14.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A14/A14/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A14/A14/gen.py' },
  { paper: '池州学院', slot: 'A15', qtype: '计算题', stem: '/tmp/audit_final/池州学院_A15.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A15/A15/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A15/A15/gen.py' },
  { paper: '池州学院', slot: 'A16', qtype: '计算题', stem: '/tmp/audit_final/池州学院_A16.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A16/A16/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A16/A16/gen.py' },
  { paper: '池州学院', slot: 'A17', qtype: '综合题', stem: '/tmp/audit_final/池州学院_A17.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A17/A17/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A17/A17/gen.py' },
  { paper: '池州学院', slot: 'A18', qtype: '综合题', stem: '/tmp/audit_final/池州学院_A18.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A18/A18/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A18/A18/gen.py' },
  { paper: '池州学院', slot: 'A19', qtype: '综合题', stem: '/tmp/audit_final/池州学院_A19.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A19/A19/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A19/A19/gen.py' },
  { paper: '池州学院', slot: 'A20', qtype: '综合题', stem: '/tmp/audit_final/池州学院_A20.json', sol: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A20/A20/solution.md', gen: '/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmA/20260627T011949/questions/A20/A20/gen.py' },]

const SCHEMA = {
  type: 'object',
  properties: {
    tier: { type: 'string', enum: ['none','expression_only','ambiguity','error'],
            description: 'none=无问题; expression_only=仅表述不精准但无歧义不改求解; ambiguity=可两读可能改求解; error=前提冲突/答案错/设计坏' },
    dimension: { type: 'string', description: '问题维度(前提相干/术语精度/设计完备/答案/其他), none时填none' },
    issue_desc: { type: 'string', description: '问题具体描述; none时填无' },
    fix_text: { type: 'string', description: '仅表述档: 给出可直接替换的修正后原文片段(逐字可定位); 歧义/出错档: 修复方向; none时填无' },
  },
  required: ['tier','dimension','issue_desc','fix_text'],
}

const results = await parallel(T.map((t) => () =>
  agent(
    '你是408试卷【对抗批判员】。用 Read 读: 1)题干 '+t.stem+'  2)官解 '+t.sol+(t.gen ? '  3)gen.py '+t.gen : '')+'\n'+
    '查三维度: ①前提相干(配置/条数在所述机制下是否可达、前提打架、公式是否忠实机制) ②术语精度(关键术语换标准读法题是否仍成立) ③设计完备(未用地址位/镜像/使能覆盖)。\n\n'+
    '【把每个发现归到恰好一档】\n'+
    '- error: 前提不可行/答案错/设计坏(如扩展操作码参数超编码容量、片选有未识别镜像却谎称全覆盖) → 必须重生成。\n'+
    '- ambiguity: 文字可两读、且换种标准读法会得到不同/错误答案(如n位补码歧义) → 需消歧+复审。\n'+
    '- expression_only: 文字不精准/口误/标点/位数标注错, 但**只有一种合理读法、不影响求解** → 模型直接改、不用复审。\n'+
    '- none: 无问题。\n\n'+
    '【fix_text 要求】expression_only 档: 给出"原文片段→修正后片段"(逐字、可精确定位替换); 其他档给修复方向。\n'+
    '门槛铁律: 只有"换读法会改变答案/误解"才算 ambiguity/error; 纯润色=expression_only。给裁决。',
    { label: '审:'+t.paper+'/'+t.slot, phase: '三档审核', schema: SCHEMA }
  ).then((v) => ({ paper: t.paper, slot: t.slot, qtype: t.qtype, ...v }))
))
const clean = results.filter(Boolean)
const byTier = { expression_only: [], ambiguity: [], error: [] }
for (const r of clean) { if (byTier[r.tier]) byTier[r.tier].push(r) }
log('三档审核 '+clean.length+'/44; 仅表述='+byTier.expression_only.length+' 歧义='+byTier.ambiguity.length+' 出错='+byTier.error.length)
return { total: clean.length, by_tier: byTier, all: clean }
