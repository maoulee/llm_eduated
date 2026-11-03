# -*- coding: utf-8 -*-
"""
中断 I/O 方式可行性分析 —— 建模+求解
把 question.md 的运算规则翻译成代码，通过条件翻译成 assert。
"""
from fractions import Fraction

# ========== PARAMS ==========
PARAMS = {
    "cpu_clock_freq_MHz": 250,     # CPU 主频 250 MHz
    "isr_cycles": 600,             # ISR 每次所需时钟周期数
    "device_A_rate_KBps": 5,       # 外设 A 数据传输率 5 KB/s
    "device_B_rate_MBps": 3,       # 外设 B 数据传输率 3 MB/s
}

# ========== 翻译题干运算规则 ==========

def compute_clock_period_ns(freq_MHz):
    """Q1(1): 主频 -> 时钟周期 (ns)
    T_clock = 1 / (freq_MHz * 1e6) s = 1e9 / (freq_MHz * 1e6) ns = 1000 / freq_MHz ns
    用 Fraction 保证精确。
    """
    return Fraction(1000, freq_MHz)  # ns


def compute_isr_time_us(freq_MHz, cycles):
    """Q1(2): 中断服务时间 (us)
    T_ISR = cycles * T_clock(ns) = cycles * 1000/freq_MHz ns
    转 us: / 1000  => cycles / freq_MHz  us
    """
    return Fraction(cycles, freq_MHz)  # us


def arrival_interval_us(rate_bytes_per_sec):
    """Q2/Q3: 数据到达间隔 (us) = 1 / rate (秒) * 1e6 = 1e6 / rate (us)
    rate 以 Byte/s 为单位（字节粒度逐字节传输）。
    """
    return Fraction(10**6, rate_bytes_per_sec)  # us


def feasibility(T_isr, T_arrival):
    """可行性判断：
    中断 I/O 可行  <=>  T_ISR < T_arrival
    （在中断响应延迟=0 的前提下，服务完 1 字节后下一字节还未到达即可）
    """
    return T_isr < T_arrival


# ========== 求解 ==========

freq = PARAMS["cpu_clock_freq_MHz"]  # 250 MHz
isr_cyc = PARAMS["isr_cycles"]       # 600
rate_A = PARAMS["device_A_rate_KBps"] * 1000   # 5 KB/s = 5000 B/s
rate_B = PARAMS["device_B_rate_MBps"] * 10**6  # 3 MB/s = 3000000 B/s

# Q1
T_clock_ns = compute_clock_period_ns(freq)
T_ISR_us   = compute_isr_time_us(freq, isr_cyc)

# Q2
T_arrival_A_us = arrival_interval_us(rate_A)
feasible_A = feasibility(T_ISR_us, T_arrival_A_us)

# Q3
T_arrival_B_us = arrival_interval_us(rate_B)
feasible_B = feasibility(T_ISR_us, T_arrival_B_us)

# ========== 输出 ==========

print("===== PARAMS =====")
for k, v in PARAMS.items():
    print(f"  {k} = {v}")
print(f"  rate_A = {rate_A} B/s")
print(f"  rate_B = {rate_B} B/s")

print("\n===== REASONING =====")
print(f"[Q1] CPU 主频 = {freq} MHz = {freq}*10^6 Hz")
print(f"  T_clock = 1 / ({freq}*10^6) s = {T_clock_ns} ns  (= {float(T_clock_ns):.2f} ns)")
print(f"  T_ISR   = {isr_cyc} * {T_clock_ns} ns = {isr_cyc * T_clock_ns} ns")
print(f"         = {isr_cyc * T_clock_ns} / 1000 us = {T_ISR_us} us  (= {float(T_ISR_us):.2f} us)")

print(f"\n[Q2] 外设 A 速率 = {PARAMS['device_A_rate_KBps']} KB/s = {rate_A} B/s")
print(f"  T_arrival_A = 1 / {rate_A} s = {float(1/rate_A)*10**6:.2f} us")
print(f"              = {T_arrival_A_us} us  (= {float(T_arrival_A_us):.2f} us)")
print(f"  比较: T_ISR = {float(T_ISR_us):.2f} us,  T_arrival_A = {float(T_arrival_A_us):.2f} us")
print(f"  T_ISR < T_arrival_A ? {feasible_A}")
print(f"  结论: {'可行' if feasible_A else '不可行'}")
print(f"  差值倍数: T_arrival_A / T_ISR = {float(T_arrival_A_us / T_ISR_us):.2f}")

print(f"\n[Q3] 外设 B 速率 = {PARAMS['device_B_rate_MBps']} MB/s = {rate_B} B/s")
print(f"  T_arrival_B = 1 / {rate_B} s")
print(f"              = {T_arrival_B_us} us  (= {float(T_arrival_B_us):.2f} us)")
print(f"  比较: T_ISR = {float(T_ISR_us):.2f} us,  T_arrival_B = {float(T_arrival_B_us):.2f} us")
print(f"  T_ISR < T_arrival_B ? {feasible_B}")
print(f"  结论: {'可行' if feasible_B else '不可行'}")
print(f"  差值倍数: T_ISR / T_arrival_B = {float(T_ISR_us / T_arrival_B_us):.2f}")

print("\n===== ANSWER =====")
print(f"  Q1(1) 时钟周期 T_clock = {T_clock_ns} ns")
print(f"  Q1(2) 中断服务时间 T_ISR = {T_ISR_us} us (= {float(T_ISR_us):.2f} us)")
print(f"  Q2(1) T_arrival_A = {T_arrival_A_us} us (= {float(T_arrival_A_us):.2f} us)")
print(f"  Q2(2) 外设 A: {'可行' if feasible_A else '不可行'}")
print(f"  Q3(1) T_arrival_B = {T_arrival_B_us} us (= {float(T_arrival_B_us):.2f} us)")
print(f"  Q3(2) 外设 B: {'可行' if feasible_B else '不可行'}")
print(f"  Q3(3) 关键因素: 中断服务时间 T_ISR 必须小于数据到达间隔 T_arrival (T_ISR < T_arrival)")

# ========== 通过条件 -> assert ==========

# 条件1: 时钟周期 = 4 ns，为正整数纳秒值
assert T_clock_ns == 4, f"T_clock 应为 4 ns，实际 {T_clock_ns}"
assert T_clock_ns.denominator == 1 and T_clock_ns > 0, "T_clock 应为正整数纳秒值"

# 条件2: T_ISR = 600 * 4 = 2400 ns = 2.4 us
assert T_ISR_us == Fraction(12, 5), f"T_ISR 应为 2.4 us (=12/5)，实际 {T_ISR_us}"
assert isr_cyc * T_clock_ns == 2400, f"T_ISR(ns) 应为 2400，实际 {isr_cyc * T_clock_ns}"

# 条件3: 外设 A 可行，T_arrival_A = 200 us, 差值 >= 10 倍
assert T_arrival_A_us == 200, f"T_arrival_A 应为 200 us，实际 {T_arrival_A_us}"
assert feasible_A == True, "外设 A 应为可行"
assert T_arrival_A_us / T_ISR_us >= 10, f"外设 A 差值应 >= 10 倍，实际 {T_arrival_A_us / T_ISR_us}"

# 条件4: 外设 B 不可行，T_arrival_B ≈ 0.33 us, 差值 >= 2 倍
assert T_arrival_B_us == Fraction(1, 3), f"T_arrival_B 应为 1/3 us，实际 {T_arrival_B_us}"
assert feasible_B == False, "外设 B 应为不可行"
assert T_ISR_us / T_arrival_B_us >= 2, f"外设 B 差值应 >= 2 倍，实际 {T_ISR_us / T_arrival_B_us}"

# 条件5: 结论互斥 —— 两设备方向相反
assert feasible_A != feasible_B, "两设备结论应相反（互斥）"

# 条件6: 非临界 —— 两设备比值均不落在 [0.8, 1.2]
ratio_A = float(T_ISR_us / T_arrival_A_us)   # T_ISR / T_arrival_A
ratio_B = float(T_ISR_us / T_arrival_B_us)   # T_ISR / T_arrival_B
for r in (ratio_A, ratio_B):
    assert not (0.8 <= r <= 1.2), f"比值 {r} 落在临界 [0.8,1.2]，题目存在歧义"

print("\n===== ALL ASSERTS PASSED =====")
