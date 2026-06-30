export const meta = {
  name: 'audit-w09-w11-recheck',
  description: '补审皖西 W09/W11 (上轮429失败)',
  phases: [{ title: '补审' }],
}
const T = [
  { paper:'皖西', slot:'W09', qtype:'分析题', stem:'/tmp/audit_final/皖西_W09.json',
    sol:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W09/W09/solution.md',
    gen:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W09/W09/gen.py' },
  { paper:'皖西', slot:'W11', qtype:'设计题', stem:'/tmp/audit_final/皖西_W11.json',
    sol:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W11/W11/solution.md',
    gen:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W11/W11/gen.py' },
]
const SCHEMA = { type:'object', properties:{
  official_answer_correct:{type:'boolean'}, my_answer:{type:'string'}, disagreement:{type:'string'},
  question_well_posed:{type:'boolean'}, well_posedness_issue:{type:'string'},
  scenario_rules_ok:{type:'boolean'}, severity:{type:'string',enum:['none','minor','major']}, note:{type:'string'} },
  required:['official_answer_correct','question_well_posed','scenario_rules_ok','severity','disagreement','note'] }
const results = await parallel(T.map((t)=>()=>
  agent('你是408对抗审查员。Read: 1)题干 '+t.stem+'  2)官解 '+t.sol+'  3)gen.py '+t.gen+'\n'+
    '题型='+t.qtype+'。A.只依题干独立求解。B.对照官解,不一致判谁对。C.题干可解性(缺条件/多解/歧义)。D.场景规则是否参数约束。给裁决。',
    { label:'补审:'+t.slot, phase:'补审', schema:SCHEMA }
  ).then((v)=>({paper:t.paper,slot:t.slot,qtype:t.qtype,...v}))
))
const clean=results.filter(Boolean)
const flags=clean.filter(r=>!r.official_answer_correct||!r.question_well_posed||!r.scenario_rules_ok||r.severity==='major')
log('补审 '+clean.length+'/2; 标记 '+flags.length)
return { total:clean.length, flagged:flags.length, flags, all:clean }
