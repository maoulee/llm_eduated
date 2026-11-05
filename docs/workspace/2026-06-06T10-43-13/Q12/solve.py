
# ===== 题目参数定义 =====
f = 2e9  # 主频 2 GHz = 2×10⁹ Hz
IC = 4e6  # 总指令数 4×10⁶

# 各类指令占比与CPI
pct_cpi1 = 0.40  # 40% 的指令 CPI=1
pct_cpi2 = 0.40  # 40% 的指令 CPI=2
pct_cpi4 = 0.20  # 20% 的指令 CPI=4

# ===== 子问题(1): 加权平均 CPI =====
avg_CPI = pct_cpi1 * 1 + pct_cpi2 * 2 + pct_cpi4 * 4
print(f"加权平均 CPI = {pct_cpi1}×1 + {pct_cpi2}×2 + {pct_cpi4}×4 = {avg_CPI}")

# ===== 子问题(2): 执行时间 =====
total_cycles = IC * avg_CPI
T_seconds = total_cycles / f
T_ms = T_seconds * 1000
print(f"总周期数 = {IC:.0e} × {avg_CPI} = {total_cycles:.0e}")
print(f"执行时间 = {total_cycles:.0e} / {f:.0e} = {T_seconds} s = {T_ms} ms")

# ===== 子问题(3): MIPS =====
MIPS = f / avg_CPI / 1e6
print(f"MIPS = {f:.0e} / {avg_CPI} / 1e6 = {MIPS}")

# ===== 最终输出 =====
print(f"\nANSWER: 执行时间 = {T_ms} ms, MIPS = {MIPS} → 选项 B")
