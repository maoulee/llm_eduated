"""
辅助验证：无转发停顿的逐周期流水线时序模拟。
方法：构造理想时序表，然后按 producer-WB→consumer-ID 依赖传播停顿。
"""
n = 5
L = 4

# 理想调度: 指令 i 的第 k 级在周期 i+k+1 (1-indexed)
# IF=1, ID=2, EX=3, MEM=4, WB=5 (k=0..4)

# RAW 相关对
raw = [
    (0, 1, 'R1', True),   # I1→I2, Load-use
    (1, 2, 'R3', False),  # I2→I3
    (2, 3, 'R5', False),  # I3→I4
]

# --- 方法: 标准停顿传播 ---
# 用一个数组 offset[i] 表示指令 i 的 ID 级被推迟了多少周期（从理想位置算起）
# 理想 ID 周期 = i + 2 (1-indexed), 理想 WB 周期 = i + 5

id_offset = [0]*L  # 每条指令的实际偏移量（相对理想）
wb_offset = [0]*L

# 逐条处理（按 consumer 顺序）
for i in range(L):
    # 指令 i 的理想 ID 周期 = i+2 (1-indexed)
    # 但前面的停顿已经推移了指令 i 的进入时间
    # 指令 i 的实际 IF 周期 = 理想(i+1) + max(之前累积 bubble)
    pass

# 更清晰的方法: 模拟每周期流水线状态
# pipeline_state[cycle] = list of (instr_idx, stage) active in that cycle
# 每周期最多 5 条不同级不同指令同时活跃

# 指令级推进表: stage_schedule[i] = 实际的各级周期号
stage_sched = [[0]*n for _ in range(L)]  # [指令][级] = 周期号(1-indexed)

# 初始理想调度
for i in range(L):
    for k in range(n):
        stage_sched[i][k] = i + k + 1

# 模拟停顿传播: 逐对 RAW 处理
# 对每对 (p→c): consumer c 的 ID 必须在 producer p 的 WB 之后(或同期，因 WB前半段写 ID后半段读)
# 需要 ID(c) >= WB(p)
# 如果 ID(c) < WB(p)，则 c 要推迟 (WB(p) - ID(c)) 个周期
# 推迟会传播到 c 之后的所有指令

for (p, c, reg, is_load) in raw:
    wb_p = stage_sched[p][4]  # producer 的 WB 周期（可能已被前序停顿影响）
    id_c = stage_sched[c][1]  # consumer 的 ID 周期
    if id_c < wb_p:
        delay = wb_p - id_c
        # consumer c 及之后所有指令的所有级推迟 delay
        for j in range(c, L):
            for k in range(n):
                stage_sched[j][k] += delay
        print(f"  I{p+1}→I{c+1}({reg}): WB(p)=周期{wb_p}, ID(c)=周期{id_c}, 推迟={delay}")

print()
print("最终各级周期号:")
for i in range(L):
    print(f"  I{i+1}: IF={stage_sched[i][0]}, ID={stage_sched[i][1]}, EX={stage_sched[i][2]}, MEM={stage_sched[i][3]}, WB={stage_sched[i][4]}")

total_cycles = max(stage_sched[i][4] for i in range(L))
ideal_cycles = n + L - 1  # 8
total_stall = total_cycles - ideal_cycles
print(f"\n总周期数(最后一条WB): {total_cycles}")
print(f"理想周期数: {ideal_cycles}")
print(f"总停顿: {total_stall}")
print(f"\n与 R6 公式(逐对求和=6)对比: 传播模拟={total_stall}")
