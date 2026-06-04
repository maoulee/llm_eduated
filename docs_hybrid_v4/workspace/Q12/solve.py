from fractions import Fraction

# ===== 题目参数定义 =====
instruction_count = 1 * 10**8          # 题干给定：共执行 1×10^8 条指令
average_cpi = Fraction(25, 10)         # 题干给定：平均 CPI 为 2.5
cpu_frequency_ghz = 2                  # 题干给定：CPU 主频为 2 GHz
hz_per_ghz = 10**9                     # 单位换算：1 GHz = 10^9 Hz

option_values = {
    "A": Fraction(5, 100),             # 0.05 s
    "B": Fraction(125, 1000),          # 0.125 s
    "C": Fraction(8, 10),              # 0.8 s
    "D": Fraction(125, 1),             # 125 s
}

# ===== 公式计算 =====
cpu_frequency_hz = cpu_frequency_ghz * hz_per_ghz
total_clock_cycles = instruction_count * average_cpi
cpu_execution_time = total_clock_cycles / cpu_frequency_hz

print("===== 题目参数 =====")
print(f"指令条数 = {instruction_count}")
print(f"平均 CPI = {float(average_cpi)}")
print(f"CPU 主频 = {cpu_frequency_ghz} GHz")
print(f"1 GHz = {hz_per_ghz} Hz")
print(f"CPU 主频换算为 Hz = {cpu_frequency_hz} Hz")

print("\n===== CPU 执行时间计算 =====")
print("公式：CPU执行时间 = 指令条数 × CPI / 时钟频率")
print(f"总时钟周期数 = {instruction_count} × {float(average_cpi)} = {float(total_clock_cycles)}")
print(f"CPU执行时间 = {float(total_clock_cycles)} / {cpu_frequency_hz}")
print(f"CPU执行时间 = {float(cpu_execution_time)} s")

# ===== 逐选项验证 =====
print("\n===== 逐选项验证 =====")
correct_option = None

for option_label, option_time in option_values.items():
    difference = abs(cpu_execution_time - option_time)
    is_correct = difference == 0

    print(f"选项 {option_label}: {float(option_time)} s")
    print(f"  计算结果 = {float(cpu_execution_time)} s")
    print(f"  与计算结果差值 = {float(difference)} s")
    print(f"  是否正确 = {is_correct}")

    if is_correct:
        correct_option = option_label

# ===== 最终答案 =====
print(f"\nANSWER: {correct_option}")
