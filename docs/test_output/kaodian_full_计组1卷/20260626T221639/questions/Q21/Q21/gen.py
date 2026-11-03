"""
CPU 性能指标计算题：加权平均 CPI + 执行时间
建模方式：整数取模无关，纯加权算术 + 单位换算翻译。
"""

def solve(cpi_list, ratio_list, N, freq_ghz):
    """
    cpi_list: 各指令类型 CPI
    ratio_list: 各类型使用占比（整数百分比，如 35 表示 35%）
    N: 程序指令总数
    freq_ghz: 主频，单位 GHz
    返回 cpi_avg, T_us
    """
    # 场景规则1：占比归一 —— 占比之和必须 = 100
    ratio_sum = sum(ratio_list)

    # 场景规则2：加权平均定义 CPI_avg = Σ(CPI_i × 占比_i小数形式)
    cpi_avg = sum(c * (r / 100.0) for c, r in zip(cpi_list, ratio_list))

    # 场景规则5：主频 GHz → Hz（×10⁹）
    freq_hz = freq_ghz * 1e9

    # 场景规则4：执行时间公式 T = (N × CPI_avg) / f （秒）
    T_s = (N * cpi_avg) / freq_hz

    # 秒 → μs（×10⁶）
    T_us = T_s * 1e6

    return cpi_avg, T_us, ratio_sum, freq_hz, T_s


# ======================== 注入参数跑 ========================
cpi_list   = [1, 3, 6, 10]
ratio_list = [35, 30, 25, 10]
N          = 100000
freq_ghz   = 2.5

cpi_avg, T_us, ratio_sum, freq_hz, T_s = solve(cpi_list, ratio_list, N, freq_ghz)

# ======================== 底部：打印完整数据流 ========================
print("=" * 60)
print("PARAMS:")
print(f"  指令类型CPI = {cpi_list}")
print(f"  使用占比(%) = {ratio_list}")
print(f"  占比之和 = {ratio_sum}%")
print(f"  程序指令总数 N = {N}")
print(f"  主频 = {freq_ghz} GHz")
print()

# --- 第1问过程 ---
print("Q1_PROCESS (加权平均CPI):")
terms = []
for c, r in zip(cpi_list, ratio_list):
    terms.append(f"{c}×{r}%")
    print(f"  {c} × {r/100.0:.2f} = {c * r / 100.0:.2f}")
print(f"  求和: {' + '.join(terms)} = {cpi_avg}")
print()

# --- 第2问过程 ---
print("Q2_PROCESS (执行时间):")
print(f"  f = {freq_ghz} GHz = {freq_ghz} × 10^9 Hz = {freq_hz:.0e} Hz")
print(f"  T = (N × CPI_avg) / f")
print(f"    = ({N} × {cpi_avg}) / {freq_hz:.0e}")
total_cycles = N * cpi_avg
print(f"    = {total_cycles} / {freq_hz:.0e}")
print(f"    = {T_s:.10f} s")
print(f"  换算为 μs: T = {T_s:.10f} s × 10^6 = {T_us} μs")
print()

# --- 最终结果 ---
print("RESULT:")
print(f"  第1问 平均CPI = {cpi_avg}")
print(f"  第2问 执行时间 = {T_us} μs (保留两位小数 = {round(T_us, 2)} μs)")
print()

# --- 场景规则验证（数据流裸露，供审核对照） ---
print("RULE_CHECK (场景规则对照):")
print(f"  规则1 占比归一: Σ占比 = {ratio_sum}%  {'✓' if ratio_sum == 100 else '✗'}")
frac = cpi_avg - int(cpi_avg)
print(f"  规则3 CPI非整数: CPI_avg = {cpi_avg}, 小数部分 = {frac:.2f}  {'✓' if frac != 0 else '✗'}")
print(f"  规则4 执行时间公式: N×CPI_avg = {total_cycles}, f = {freq_hz:.0e}, T = {T_s:.10f} s")
print(f"  规则5 单位换算: GHz→Hz ({freq_ghz}→{freq_hz:.0e}), s→μs (×10^6)")
print(f"  规则6 量级合理: T = {T_us} μs  {'✓' if 1 <= T_us <= 1e6 else '✗'}")
print("=" * 60)
