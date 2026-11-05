# ===== 题目参数定义 =====
freq_ghz = 2              # 主频 2 GHz
total_instructions = 8e6  # 总指令数 8×10^6
pct_cpi2 = 0.75           # 75% 的指令 CPI=2
pct_cpi6 = 0.25           # 25% 的指令 CPI=6
cpi_low = 2
cpi_high = 6

# ===== 子问题: 求程序P的执行时间 =====
# 步骤1: 计算加权平均 CPI
cpi_avg = pct_cpi2 * cpi_low + pct_cpi6 * cpi_high
print(f"加权平均 CPI = {pct_cpi2}×{cpi_low} + {pct_cpi6}×{cpi_high} = {cpi_avg}")

# 步骤2: 计算总周期数
total_cycles = total_instructions * cpi_avg
print(f"总周期数 = {total_instructions:.0e} × {cpi_avg} = {total_cycles:.1e}")

# 步骤3: 计算执行时间
freq_hz = freq_ghz * 1e9  # 2 GHz → 2×10^9 Hz
time_s = total_cycles / freq_hz
time_ms = time_s * 1e3    # s → ms
print(f"主频 = {freq_ghz} GHz = {freq_hz:.0e} Hz")
print(f"执行时间 = {total_cycles:.1e} / {freq_hz:.0e} = {time_s} s = {time_ms} ms")

print(f"\nANSWER: B: {time_ms:.0f} ms")
