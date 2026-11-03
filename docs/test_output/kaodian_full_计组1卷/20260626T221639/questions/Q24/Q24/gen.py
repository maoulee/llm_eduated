# -*- coding: utf-8 -*-
"""
总线带宽计算 —— gen.py
题干规则翻译：B = (W / 8) × (f × 10^6) / n  (MB/s)
场景规则：
  1. 公式一致性：B 严格等于 (W/8)*(f*1e6)/n
  2. 结果合理性：100 <= B <= 2000
  3. 结果非平凡：B % 100 != 0
"""
from fractions import Fraction


def solve(W_bit, f_MHz, n):
    """题干规则逐句翻译：带宽 = (数据宽度/8 Byte) × (每秒传输次数)"""
    # 翻译："W 单位 bit，÷8 转 Byte"
    W_byte = Fraction(W_bit, 8)
    # 翻译："f 单位 MHz，×10^6 转 Hz"
    f_Hz = Fraction(f_MHz) * 10**6
    # 翻译："每传输一次需 n 个时钟周期" → 每秒传输次数 = f_Hz / n
    transfers_per_sec = f_Hz / n
    # 带宽 = 每次传的字节数 × 每秒传输次数
    B = W_byte * transfers_per_sec          # 单位 Byte/s
    B_MBps = B / Fraction(10**6)            # 转 MB/s（1 MB = 10^6 B）

    # 错误路径产物（供分析"跳过某步换算"会得到什么，展示区分度）
    # 错误1：忘记 ÷n
    err_skip_n = (W_byte * f_Hz) / Fraction(10**6)
    # 错误2：bit/Byte 搞反（不除8）
    err_no_div8 = Fraction(W_bit) * f_Hz / n / Fraction(10**6)
    # 错误3：MHz 没乘 10^6
    err_no_MHz = W_byte * Fraction(f_MHz) / n

    return {
        "W_bit": W_bit,
        "W_byte": W_byte,
        "f_MHz": f_MHz,
        "f_Hz": f_Hz,
        "n": n,
        "transfers_per_sec": transfers_per_sec,
        "B_Bytes_per_sec": B,
        "B_MBps": B_MBps,
        "B_MBps_float": float(B_MBps),
        "B_MBps_2dp": float(round(B_MBps, 2)),
        "err_skip_n": float(err_skip_n),
        "err_no_div8": float(err_no_div8),
        "err_no_MHz": float(err_no_MHz),
    }


# ---- 注入题干参数跑 ----
W, f, n = 64, 250, 3
res = solve(W, f, n)

# ---- 场景规则验证（打特征，非恒真）----
B_val = res["B_MBps"]
rule1_formula_consistency = (B_val == Fraction(W, 8) * Fraction(f) * 10**6 / n / 10**6)
rule2_reasonable = (100 <= B_val <= 2000)
rule3_nontrivial = (B_val % 100 != 0)

# ---- 底部：完整数据流 ----
print("=" * 60)
print("PARAMS:")
print(f"  总线数据宽度 W = {res['W_bit']} bit")
print(f"  总线时钟频率 f = {res['f_MHz']} MHz")
print(f"  每传输周期时钟周期数 n = {res['n']}")
print()
print("PROCESS:")
print(f"  Step1 bit→Byte: W = {res['W_bit']} bit = {res['W_bit']}/8 = {res['W_byte']} Byte")
print(f"  Step2 MHz→Hz:   f = {res['f_MHz']} MHz = {res['f_MHz']}×10^6 = {res['f_Hz']} Hz")
print(f"  Step3 ÷n:       每秒传输次数 = f/n = {res['f_Hz']}/{res['n']} = {res['transfers_per_sec']} 次/s")
print(f"  Step4 带宽:     B = {res['W_byte']} Byte × {res['transfers_per_sec']} 次/s")
print(f"                   = {res['B_Bytes_per_sec']} Byte/s")
print(f"                   = {res['B_Bytes_per_sec']}/{10**6} MB/s")
print()
print("RESULT:")
print(f"  B = {res['B_MBps']} MB/s ≈ {res['B_MBps_float']:.6f} MB/s")
print(f"  B（保留两位小数）= {res['B_MBps_2dp']:.2f} MB/s")
print()
print("RULE_CHECK:")
print(f"  规则1 公式一致性: B == (W/8)*(f*1e6)/n/1e6 → {rule1_formula_consistency}")
print(f"  规则2 结果合理性: 100 <= B <= 2000 → {rule2_reasonable}  (B={float(B_val):.4f})")
print(f"  规则3 结果非平凡: B % 100 != 0      → {rule3_nontrivial}  (B%100={float(B_val%100):.4f})")
print()
print("ERROR_PATH_DISTINGUISHABILITY (区分度):")
print(f"  正确答案:                    {res['B_MBps_float']:.4f} MB/s")
print(f"  错误-忘除n(×3):             {res['err_skip_n']:.4f} MB/s")
print(f"  错误-bit/Byte搞反(×8):      {res['err_no_div8']:.4f} MB/s")
print(f"  错误-MHz没转(÷1e6):        {res['err_no_MHz']:.4f} MB/s")
print("=" * 60)
