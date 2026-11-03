# -*- coding: utf-8 -*-
"""
指令流水线性能与冒险分析 —— gen.py
逐句翻译题干规则 + 通过条件→assert
"""

# ============================================================
# PARAMS
# ============================================================
stage_delays = {'IF': 200, 'ID': 150, 'EX': 400, 'WB': 300}
num_stages = 4   # IF, ID, EX, WB

# 指令序列：(指令名, 目标寄存器, 源寄存器列表)
# 立即数源(如 SLL 的 2)不在列表中——不是寄存器
instructions = [
    ('I1 ADD R1,R2,R3', 'R1', ['R2', 'R3']),
    ('I2 SUB R4,R1,R5', 'R4', ['R1', 'R5']),
    ('I3 OR  R6,R1,R7', 'R6', ['R1', 'R7']),
    ('I4 AND R8,R4,R6', 'R8', ['R4', 'R6']),
    ('I5 SLL R9,R8,2',  'R9', ['R8']),          # 2 是立即数
    ('I6 ADD R10,R9,R11','R10',['R9', 'R11']),
]
num_instr = len(instructions)

print("=" * 60)
print("PARAMS")
print("=" * 60)
print(f"stage_delays = {stage_delays}")
print(f"num_stages = {num_stages}")
print(f"num_instr = {num_instr}")
for ins in instructions:
    print(f"  {ins[0]}  dst={ins[1]}  src={ins[2]}")
print()

# ============================================================
# Q1: 操作周期
# ============================================================
period = max(stage_delays.values())           # 翻译："操作周期=各段延迟最大值"
delay_values = list(stage_delays.values())
max_count = delay_values.count(period)        # 唯一最大值检查

print("=" * 60)
print("Q1: 操作周期")
print("=" * 60)
print(f"max(stage_delays) = max({delay_values}) = {period} ns")
print(f"最大值出现次数 = {max_count}（应为1=唯一确定）")
print()

# ============================================================
# Q2: 加速比
# ============================================================
non_pipe_time = sum(stage_delays.values()) * num_instr          # 翻译：非流水线时间
pipe_time_no_hazard = period * (num_stages + num_instr - 1)     # 翻译：流水线时间(不考虑冒险)
speedup = non_pipe_time / pipe_time_no_hazard                   # 翻译：加速比

print("=" * 60)
print("Q2: 加速比")
print("=" * 60)
print(f"非流水线时间 = ({'+'.join(str(v) for v in stage_delays.values())}) × {num_instr} = {sum(stage_delays.values())} × {num_instr} = {non_pipe_time} ns")
print(f"流水线时间(不考虑冒险) = {period} × ({num_stages}+{num_instr}-1) = {period} × {num_stages+num_instr-1} = {pipe_time_no_hazard} ns")
print(f"加速比 = {non_pipe_time} ÷ {pipe_time_no_hazard} = {speedup:.4f}")
print()

# ============================================================
# Q3: 数据冒险识别
# ============================================================
raw_hazards = []
war_hazards = []
waw_hazards = []

for i in range(num_instr):
    for j in range(i + 1, num_instr):
        dst_i = instructions[i][1]
        src_j = instructions[j][2]
        dst_j = instructions[j][1]
        src_i = instructions[i][2]

        # RAW: 后指令的源 == 前指令的目标
        for s in src_j:
            if s == dst_i:
                raw_hazards.append((instructions[i][0], instructions[j][0], s, j - i))

        # WAR: 后指令的目标 == 前指令的源
        for s in src_i:
            if s == dst_j:
                war_hazards.append((instructions[i][0], instructions[j][0], s, j - i))

        # WAW: 后指令的目标 == 前指令的目标
        if dst_j == dst_i:
            waw_hazards.append((instructions[i][0], instructions[j][0], dst_i, j - i))

print("=" * 60)
print("Q3: 数据冒险识别")
print("=" * 60)
print(f"RAW 冒险 ({len(raw_hazards)} 组):")
for h in raw_hazards:
    print(f"  {h[0]} → {h[1]}  寄存器={h[2]}  间距={h[3]}")
print(f"WAR 冒险 ({len(war_hazards)} 组):")
for h in war_hazards:
    print(f"  {h}")
print(f"WAW 冒险 ({len(waw_hazards)} 组):")
for h in waw_hazards:
    print(f"  {h}")
print()

# ============================================================
# Q4: 无转发停顿 + 总周期
# ============================================================
# 翻译题干："指令遇到RAW冒险时必须在ID段停顿，直到产生结果的指令完成WB段"
#
# 4级流水线(IF/ID/EX/WB)，无内部前递，无写前半/读后半优化:
#   正常情况: 后指令在周期 c 的 ID 段读源寄存器
#   前指令在周期 c 的 ID-3 的 WB 段写目标寄存器
#   若前指令WB在后指令ID之前或同周期完成→无冒险
#   否则停顿 = 前指令.WB周期 - 后指令.ID周期

print("=" * 60)
print("Q4: 无转发停顿与总周期")
print("=" * 60)

# 起始周期: 指令 k 的 IF 在周期 k+1（从1开始计数）
def no_forward_stalls():
    schedule = [None] * num_instr  # 每条指令的实际 IF 周期
    stall_per_instr = [0] * num_instr

    for k in range(num_instr):
        if k == 0:
            schedule[k] = 1   # I1 在周期1进入IF
        else:
            # 默认在前一条指令IF的下一个周期进入IF
            earliest_if = schedule[k-1] + 1
            schedule[k] = earliest_if

        # 检查所有RAW: 前指令写入 vs 本指令读取
        max_gap = 0
        for i in range(k):
            dst_i = instructions[i][1]
            src_k = instructions[k][2]
            if dst_i in src_k:
                # 前指令i的WB周期 = schedule[i] + 3 (IF=0, ID=1, EX=2, WB=3 相对偏移)
                wb_producer = schedule[i] + 3
                # 本指令k的ID周期 = schedule[k] + 1
                id_consumer = schedule[k] + 1
                if wb_producer > id_consumer:
                    gap = wb_producer - id_consumer
                    if gap > max_gap:
                        max_gap = gap

        if max_gap > 0:
            stall_per_instr[k] = max_gap
            # 停顿推迟当前及后续所有已调度的指令（None的还未赋值，会被覆盖）
            for kk in range(k, num_instr):
                if schedule[kk] is not None:
                    schedule[kk] += max_gap

    return schedule, stall_per_instr

nf_schedule, nf_stalls = no_forward_stalls()
total_stalls_nf = sum(nf_stalls)
ideal_cycles = num_stages + num_instr - 1
# 最后一条指令的WB周期 = 总周期数
last_wb_nf = nf_schedule[-1] + 3
total_cycles_nf = last_wb_nf

print("指令排程与停顿:")
for k in range(num_instr):
    print(f"  {instructions[k][0]}: IF周期={nf_schedule[k]}, 停顿={nf_stalls[k]}")
print(f"理想周期数(无冒险) = {num_stages} + {num_instr} - 1 = {ideal_cycles}")
print(f"总停顿周期数 = {total_stalls_nf}")
print(f"总时钟周期数(无转发) = {ideal_cycles} + {total_stalls_nf} = {total_cycles_nf}")
print()

# ============================================================
# Q5: 有EX→EX转发的停顿与总周期
# ============================================================
# 翻译题干："EX→EX转发——前一条指令EX段产生的ALU结果旁路到后一条指令EX段"
#
# 有EX→EX转发时，前指令EX结果在周期 EX_producer 可供后指令EX使用
#   前指令EX周期 = IF + 2, 后指令EX周期 = IF + 2
#   若前指令EX周期 <= 后指令EX周期 → 可转发，无需停顿
#   否则需停顿 = 前指令EX周期 - 后指令EX周期

print("=" * 60)
print("Q5: EX→EX转发停顿与总周期")
print("=" * 60)

def forwarding_stalls():
    schedule = [None] * num_instr
    stall_per_instr = [0] * num_instr

    for k in range(num_instr):
        if k == 0:
            schedule[k] = 1
        else:
            earliest_if = schedule[k-1] + 1
            schedule[k] = earliest_if

        # EX→EX转发检查
        max_gap = 0
        for i in range(k):
            dst_i = instructions[i][1]
            src_k = instructions[k][2]
            if dst_i in src_k:
                ex_producer = schedule[i] + 2   # 前指令EX周期
                ex_consumer = schedule[k] + 2   # 本指令EX周期
                if ex_producer > ex_consumer:
                    gap = ex_producer - ex_consumer
                    if gap > max_gap:
                        max_gap = gap

        if max_gap > 0:
            stall_per_instr[k] = max_gap
            for kk in range(k, num_instr):
                if schedule[kk] is not None:
                    schedule[kk] += max_gap

    return schedule, stall_per_instr

fwd_schedule, fwd_stalls = forwarding_stalls()
total_stalls_fwd = sum(fwd_stalls)
last_wb_fwd = fwd_schedule[-1] + 3
total_cycles_fwd = last_wb_fwd

print("指令排程与停顿(EX→EX转发):")
for k in range(num_instr):
    print(f"  {instructions[k][0]}: IF周期={fwd_schedule[k]}, 停顿={fwd_stalls[k]}")
print(f"总停顿周期数(有转发) = {total_stalls_fwd}")
print(f"总时钟周期数(有转发) = {ideal_cycles} + {total_stalls_fwd} = {total_cycles_fwd}")
print(f"转发减少周期数 = {total_cycles_nf} - {total_cycles_fwd} = {total_cycles_nf - total_cycles_fwd}")
print()

# ============================================================
# ANSWER 汇总
# ============================================================
print("=" * 60)
print("ANSWER 汇总")
print("=" * 60)
print(f"Q1: 操作周期 = {period} ns")
print(f"Q2: 加速比 = {speedup:.4f}  ({non_pipe_time}/{pipe_time_no_hazard})")
print(f"Q3: RAW {len(raw_hazards)}组, WAR {len(war_hazards)}组, WAW {len(waw_hazards)}组")
print(f"Q4: 总停顿={total_stalls_nf}, 总周期(无转发)={total_cycles_nf}")
print(f"Q5: 总停顿={total_stalls_fwd}, 总周期(有转发)={total_cycles_fwd}, 减少={total_cycles_nf-total_cycles_fwd}")
print()

# ============================================================
# ASSERT 通过条件
# ============================================================
print("=" * 60)
print("通过条件验证 (ASSERT)")
print("=" * 60)

# 条件1: 操作周期=400，唯一最大值
assert period == 400, f"操作周期应为400, 实际{period}"
assert max_count == 1, f"最大值应唯一, 实际出现{max_count}次"
print("[PASS] 条件1: 操作周期=400 ns, 唯一最大值")

# 条件2: 加速比有意义, >1
assert non_pipe_time == 6300, f"非流水线时间应为6300, 实际{non_pipe_time}"
assert pipe_time_no_hazard == 3600, f"流水线时间应为3600, 实际{pipe_time_no_hazard}"
assert speedup > 1, f"加速比应>1, 实际{speedup}"
print(f"[PASS] 条件2: 加速比={speedup:.4f} > 1")

# 条件3: RAW冒险充分触发——至少2组, 至少1组间距=1, 至少1组间距=2
gaps = [h[3] for h in raw_hazards]
assert len(raw_hazards) >= 2, f"RAW冒险应≥2组, 实际{len(raw_hazards)}"
assert 1 in gaps, f"应有间距=1的RAW冒险, 实际间距={gaps}"
assert 2 in gaps, f"应有间距=2的RAW冒险, 实际间距={gaps}"
print(f"[PASS] 条件3: RAW {len(raw_hazards)}组, 含间距1和间距2")

# 条件4: 无WAR/WAW冒险
assert len(war_hazards) == 0, f"不应有WAR冒险, 实际{len(war_hazards)}组"
assert len(waw_hazards) == 0, f"不应有WAW冒险, 实际{len(waw_hazards)}组"
print("[PASS] 条件4: 无WAR/WAW冒险")

# 条件5: 无转发停顿>0, 总周期>9
assert total_cycles_nf > ideal_cycles, f"无转发总周期应>{ideal_cycles}, 实际{total_cycles_nf}"
assert total_stalls_nf > 0, f"无转发应有停顿, 实际{total_stalls_nf}"
print(f"[PASS] 条件5: 无转发总周期={total_cycles_nf} > {ideal_cycles}")

# 条件6: 转发改善有效, 有转发≤无转发 且 差值>0
assert total_cycles_fwd <= total_cycles_nf, f"有转发应≤无转发"
assert total_cycles_nf - total_cycles_fwd > 0, f"转发应减少周期, 差值={total_cycles_nf-total_cycles_fwd}"
print(f"[PASS] 条件6: 转发减少 {total_cycles_nf-total_cycles_fwd} 个周期")

# 条件7: 停顿计算自洽
assert total_cycles_nf == ideal_cycles + total_stalls_nf, \
    f"总周期应={ideal_cycles}+{total_stalls_nf}={ideal_cycles+total_stalls_nf}, 实际{total_cycles_nf}"
print(f"[PASS] 条件7: {total_cycles_nf} = {ideal_cycles} + {total_stalls_nf}")

print()
print("=" * 60)
print("全部通过条件验证通过！")
print("=" * 60)
