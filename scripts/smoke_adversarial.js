export const meta = {
  name: 'smoke-adversarial-critique',
  description: 'smoke: 对抗批判能否抓W08/Q11/Q17 + 不误伤Q8/Q21',
  phases: [{ title: '对抗批判' }],
}
const T = [
  { paper:'皖西', slot:'W08', qtype:'扩展操作码', expect:'issue',
    stem:'/tmp/audit_final/皖西_W08.json', sol:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W08/W08/solution.md', gen:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_nmWX/20260626T233539/questions/W08/W08/gen.py' },
  { paper:'计组A卷', slot:'Q11', qtype:'变形补码', expect:'issue',
    stem:'/tmp/audit_final/计组A卷_Q11.json', sol:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_coA/20260626T233539/questions/Q11/Q11/solution.md', gen:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_coA/20260626T233539/questions/Q11/Q11/gen.py' },
  { paper:'计组A卷', slot:'Q17', qtype:'74LS138片选', expect:'issue',
    stem:'/tmp/audit_final/计组A卷_Q17.json', sol:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_coA/20260626T233539/questions/Q17/Q17/solution.md', gen:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full2_coA/20260626T233539/questions/Q17/Q17/gen.py' },
  { paper:'计组1卷', slot:'Q8', qtype:'Cache容量(对照)', expect:'clean',
    stem:'/tmp/audit_final/计组1卷_Q8.json', sol:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q8/Q8/solution.md', gen:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q8/Q8/gen.py' },
  { paper:'计组1卷', slot:'Q21', qtype:'CPI(对照)', expect:'clean',
    stem:'/tmp/audit_final/计组1卷_Q21.json', sol:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q21/Q21/solution.md', gen:'/data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth/docs/test_output/kaodian_full_计组1卷/20260626T221639/questions/Q21/Q21/gen.py' },
]
const SCHEMA = { type:'object', properties:{
  has_real_issue:{type:'boolean', description:'是否存在会导致学生误解或解出不同/错误答案的真问题(纯文字润色不算)'},
  dimension:{type:'string', enum:['none','前提相干','术语精度','设计完备','其他'], description:'问题维度'},
  severity:{type:'string', enum:['none','cosmetic','minor','major'], description:'none/cosmetic=纯文字不影响解题→通过; minor/major=影响解题→needs_fix'},
  issue_desc:{type:'string', description:'问题具体描述+为何影响解题(或为何只是cosmetic)'},
  verdict:{type:'string', enum:['pass','needs_fix']} },
  required:['has_real_issue','dimension','severity','issue_desc','verdict'] }
const results = await parallel(T.map((t)=>()=>
  agent('你是408试卷【对抗批判员】(不是正向解题员)。用 Read 读: 1)题干 '+t.stem+'  2)官解 '+t.sol+'  3)gen.py '+t.gen+'\n\n'+
    '你的任务不是解题,而是【找题干/建模里会导致学生误解或解出不同答案的隐患】。查三个维度:\n'+
    '① 前提相干: 声称的配置/条数在所述机制下是否真可达? 前提之间是否打架? 建模公式是否忠实机制(扩展操作码是链式前缀预留,不能把某级当独立空间)?\n'+
    '② 术语精度: 关键术语(n位/补码/编址方式/容量口径)换"标准读法"题是否仍成立? 是否会引起不同答案?\n'+
    '③ 设计完备: 片选/译码/地址分配——未使用地址位如何处理? 是否镜像? 使能是否覆盖全部高位?\n\n'+
    '【判定门槛·极重要】对抗审核的核心不是拦题,是拦"真会导致误解/错解"的问题:\n'+
    '  - 纯文字润色、标点、不影响理解的表述瑕疵 → severity=cosmetic, verdict=pass(予以通过);\n'+
    '  - 只有当问题会让学生在标准读法下误解题意、或解出不同/错误答案时 → severity=minor/major, verdict=needs_fix。\n'+
    '给裁决(dimension/severity/issue_desc/verdict)。',
    { label:'批判:'+t.paper+'/'+t.slot, phase:'对抗批判', schema: SCHEMA }
  ).then((v)=>({paper:t.paper, slot:t.slot, qtype:t.qtype, expect:t.expect, ...v}))
))
const clean = results.filter(Boolean)
const flags = clean.filter(r=>r.verdict==='needs_fix')
log('smoke: '+clean.length+'/5; needs_fix '+flags.length+'; 预期issue题: '+(flags.map(f=>f.slot).join(',')))
return { total:clean.length, flagged:flags.length, flags, all:clean }
