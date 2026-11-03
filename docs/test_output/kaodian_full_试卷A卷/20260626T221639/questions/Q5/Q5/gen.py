"""
MIPS/CPI 计算题建模
忠实翻译题干运算规则 + 底部打印完整数据流
"""

# ============ 输入参数（来自题干） ============
total_instructions = 10**8  # 程序总指令数

ratios = [0.40, 0.30, 0.20, 0.10]  # 4类指令占比

# 机器A
freq_A_MHz = 500
cpi_A = [1, 3, 4, 6]  # I1~I4

# 机器B
freq_B_MHz = 750
cpi_B = [2, 3, 3, 5]  # I1~I4


def compute(freq_MHz, cpi_list):
    """翻译题干规则：加权CPI → MIPS → 执行时间"""
    freq_Hz = freq_MHz * 10**6

    # 规则2：加权 CPI == Σ(CPI_i × ratio_i)
    weighted_cpi = sum(c * r for c, r in zip(cpi_list, ratios))

    # 规则3：MIPS == f_clock_MHz / weighted_CPI
    mips = freq_MHz / weighted_cpi

    # 规则4：执行时间（两种公式）
    exec_time_formula1 = (total_instructions * weighted_cpi) / freq_Hz
    exec_time_formula2 = total_instructions / (mips * 10**6)

    return {
        'freq_MHz': freq_MHz,
        'freq_Hz': freq_Hz,
        'cpi_list': cpi_list,
        'weighted_cpi': weighted_cpi,
        'mips': mips,
        'exec_time_f1': exec_time_formula1,
        'exec_time_f2': exec_time_formula2,
    }


# ============ 注入参数跑 ============
result_A = compute(freq_A_MHz, cpi_A)
result_B = compute(freq_B_MHz, cpi_B)

# ============ 底部：打印完整数据流 ============
print("=" * 60)
print("PARAMS:")
print(f"  total_instructions = {total_instructions:.0e} = {total_instructions}")
print(f"  ratios = {ratios}, sum = {sum(ratios)}")
print(f"  Machine A: freq={freq_A_MHz} MHz, CPI={cpi_A}")
print(f"  Machine B: freq={freq_B_MHz} MHz, CPI={cpi_B}")
print()

print("-" * 60)
print("PROCESS (Machine A):")
print(f"  freq_A_Hz = {freq_A_MHz} * 10^6 = {result_A['freq_Hz']:.4e}")
print(f"  weighted_CPI_A = {cpi_A[0]}*{ratios[0]} + {cpi_A[1]}*{ratios[1]} + {cpi_A[2]}*{ratios[2]} + {cpi_A[3]}*{ratios[3]}")
print(f"                 = {cpi_A[0]*ratios[0]} + {cpi_A[1]*ratios[1]} + {cpi_A[2]*ratios[2]} + {cpi_A[3]*ratios[3]}")
print(f"                 = {result_A['weighted_cpi']:.4f}")
print(f"  MIPS_A = {freq_A_MHz} / {result_A['weighted_cpi']:.4f} = {result_A['mips']:.4f}")
print(f"  exec_time_A (formula1: N*CPI/f)  = {total_instructions}*{result_A['weighted_cpi']:.4f}/{result_A['freq_Hz']:.4e} = {result_A['exec_time_f1']:.6f} s")
print(f"  exec_time_A (formula2: N/(MIPS*1e6)) = {result_A['exec_time_f2']:.6f} s")
print()

print("-" * 60)
print("PROCESS (Machine B):")
print(f"  freq_B_Hz = {freq_B_MHz} * 10^6 = {result_B['freq_Hz']:.4e}")
print(f"  weighted_CPI_B = {cpi_B[0]}*{ratios[0]} + {cpi_B[1]}*{ratios[1]} + {cpi_B[2]}*{ratios[2]} + {cpi_B[3]}*{ratios[3]}")
print(f"                 = {cpi_B[0]*ratios[0]} + {cpi_B[1]*ratios[1]} + {cpi_B[2]*ratios[2]} + {cpi_B[3]*ratios[3]}")
print(f"                 = {result_B['weighted_cpi']:.4f}")
print(f"  MIPS_B = {freq_B_MHz} / {result_B['weighted_cpi']:.4f} = {result_B['mips']:.4f}")
print(f"  exec_time_B (formula1: N*CPI/f)  = {total_instructions}*{result_B['weighted_cpi']:.4f}/{result_B['freq_Hz']:.4e} = {result_B['exec_time_f1']:.6f} s")
print(f"  exec_time_B (formula2: N/(MIPS*1e6)) = {result_B['exec_time_f2']:.6f} s")
print()

print("=" * 60)
print("RESULT:")
print(f"  Q1: weighted_CPI_A = {result_A['weighted_cpi']:.2f}")
print(f"      weighted_CPI_B = {result_B['weighted_cpi']:.2f}")
print(f"  Q2: MIPS_A = {result_A['mips']:.2f}")
print(f"      MIPS_B = {result_B['mips']:.2f}")
print(f"  Q3: exec_time_A = {result_A['exec_time_f1']:.4f} s")
print(f"      exec_time_B = {result_B['exec_time_f1']:.4f} s")
faster = "A" if result_A['exec_time_f1'] < result_B['exec_time_f1'] else "B"
speedup = max(result_A['exec_time_f1'], result_B['exec_time_f1']) / min(result_A['exec_time_f1'], result_B['exec_time_f1'])
print(f"      {faster} 更快（执行时间更短），加速比 = {speedup:.4f}")
print()

print("=" * 60)
print("RULE_CHECK (场景规则验证):")
print(f"  R1 占比归一: sum(ratios) = {sum(ratios)} (==1.0? {abs(sum(ratios)-1.0)<1e-9})")
print(f"  R2 加权CPI_A = Σ(CPI_i*ratio_i) = {sum(c*r for c,r in zip(cpi_A,ratios)):.4f} (直接算: {result_A['weighted_cpi']:.4f})")
print(f"  R2 加权CPI_B = Σ(CPI_i*ratio_i) = {sum(c*r for c,r in zip(cpi_B,ratios)):.4f} (直接算: {result_B['weighted_cpi']:.4f})")
print(f"  R3 MIPS_A = freq_MHz/CPI = {freq_A_MHz}/{result_A['weighted_cpi']:.4f} = {result_A['mips']:.4f}")
print(f"  R3 MIPS_B = freq_MHz/CPI = {freq_B_MHz}/{result_B['weighted_cpi']:.4f} = {result_B['mips']:.4f}")
print(f"  R4 定义一致性 A: formula1={result_A['exec_time_f1']:.10f}, formula2={result_A['exec_time_f2']:.10f}, equal={abs(result_A['exec_time_f1']-result_A['exec_time_f2'])<1e-9}")
print(f"  R4 定义一致性 B: formula1={result_B['exec_time_f1']:.10f}, formula2={result_B['exec_time_f2']:.10f}, equal={abs(result_B['exec_time_f1']-result_B['exec_time_f2'])<1e-9}")
print(f"  R5 执行时间不同: A={result_A['exec_time_f1']:.6f}, B={result_B['exec_time_f1']:.6f}, 不同={abs(result_A['exec_time_f1']-result_B['exec_time_f1'])>1e-9}, 更快者={faster}")
print(f"  R6 参数合法: all CPI in [1,8] A={all(1<=c<=8 for c in cpi_A)}, B={all(1<=c<=8 for c in cpi_B)}")
print(f"  R6 频率合法: A={200<=freq_A_MHz<=800}, B={200<=freq_B_MHz<=800}")
print(f"  R6 频率不同: {freq_A_MHz != freq_B_MHz}")
print(f"  R6 CPI不完全相同: {cpi_A != cpi_B}")
