# ===== 题目参数定义 =====
f = 2e9          # 主频 2 GHz
IC = 4e6         # 指令数 4×10^6
ratio_1 = 0.80   # 80% 指令
CPI_1 = 1        # CPI = 1
ratio_2 = 0.20   # 20% 指令
CPI_2 = 6        # CPI = 6

# ===== 子问题: 加权平均 CPI =====
CPI_avg = ratio_1 * CPI_1 + ratio_2 * CPI_2
print(f"加权平均 CPI = {ratio_1}×{CPI_1} + {ratio_2}×{CPI_2} = {CPI_avg}")

# ===== 总周期数 =====
total_cycles = IC * CPI_avg
print(f"总周期数 = {IC:.0e} × {CPI_avg} = {total_cycles:.0e}")

# ===== 执行时间 =====
T_seconds = total_cycles / f
T_ms = T_seconds * 1e3
T_us = T_seconds * 1e6
print(f"执行时间 = {total_cycles:.0e} / {f:.0e} = {T_seconds} s")
print(f"  = {T_ms} ms")
print(f"  = {T_us} μs")

# ===== 选项验证 =====
print(f"\n选项A (2 ms): {'正确' if abs(T_ms-2)<0.01 else '错误'}")
print(f"选项B (4 ms): {'正确' if abs(T_ms-4)<0.01 else '错误'}")
print(f"选项C (4 μs): {'正确' if abs(T_us-4)<0.01 else '错误'}")
print(f"选项D (10 ms): {'正确' if abs(T_ms-10)<0.01 else '错误'}")

print(f"\nANSWER: B: {T_ms:.0f} ms")
