export const meta = {
  name: 'reaudit-q11-q17-postfix',
  description: '复验: Q11/Q17 wording_fix后对抗批判是否通过',
  phases: [{ title: '复验' }],
}
const T = [
  { paper:'计组A卷', slot:'Q11', qtype:'变形补码',
    stem:'/tmp/audit_final/计组A卷_Q11.json', sol:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_coA/20260626T233539/questions/Q11/Q11/solution.md', gen:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_coA/20260626T233539/questions/Q11/Q11/gen.py' },
  { paper:'计组A卷', slot:'Q17', qtype:'74LS138片选',
    stem:'/tmp/audit_final/计组A卷_Q17.json', sol:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_coA/20260626T233539/questions/Q17/Q17/solution.md', gen:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_coA/20260626T233539/questions/Q17/Q17/gen.py' },
]
const SCHEMA = { type:'object', properties:{
  has_real_issue:{type:'boolean'}, dimension:{type:'string',enum:['none','前提相干','术语精度','设计完备','其他']},
  severity:{type:'string',enum:['none','cosmetic','minor','major']}, issue_desc:{type:'string'},
  verdict:{type:'string',enum:['pass','needs_fix']} },
  required:['has_real_issue','dimension','severity','issue_desc','verdict'] }
const results = await parallel(T.map((t)=>()=>
  agent('你是408试卷【对抗批判员】。用 Read 读: 1)题干 '+t.stem+'  2)官解 '+t.sol+'  3)gen.py '+t.gen+'\n'+
    '查三维度: ①前提相干(配置/条数在机制下是否可达、前提是否打架、公式是否忠实机制) ②术语精度(换标准读法题是否仍成立) ③设计完备(未用地址位/镜像/使能覆盖)。\n'+
    '门槛: 纯文字不影响解题→cosmetic=pass; 会导致误解/错解→minor/major=needs_fix。给裁决。',
    { label:'复验:'+t.slot, phase:'复验', schema:SCHEMA }
  ).then((v)=>({paper:t.paper,slot:t.slot,qtype:t.qtype,...v}))
))
const clean=results.filter(Boolean)
const flags=clean.filter(r=>r.verdict==='needs_fix')
log('复验 '+clean.length+'/2; 仍 needs_fix '+flags.length)
return { total:clean.length, flagged:flags.length, all:clean }
