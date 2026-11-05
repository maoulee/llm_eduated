# ===== 题目参数 =====
clock_rate_GHz = 2  # 主频 2GHz
total_instructions = 8e6  # 总指令数 8×10^6
ratio_1cycle = 0.6  # 60%的指令需1个时钟周期
ratio_2cycle = 0.4  # 40%的指令需2个时钟周期

# ===== 校验1：参数封闭性 =====
# 所有子问题所需参数：主频、总指令数、各类指令比例、各类指令周期数
# 题干中均已给出，参数封闭

# ===== 校验2：比例之和为1 =====
assert abs(ratio_1cycle + ratio_2cycle - 1.0) < 1e-9, \
    f"指令比例之和不等于1: {ratio_1cycle} + {ratio_2cycle} = {ratio_1cycle + ratio_2cycle}"

# ===== 校验3：指令数为整数 =====
instructions_1cycle = total_instructions * ratio_1cycle
instructions_2cycle = total_instructions * ratio_2cycle
assert instructions_1cycle == int(instructions_1cycle), \
    f"1周期指令数非整数: {instructions_1cycle}"
assert instructions_2cycle == int(instructions_2cycle), \
    f"2周期指令数非整数: {instructions_2cycle}"

# ===== 校验4：单位换算链 =====
# 2GHz = 2×10^9 Hz，时钟周期 = 1/(2×10^9) 秒
clock_period_s = 1.0 / (clock_rate_GHz * 1e9)
print(f"时钟周期: {clock_period_s} s = {clock_period_s * 1e9} ns")

print("参数校验通过")
