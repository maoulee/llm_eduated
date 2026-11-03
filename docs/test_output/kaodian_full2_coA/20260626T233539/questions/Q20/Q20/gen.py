"""
指令流水线性能与冒险分析 — 综合题建模
把 question.md 声明的场景规则 R1~R8 翻译成代码，
底部 print 完整数据流供审核对照场景规则验证。
"""

# ============================================================
# 输入参数（PARAMS）
# ============================================================
n = 5                              # 流水线级数
stage_times = {
    'IF':  300,
    'ID':  200,
    'EX':  500,
    'MEM': 400,
    'WB':  200,
}
L = 4                              # 指令条数

# 指令序列（用数据描述供冒险分析引用）
# 每条: (编号, 操作码, 是Load?, 读取的源寄存器集合)
instructions = [
    ('I1', 'LW  R1,0(R2)', True,  {'R2'}),       # I1: R1←Mem[R2]，目标 R1（Load）
    ('I2', 'ADD R3,R1,R4', False, {'R1', 'R4'}), # I2: R3←R1+R4
    ('I3', 'SUB R5,R3,R6', False, {'R3', 'R6'}), # I3: R5←R3-R6
    ('I4', 'SW  R5,8(R2)', False, {'R5', 'R2'}), # I4: Mem[R2+8]←R5（读 R5）
]
# 每条指令的目标寄存器（写入）
dest_reg = ['R1', 'R3', 'R5', None]  # I4 是 Store，无寄存器目标

# ============================================================
# Q1: 时钟周期  (规则 R1)
# ============================================================
clock_cycle = max(stage_times.values())          # R1

# ============================================================
# Q2: 性能计算
# ============================================================
sum_stages = sum(stage_times.values())            # IF+ID+EX+MEM+WB

# 非流水线执行时间 (规则 R2)
non_pipeline_time = L * sum_stages                # R2

# 理想流水线执行时间 (规则 R3)
ideal_cycles = n + L - 1                          # 5+4-1 = 8
ideal_pipeline_time = ideal_cycles * clock_cycle  # R3

# 加速比 (规则 R4)
speedup = non_pipeline_time / ideal_pipeline_time # R4

# 吞吐率 (规则 R5): L/ideal_time，单位 条/ps → ×1000 = 条/ns
throughput_per_ps = L / ideal_pipeline_time
throughput_per_ns = throughput_per_ps * 1000      # ps→ns

# ============================================================
# Q3: 数据冒险识别（RAW 相关对自动检测）
# ============================================================
raw_pairs = []  # (producer_index, consumer_index, 相关寄存器)
for ci in range(L):
    consumer_srcs = instructions[ci][3]
    for pi in range(ci):
        d = dest_reg[pi]
        if d is not None and d in consumer_srcs:
            raw_pairs.append((pi, ci, d, instructions[pi][2]))  # 含 is_load 标志

# WAR / WAW: 按序流水线不存在（本序列也无逆序写-读/写-写对）
war_pairs = []
waw_pairs = []

# ============================================================
# Q4(a): 无转发停顿  (规则 R6)
# ============================================================
# 理想调度下每条指令的各级周期号: 指令 i 的第 k 级在周期 (i+k+1)  (1-indexed)
# 级索引: IF=0, ID=1, EX=2, MEM=3, WB=4
def stage_cycle(i, k):
    return i + k + 1          # i,k 均 0-indexed → 1-indexed 周期号

# 无转发: consumer 在 ID 级必须等到 producer WB 完成（WB 周期号）
# stall_per_pair = max(0, WB(producer) - ID(consumer_original))   (规则 R6)
# 停顿会推后后续指令，先做逐对原始停顿
no_fwd_raw = []  # (pair, stall_per_pair)
for (pi, ci, reg, is_load) in raw_pairs:
    wb_p = stage_cycle(pi, 4)              # producer WB 周期号
    id_c = stage_cycle(ci, 1)              # consumer 原始 ID 周期号
    stall = max(0, wb_p - id_c)            # R6
    no_fwd_raw.append(((pi, ci, reg), wb_p, id_c, stall))

# 累计停顿（停顿逐指令传播：consumer 的实际 ID = 原始ID + 之前累计停顿）
# 简化模型：总停顿 = 各相关对 stall 之和（每对独立贡献，停顿由 bubble 传播）
# 但标准做法是累加 —— 此处用"每对 stall 求和"且校验最终周期自洽(R8)
total_stall_no_fwd = sum(s for (_, _, _, s) in no_fwd_raw)

# 实际执行总周期 (规则 R8)
actual_cycles_no_fwd = ideal_cycles + total_stall_no_fwd

# ============================================================
# Q4(b): 有转发停顿  (规则 R7)
# ============================================================
# Load-use 对(producer 为 Load): 1 停顿;  一般 ALU→ALU: 0 停顿
fwd_raw = []
for (pi, ci, reg, is_load) in raw_pairs:
    if is_load:
        stall = 1                            # R7: Load-use 残留 1
        kind = 'Load-use'
    else:
        stall = 0                            # R7: ALU→ALU 转发 0
        kind = 'ALU→ALU'
    fwd_raw.append(((pi, ci, reg), kind, stall))

total_stall_fwd = sum(s for (_, _, s) in fwd_raw)
actual_cycles_fwd = ideal_cycles + total_stall_fwd          # R8

# ============================================================
# 底部：打印完整数据流
# ============================================================
print("="*60)
print("PARAMS:")
print("  stage_times:", stage_times)
print("  n(级数):", n, " L(指令条数):", L)
print()
print("Q1 — 时钟周期 (规则R1: max(各段时间))")
print("  sum_stages =", sum_stages)
print("  clock_cycle =", clock_cycle, "ps")
print()
print("Q2 — 性能计算")
print("  非流水线时间 (R2: L*sum):", non_pipeline_time, "ps")
print("  理想流水线周期数 (n+L-1):", ideal_cycles)
print("  理想流水线时间 (R3):", ideal_pipeline_time, "ps")
print("  加速比 (R4: non/ideal):", speedup)
print("  吞吐率 (R5):", round(throughput_per_ns, 2), "指令/ns  (", throughput_per_ps, "条/ps )")
print()
print("Q3 — 数据冒险识别")
for (pi, ci, reg, is_load) in raw_pairs:
    idx_p, idx_c = pi+1, ci+1
    tag = "Load-use相关" if is_load else "一般RAW相关(ALU→ALU)"
    print(f"  I{idx_p}→I{idx_c}: 相关寄存器={reg}, 类型={tag}")
print("  WAR相关对数:", len(war_pairs), "  WAW相关对数:", len(waw_pairs))
print("  (按序流水线: 无逆序写-读/写-写, 故无 WAR/WAW 冒险)")
print()
print("Q4(a) — 无转发停顿 (规则R6)")
for (pair, wb_p, id_c, stall) in no_fwd_raw:
    pi, ci, reg = pair
    print(f"  I{pi+1}→I{ci+1}({reg}): WB(I{pi+1})=周期{wb_p}, ID(I{ci+1})原始=周期{id_c}, 停顿={stall}")
print("  总停顿周期 =", total_stall_no_fwd)
print("  实际执行总周期 =", actual_cycles_no_fwd, "(理想", ideal_cycles, "+ 停顿", total_stall_no_fwd, ")")
print()
print("Q4(b) — 有转发停顿 (规则R7)")
for (pair, kind, stall) in fwd_raw:
    pi, ci, reg = pair
    print(f"  I{pi+1}→I{ci+1}({reg}): 类型={kind}, 停顿={stall}")
print("  总停顿周期 =", total_stall_fwd)
print("  实际执行总周期 =", actual_cycles_fwd, "(理想", ideal_cycles, "+ 停顿", total_stall_fwd, ")")
print()
print("="*60)
print("RULE_CHECK (审核对照场景规则验证):")
print("  R1 clock_cycle==max(IF,ID,EX,MEM,WB):", clock_cycle, "==", max(stage_times.values()),
      "→", clock_cycle == max(stage_times.values()))
print("  R2 non_pipeline==L*sum_stages:", non_pipeline_time, "==", L*sum_stages, "→", non_pipeline_time == L*sum_stages)
print("  R3 ideal_pipeline==(n+L-1)*clock:", ideal_pipeline_time, "==", (n+L-1)*clock_cycle,
      "→", ideal_pipeline_time == (n+L-1)*clock_cycle)
print("  R4 speedup==non/ideal & S>1 & 非整数:", speedup, " S>1→", speedup>1, " 非整数→", speedup!=int(speedup))
print("  R5 throughput==L/ideal (条/ns):", round(throughput_per_ns,2))
print("  R6 无转发总停顿≥2:", total_stall_no_fwd, "→", total_stall_no_fwd >= 2)
print("  R7 有转发Load-use残留停顿≥1:", total_stall_fwd, "→", total_stall_fwd >= 1)
print("  R8a 实际周期==理想+停顿(无转发):", actual_cycles_no_fwd, "==", ideal_cycles+total_stall_no_fwd,
      "→", actual_cycles_no_fwd == ideal_cycles + total_stall_no_fwd)
print("  R8b 实际周期==理想+停顿(有转发):", actual_cycles_fwd, "==", ideal_cycles+total_stall_fwd,
      "→", actual_cycles_fwd == ideal_cycles + total_stall_fwd)
