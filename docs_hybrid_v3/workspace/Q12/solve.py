from decimal import Decimal, getcontext

getcontext().prec = 28

# ===== 题目参数定义 =====
instruction_count = Decimal("4.0") * (Decimal(10) ** 7)  # 题干给定：4.0 × 10^7 条指令
average_cpi = Decimal("1.5")                            # 题干给定：平均 CPI 为 1.5
cpu_time_ms = Decimal("24")                             # 题干给定：用户 CPU 时间为 24 ms

milliseconds_per_second = Decimal("1000")
hz_per_ghz = Decimal(10) ** 9

option_frequency_ghz = {
    "A": Decimal("1.0"),
    "B": Decimal("1.67"),
    "C": Decimal("2.5"),
    "D": Decimal("25"),
}

# ===== 单位换算 =====
cpu_time_seconds = cpu_time_ms / milliseconds_per_second

print("===== 单位换算 =====")
print(f"指令条数 IC = {instruction_count} 条")
print(f"平均 CPI = {average_cpi}")
print(f"CPU 时间 = {cpu_time_ms} ms")
print(f"CPU 时间换算为秒: {cpu_time_ms} / {milliseconds_per_second} = {cpu_time_seconds} s")

# ===== 主频计算 =====
total_clock_cycles = instruction_count * average_cpi
cpu_frequency_hz = total_clock_cycles / cpu_time_seconds
cpu_frequency_ghz = cpu_frequency_hz / hz_per_ghz

print("\n===== 主频计算 =====")
print("CPU 执行时间公式: T_CPU = IC × CPI / f")
print("变形得到: f = IC × CPI / T_CPU")
print(f"总时钟周期数 = IC × CPI = {instruction_count} × {average_cpi} = {total_clock_cycles}")
print(f"主频 f = {total_clock_cycles} / {cpu_time_seconds} = {cpu_frequency_hz} Hz")
print(f"主频换算为 GHz = {cpu_frequency_hz} / {hz_per_ghz} = {cpu_frequency_ghz} GHz")

# ===== 逐选项验证 =====
print("\n===== 逐选项验证 =====")
matched_options = []
tolerance_hz = Decimal("0.000001")

for option_label in ["A", "B", "C", "D"]:
    option_ghz = option_frequency_ghz[option_label]
    option_hz = option_ghz * hz_per_ghz
    difference_hz = abs(option_hz - cpu_frequency_hz)
    is_match = difference_hz <= tolerance_hz

    print(f"选项 {option_label}: {option_ghz} GHz")
    print(f"  换算为 Hz: {option_ghz} × {hz_per_ghz} = {option_hz} Hz")
    print(f"  与计算主频差值: |{option_hz} - {cpu_frequency_hz}| = {difference_hz} Hz")
    print(f"  是否匹配: {is_match}")

    if is_match:
        matched_options.append(option_label)

# ===== 最终答案 =====
if len(matched_options) != 1:
    raise ValueError(f"匹配到的选项数量不是 1，实际匹配选项: {matched_options}")

final_answer = matched_options[0]
print(f"\n计算得到主频为 {cpu_frequency_ghz} GHz，对应选项 {final_answer}")
print(f"ANSWER: {final_answer}")
