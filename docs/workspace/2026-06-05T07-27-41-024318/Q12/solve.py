# ===== 题目参数定义 =====
frequency_GHz = 2.0  # 主频 2.0 GHz
instruction_count = 20000  # 指令总数

# 指令分布
ratio_1 = 0.4  # 40% 指令需 1 个时钟周期
cpi_1 = 1
ratio_2 = 0.4  # 40% 指令需 2 个时钟周期
cpi_2 = 2
ratio_3 = 0.2  # 20% 指令需 4 个时钟周期
cpi_3 = 4

# ===== 子问题(1) =====
# 计算加权平均 CPI
average_cpi = ratio_1 * cpi_1 + ratio_2 * cpi_2 + ratio_3 * cpi_3
print(f"子问题(1): 计算平均 CPI 和 CPU 执行时间")
print(f"  加权平均 CPI = {ratio_1}×{cpi_1} + {ratio_2}×{cpi_2} + {ratio_3}×{cpi_3}")
print(f"  加权平均 CPI = {ratio_1 * cpi_1} + {ratio_2 * cpi_2} + {ratio_3 * cpi_3}")
print(f"  平均 CPI = {average_cpi}")

# 计算总时钟周期
total_cycles = instruction_count * average_cpi
print(f"  总时钟周期 = {instruction_count} × {average_cpi} = {total_cycles}")

# 计算 CPU 执行时间
frequency_Hz = frequency_GHz * 1e9  # GHz 转 Hz
cpu_time_s = total_cycles / frequency_Hz  # 秒
cpu_time_us = cpu_time_s * 1e6  # 秒转微秒
print(f"  主频 = {frequency_GHz} GHz = {frequency_Hz} Hz")
print(f"  CPU 执行时间 = {total_cycles} / {frequency_Hz} = {cpu_time_s} 秒")
print(f"  CPU 执行时间 = {cpu_time_us} μs")

print(f"\n  答案: CPI = {average_cpi}, 执行时间 = {cpu_time_us} μs")
print(f"  对应选项: C. 2.0，20 μs")
