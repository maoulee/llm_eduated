# ===== 题目参数定义 =====
freq = 2e9  # 主频 2 GHz = 2e9 Hz
IC = 40000  # 总指令数

# 各类指令占比和CPI
pct_2 = 0.60; cpi_2 = 2
pct_4 = 0.20; cpi_4 = 4
pct_10 = 0.20; cpi_10 = 10

# ===== 子问题(1): 计算加权平均CPI =====
cpi_avg = pct_2 * cpi_2 + pct_4 * cpi_4 + pct_10 * cpi_10
print(f"加权平均CPI = {pct_2}*{cpi_2} + {pct_4}*{cpi_4} + {pct_10}*{cpi_10} = {cpi_avg}")

# ===== 子问题(2): 计算总周期数 =====
total_cycles = IC * cpi_avg
print(f"总周期数 = {IC} × {cpi_avg} = {total_cycles}")

# ===== 子问题(3): 计算执行时间 =====
T_seconds = total_cycles / freq
T_us = T_seconds * 1e6
print(f"执行时间 = {total_cycles} / {freq:.0e} = {T_seconds} s = {T_us} μs")

print(f"\nANSWER: C: {T_us} μs")
