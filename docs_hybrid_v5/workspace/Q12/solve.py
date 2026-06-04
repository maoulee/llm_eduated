from decimal import Decimal, getcontext

getcontext().prec = 28

# ===== 题目参数定义 =====
cpu_frequency_ghz = Decimal("2")                 # 主频 2 GHz
cpu_frequency_hz = cpu_frequency_ghz * (Decimal(10) ** 9)

instruction_count = Decimal("4") * (Decimal(10) ** 6)  # 指令条数 4 × 10^6

instruction_classes = [
    {"proportion": Decimal("0.50"), "cpi": Decimal("1")},
    {"proportion": Decimal("0.25"), "cpi": Decimal("2")},
    {"proportion": Decimal("0.25"), "cpi": Decimal("4")},
]

options_ms = {
    "A": Decimal("2"),
    "B": Decimal("4"),
    "C": Decimal("8"),
    "D": Decimal("16"),
}

def format_decimal(value):
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return str(normalized)

# ===== 平均 CPI 计算 =====
average_cpi = Decimal("0")
print("===== 平均 CPI 计算 =====")
for index, instruction_class in enumerate(instruction_classes, start=1):
    proportion = instruction_class["proportion"]
    cpi = instruction_class["cpi"]
    weighted_cpi = proportion * cpi
    average_cpi += weighted_cpi
    print(f"第{index}类指令: 比例={proportion}, CPI={cpi}, 加权贡献={weighted_cpi}")

print(f"平均 CPI = {average_cpi}")

# ===== CPU 时钟周期数计算 =====
total_cpu_cycles = instruction_count * average_cpi
print("===== CPU 时钟周期数计算 =====")
print(f"指令条数 IC = {format_decimal(instruction_count)}")
print(f"平均 CPI = {format_decimal(average_cpi)}")
print(f"总 CPU 周期数 = IC × CPI = {format_decimal(total_cpu_cycles)}")

# ===== CPU 执行时间计算 =====
cpu_time_seconds = total_cpu_cycles / cpu_frequency_hz
cpu_time_ms = cpu_time_seconds * Decimal("1000")

print("===== CPU 执行时间计算 =====")
print(f"CPU 主频 = {format_decimal(cpu_frequency_hz)} Hz")
print(f"CPU 执行时间 = 总 CPU 周期数 / 主频 = {cpu_time_seconds} s")
print(f"CPU 执行时间 = {format_decimal(cpu_time_ms)} ms")

# ===== 逐选项验证 =====
print("===== 逐选项验证 =====")
matching_options = []

for option_label, option_time_ms in options_ms.items():
    difference_ms = abs(cpu_time_ms - option_time_ms)
    is_correct = difference_ms == Decimal("0")
    if is_correct:
        matching_options.append(option_label)

    print(
        f"选项 {option_label}: {format_decimal(option_time_ms)} ms, "
        f"与计算结果差值 = {format_decimal(difference_ms)} ms, "
        f"判断 = {'正确' if is_correct else '错误'}"
    )

# ===== 最终答案 =====
if len(matching_options) != 1:
    raise ValueError(f"匹配到的正确选项数量不是 1，实际匹配结果: {matching_options}")

correct_answer = matching_options[0]
print(f"ANSWER: {correct_answer}")
