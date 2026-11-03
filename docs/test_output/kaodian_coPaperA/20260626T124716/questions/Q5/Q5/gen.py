"""
CPU性能指标计算：CPI / MIPS / 执行时间比较
题干→代码翻译：加权CPI、MIPS、执行时间，三问串行。
"""

# ============ PARAMS ============
# 指令使用频率 p_i
freq = [0.40, 0.30, 0.20, 0.10]

# 机器A各指令类CPI
CPI_A_list = [1, 2, 3, 4]

# 机器B各指令类CPI
CPI_B_list = [2, 2, 4, 3]

# 主频 (Hz)
f_A = 2e9   # 2 GHz
f_B = 3e9   # 3 GHz

# 指令总数
N = 5e8

print("=== PARAMS ===")
print(f"freq = {freq}")
print(f"CPI_A_list = {CPI_A_list}")
print(f"CPI_B_list = {CPI_B_list}")
print(f"f_A = {f_A:.0e} Hz")
print(f"f_B = {f_B:.0e} Hz")
print(f"N = {N:.0e}")


# ============ 函数定义（题干公式翻译） ============
def avg_cpi(freq_list, cpi_list):
    """平均 CPI = Σ p_i × CPI_i"""
    return sum(p * c for p, c in zip(freq_list, cpi_list))


def mips(f_hz, cpi):
    """MIPS = f(Hz) / (CPI × 10^6)"""
    return f_hz / (cpi * 1e6)


def exec_time(N_instructions, cpi, f_hz):
    """执行时间 T = N × CPI / f (秒)"""
    return N_instructions * cpi / f_hz


# ============ 第1问：平均CPI ============
cpi_A = avg_cpi(freq, CPI_A_list)
cpi_B = avg_cpi(freq, CPI_B_list)

print("\n=== 第1问：平均CPI ===")
print(f"机器A平均CPI = {freq[0]}×{CPI_A_list[0]} + {freq[1]}×{CPI_A_list[1]} + {freq[2]}×{CPI_A_list[2]} + {freq[3]}×{CPI_A_list[3]}")
print(f"  = {cpi_A:.2f}")
print(f"机器B平均CPI = {freq[0]}×{CPI_B_list[0]} + {freq[1]}×{CPI_B_list[1]} + {freq[2]}×{CPI_B_list[2]} + {freq[3]}×{CPI_B_list[3]}")
print(f"  = {cpi_B:.2f}")


# ============ 第2问：MIPS ============
mips_A = mips(f_A, cpi_A)
mips_B = mips(f_B, cpi_B)

print("\n=== 第2问：MIPS ===")
print(f"机器A MIPS = {f_A:.0e} / ({cpi_A:.2f} × 10^6) = {mips_A:.2f}")
print(f"机器B MIPS = {f_B:.0e} / ({cpi_B:.2f} × 10^6) = {mips_B:.2f}")


# ============ 第3问：执行时间 ============
T_A = exec_time(N, cpi_A, f_A)
T_B = exec_time(N, cpi_B, f_B)

print("\n=== 第3问：执行时间 ===")
print(f"机器A执行时间 T_A = {N:.0e} × {cpi_A:.2f} / {f_A:.0e} = {T_A:.2f} s")
print(f"机器B执行时间 T_B = {N:.0e} × {cpi_B:.2f} / {f_B:.0e} = {T_B:.2f} s")

if T_A < T_B:
    faster = "A"
    ratio = T_B / T_A
    diff = T_B - T_A
    print(f"\n机器A更快。T_B - T_A = {diff:.2f} s")
    print(f"机器A是机器B的 {ratio:.2f} 倍速度（T_B/T_A = {ratio:.2f}）")
elif T_B < T_A:
    faster = "B"
    ratio = T_A / T_B
    diff = T_A - T_B
    print(f"\n机器B更快。T_A - T_B = {diff:.2f} s")
    print(f"机器B是机器A的 {ratio:.2f} 倍速度（T_A/T_B = {ratio:.2f}）")
else:
    faster = "none"

print(f"\n=== ANSWER ===")
print(f"CPI_A = {cpi_A:.2f}")
print(f"CPI_B = {cpi_B:.2f}")
print(f"MIPS_A = {mips_A:.2f}")
print(f"MIPS_B = {mips_B:.2f}")
print(f"T_A = {T_A:.2f} s")
print(f"T_B = {T_B:.2f} s")
print(f"faster machine = {faster}")


# ============ ASSERT 通过条件（题干声明的5条特征） ============

# 条件4：频率归一化 Σp_i = 1
assert abs(sum(freq) - 1.0) < 1e-9, f"频率和={sum(freq)}，不满足归一化"

# 条件1：加权平均CPI互异且为正
assert cpi_A > 0 and cpi_B > 0, "CPI必须为正数"
assert cpi_A != cpi_B, f"CPI_A({cpi_A}) 不应等于 CPI_B({cpi_B})"

# 条件2：MIPS互异且为正、量级在10^2~10^4范围
assert mips_A > 0 and mips_B > 0, "MIPS必须为正数"
assert mips_A != mips_B, f"MIPS_A({mips_A}) 不应等于 MIPS_B({mips_B})"
assert 1e2 <= mips_A <= 1e4, f"MIPS_A={mips_A} 不在10^2~10^4范围"
assert 1e2 <= mips_B <= 1e4, f"MIPS_B={mips_B} 不在10^2~10^4范围"

# 条件3：执行时间严格不等，有唯一"更快"结论
assert T_A != T_B, f"T_A({T_A}) 不应等于 T_B({T_B})"
assert faster in ("A", "B"), "第3问必须有唯一更快结论"

# 条件5：至少2类指令CPI不同
diff_count = sum(1 for a, b in zip(CPI_A_list, CPI_B_list) if a != b)
assert diff_count >= 2, f"两机器CPI不同的指令类只有{diff_count}个，需≥2"

print("\n=== 所有assert通过 ===")
