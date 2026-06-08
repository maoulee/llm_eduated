# ===== 题目参数 =====
clock_freq_MHz = 500  # 主频 500MHz
total_instructions = 2e6  # 总指令数 2×10^6
ratio_fast = 0.75  # 75%的指令
cpi_fast = 2  # 平均2个时钟周期
ratio_slow = 0.25  # 25%的指令
cpi_slow = 6  # 平均6个时钟周期

# ===== 校验1：参数封闭性 =====
# 所有子问题所需参数是否都在题干中给出
# 需要：主频、总指令数、各类指令比例、各类指令CPI
# 全部已给出 ✓

# ===== 校验2：比例之和为1 =====
assert abs(ratio_fast + ratio_slow - 1.0) < 1e-9, f"比例之和不等于1: {ratio_fast + ratio_slow}"

# ===== 校验3：指令数为整数 =====
fast_instructions = total_instructions * ratio_fast
slow_instructions = total_instructions * ratio_slow
assert fast_instructions == int(fast_instructions), f"快速指令数不是整数: {fast_instructions}"
assert slow_instructions == int(slow_instructions), f"慢速指令数不是整数: {slow_instructions}"

# ===== 校验4：总时钟周期为整数 =====
total_cycles = fast_instructions * cpi_fast + slow_instructions * cpi_slow
assert total_cycles == int(total_cycles), f"总时钟周期不是整数: {total_cycles}"

# ===== 校验5：单位换算链 =====
# 500MHz = 500 × 10^6 Hz
# 时钟周期 = 1 / 500MHz = 2 × 10^-9 s = 2ns
clock_period_ns = 1e9 / (clock_freq_MHz * 1e6)  # ns
assert abs(clock_period_ns - 2.0) < 1e-9, f"时钟周期不是2ns: {clock_period_ns}"

# ===== 校验6：执行时间单位换算 =====
# 执行时间 = 总时钟周期 × 时钟周期
# 结果应为 ms 级别
execution_time_s = total_cycles / (clock_freq_MHz * 1e6)
execution_time_ms = execution_time_s * 1e3
print(f"快速指令数: {int(fast_instructions)}")
print(f"慢速指令数: {int(slow_instructions)}")
print(f"总时钟周期: {int(total_cycles)}")
print(f"时钟周期: {clock_period_ns}ns")
print(f"执行时间: {execution_time_ms}ms")

print("参数校验通过")
