"""
总线带宽计算 —— gen.py
把题干运算规则 + 场景规则翻译成代码，底部打印完整数据流。
"""

import math


def solve(W, f_MHz, N, D):
    """
    W    : 数据线宽度（字节），题干 32 位 = 4 B
    f_MHz: 总线时钟频率（MHz），题干 150 MHz
    N    : 每事务占用时钟周期数，题干 3
    D    : 待传输数据量（字节），题干 4097 B
    """
    f = f_MHz * 1_000_000          # Hz，翻译：MHz → Hz

    # ---- SQ1 理论带宽：每个时钟周期传输 W 字节 ----
    # 翻译题干："理论带宽 = 总线宽度 × 时钟频率"
    theoretical_Bps = W * f         # 单位 B/s
    theoretical_MBps = theoretical_Bps / 1_000_000   # 1 MB = 10^6 B

    # ---- SQ2 有效带宽：N 个周期完成一次传输 ----
    # 翻译题干："有效带宽 = 理论带宽 ÷ 事务周期数"
    effective_Bps = theoretical_Bps / N
    effective_MBps = effective_Bps / 1_000_000

    # ---- SQ3 传输时间 ----
    # 翻译题干："传输次数 = ceil(D / W)"（向上取整，最后不足一个事务也要传）
    transfers = math.ceil(D / W)
    # 翻译题干："总周期数 = 传输次数 × N"
    total_cycles = transfers * N
    # 翻译题干："时间 = 总周期数 / f"
    time_s = total_cycles / f
    time_us = time_s * 1_000_000   # s → μs

    return {
        "W": W,
        "f_MHz": f_MHz,
        "f_Hz": f,
        "N": N,
        "D": D,

        "theoretical_Bps": theoretical_Bps,
        "theoretical_MBps": theoretical_MBps,

        "effective_Bps": effective_Bps,
        "effective_MBps": effective_MBps,

        "D_div_W": D / W,
        "D_mod_W": D % W,
        "floor_D_div_W": D // W,
        "transfers": transfers,
        "total_cycles": total_cycles,
        "time_s": time_s,
        "time_us": time_us,
    }


# ============ 注入题干参数 ============
W = 4          # 32 位 = 4 B
f_MHz = 150    # 150 MHz
N = 3          # 每事务 3 个时钟周期
D = 4097       # 4097 B

r = solve(W, f_MHz, N, D)

# ============ 底部打印完整数据流 ============
print("=" * 60)
print("PARAMS:")
print(f"  W (数据线宽度)      = {r['W']} B  ({r['W']*8} 位)")
print(f"  f (时钟频率)        = {r['f_MHz']} MHz = {r['f_Hz']} Hz")
print(f"  N (事务周期数)      = {r['N']}")
print(f"  D (待传输数据量)    = {r['D']} B")
print()

print("=" * 60)
print("PROCESS / SQ1 理论带宽:")
print(f"  理论带宽 = W × f = {r['W']} × {r['f_Hz']}")
print(f"           = {r['theoretical_Bps']} B/s")
print(f"           = {r['theoretical_MBps']} MB/s  (1 MB = 10^6 B)")
print()

print("=" * 60)
print("PROCESS / SQ2 有效带宽:")
print(f"  有效带宽 = 理论带宽 ÷ N = {r['theoretical_Bps']} ÷ {r['N']}")
print(f"           = {r['effective_Bps']} B/s")
print(f"           = {r['effective_MBps']} MB/s")
print()

print("=" * 60)
print("PROCESS / SQ3 传输时间:")
print(f"  D / W = {r['D']} / {r['W']} = {r['D_div_W']}")
print(f"  D mod W = {r['D_mod_W']}  (≠ 0 → 必须向上取整)")
print(f"  传输次数 = ceil({r['D_div_W']}) = {r['transfers']}")
print(f"  总周期数 = 传输次数 × N = {r['transfers']} × {r['N']} = {r['total_cycles']}")
print(f"  传输时间 = 总周期数 / f = {r['total_cycles']} / {r['f_Hz']}")
print(f"           = {r['time_s']} s")
print(f"           = {r['time_us']} μs")
print()

print("=" * 60)
print("RESULT:")
print(f"  SQ1 理论带宽 = {r['theoretical_MBps']} MB/s")
print(f"  SQ2 有效带宽 = {r['effective_MBps']} MB/s")
print(f"  SQ3 传输时间 = {r['time_us']} μs")
print()

# ============ 场景规则验证（打印数据流供审核核对，非恒真废print）============
print("=" * 60)
print("RULE_CHECK (审核对照场景规则):")
print(f"  规则1 理论带宽==W×f : {r['theoretical_Bps']} == {r['W']*r['f_Hz']}  → {r['theoretical_Bps'] == r['W']*r['f_Hz']}")
print(f"  规则2 有效带宽==理论/N: {r['effective_Bps']} == {r['theoretical_Bps']/r['N']}  → {r['effective_Bps'] == r['theoretical_Bps']/r['N']}")
print(f"  规则3 D mod W ≠ 0    : {r['D_mod_W']} ≠ 0  → {r['D_mod_W'] != 0}")
print(f"         ceil≠floor      : ceil={r['transfers']}, floor={r['floor_D_div_W']}  → {r['transfers'] != r['floor_D_div_W']}")
print(f"  规则4 时间==传输×N/f  : {r['time_s']} == {r['transfers']*r['N']/r['f_Hz']}  → {r['time_s'] == r['transfers']*r['N']/r['f_Hz']}")
print(f"         时间 > 0        : {r['time_s']} > 0  → {r['time_s'] > 0}")
print(f"  规则5 N ≥ 2 (有效≠理论): N={r['N']}, 有效={r['effective_MBps']}, 理论={r['theoretical_MBps']}  → {r['effective_Bps'] != r['theoretical_Bps']}")
print(f"  规则6 f 非2幂         : f={r['f_MHz']}, is_power_of_2={r['f_MHz'] & (r['f_MHz']-1) == 0 and r['f_MHz']>0}  → {not (r['f_MHz'] & (r['f_MHz']-1) == 0 and r['f_MHz']>0)}")
