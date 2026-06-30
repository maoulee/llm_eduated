#!/bin/bash
# 全面重跑编排：3 批 × 2 套并行，自动衔接 + 日志
cd /data/amax/home/E22101006/llm_edu/llm_eduated_code_as_truth
source .venv/bin/activate 2>/dev/null
LOG=/tmp/full_rerun.log
echo "$(date) === orchestrator started ===" > $LOG

# --- 等 batch 1（已启动：full_计组1卷 + full_试卷A卷）---
echo "waiting batch 1 (计组1卷 + 试卷A卷)..." >> $LOG
while true; do
  b1=$(grep -c 'TOTAL' "/tmp/full_计组1卷.log" 2>/dev/null || echo 0)
  b2=$(grep -c 'TOTAL' "/tmp/full_试卷A卷.log" 2>/dev/null || echo 0)
  if [ "${b1:-0}" -ge 1 ] && [ "${b2:-0}" -ge 1 ]; then break; fi
  sleep 60
done
echo "$(date) batch 1 done" >> $LOG

# --- batch 2: 计组A卷 + 皖西 ---
echo "launching batch 2 (计组A卷 + 皖西)..." >> $LOG
python3 scripts/gen_kaodian_paper.py --handoff workspace/edd151236231/compose/paper_request.yaml --tag full2_coA >/tmp/full2_coA.log 2>&1 &
P1=$!
python3 scripts/gen_kaodian_paper.py --handoff workspace/v8_wanxi_handoff.yaml --tag full2_nmWX >/tmp/full2_nmWX.log 2>&1 &
P2=$!
wait $P1; wait $P2
echo "$(date) batch 2 done" >> $LOG

# --- batch 3: 正常A卷 + 合肥师范 ---
echo "launching batch 3 (正常A卷 + 合肥师范)..." >> $LOG
python3 scripts/gen_kaodian_paper.py --handoff workspace/v8_acollege_handoff.yaml --tag full2_nmA >/tmp/full2_nmA.log 2>&1 &
P1=$!
python3 scripts/gen_kaodian_paper.py --handoff workspace/v6_full_paper_handoff.yaml --tag full2_nmHF >/tmp/full2_nmHF.log 2>&1 &
P2=$!
wait $P1; wait $P2
echo "$(date) batch 3 done" >> $LOG

echo "$(date) === ALL 6 PAPERS DONE ===" >> $LOG
# 汇总各套 finals 数
for tag in "full_计组1卷" "full_试卷A卷" "full2_coA" "full2_nmWX" "full2_nmA" "full2_nmHF"; do
  n=$(find "docs/test_output/kaodian_${tag}" -name final.md 2>/dev/null | wc -l)
  echo "  $tag: $n finals" >> $LOG
done
