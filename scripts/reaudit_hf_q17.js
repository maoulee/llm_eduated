export const meta = { name:'reaudit-hf-q17', description:'补审合肥师范Q17(429)', phases:[{title:'补审'}] }
const T = [{ paper:'合肥师范', slot:'Q17', qtype:'简答题',
  stem:'/tmp/audit_final/合肥师范_Q17.json',
  sol:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q17/Q17/solution.md',
  gen:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmHF/20260627T011949/questions/Q17/Q17/gen.py' }]
const SCHEMA = { type:'object', properties:{
  tier:{type:'string',enum:['none','expression_only','ambiguity','error']},
  dimension:{type:'string'}, issue_desc:{type:'string'}, fix_text:{type:'string'} },
  required:['tier','dimension','issue_desc','fix_text'] }
const r = await parallel(T.map((t)=>()=>
  agent('你是408对抗批判员。Read 题干 '+t.stem+' 官解 '+t.sol+' gen.py '+t.gen+'。查前提相干/术语精度/设计完备，归档: error/ambiguity/expression_only/none。expression_only档给"原文→修正"片段。',
    { label:'补审:HF/Q17', phase:'补审', schema:SCHEMA }).then((v)=>({paper:t.paper,slot:t.slot,...v}))))
return { all: r.filter(Boolean) }
