# ===== 题目参数定义 =====
clock_rate_GHz = 2  # 主频 2GHz
total_instructions = 8e6  # 总指令数 8×10^6
ratio_1cycle = 0.6  # 60%的指令需1个时钟周期
ratio_2cycle = 0.4  # 40%的指令需2个时钟周期

# ===== 子问题：计算CPU执行时间 =====

# 1. 计算各类指令数量
instructions_1cycle = total_instructions * ratio_1cycle  # 1周期指令数
instructions_2cycle = total_instructions * ratio_2cycle  # 2周期指令数

print(f"1周期指令数: {instructions_1cycle:.0e}")
print(f"2周期指令数: {instructions_2cycle:.0e}")

# 2. 计算总时钟周期数
total_cycles = instructions_1cycle * 1 + instructions_2cycle * 2
print(f"总时钟周期数: {total_cycles:.0e}")

# 3. 计算时钟周期（秒）
clock_period_s = 1.0 / (clock_rate_GHz * 1e9)
print(f"时钟周期: {clock_period_s} s = {clock_period_s * 1e9} ns")

# 4. 计算CPU执行时间（秒）
cpu_time_s = total_cycles * clock_period_s
print(f"CPU执行时间: {cpu_time_s} s")

# 5. 转换为ms
cpu_time_ms = cpu_time_s * 1e3
print(f"CPU执行时间: {cpu_time_ms} ms")

# ===== 最终输出 =====
print(f"ANSWER: {cpu_time_ms}ms")
