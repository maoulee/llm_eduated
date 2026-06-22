# -*- coding: utf-8 -*-
"""
计算机系统总线带宽与性能分析求解代码
"""

# ============================================================
# 题目参数定义
# ============================================================
bus_width_bits = 64          # 数据总线宽度（位）
bus_width_bytes = bus_width_bits // 8  # 数据总线宽度（字节）= 8字节
bus_clock_freq_MHz = 500     # 总线时钟频率（MHz）
bus_clock_freq_Hz = bus_clock_freq_MHz * 10**6  # 总线时钟频率（Hz）
bus_clock_period_ns = 1000 / bus_clock_freq_MHz  # 总线时钟周期（ns）= 2ns

burst_word_count = 8         # 每次突发传输字块数
first_word_cycles = 4        # 首字块传输所需总线时钟周期数
subsequent_word_cycles = 1   # 后续每个字块所需总线时钟周期数

memory_access_time_ns = 80   # 内存访问周期（ns）

cpu_freq_GHz = 2             # CPU主频（GHz）
cpu_freq_Hz = cpu_freq_GHz * 10**9  # CPU主频（Hz）
cpu_clock_period_ns = 1000 / cpu_freq_GHz  # CPU时钟周期（ns）= 0.5ns

avg_cpi = 1                  # 平均CPI（每条指令时钟周期数）
instructions_per_burst = 100 # 每执行100条指令发起1次突发传输

# 单位换算：1 GB = 10^9 Byte
GB = 10**9

print("=" * 70)
print("计算机系统总线带宽与性能分析")
print("=" * 70)

# ============================================================
# 子问题(1)：理论带宽与有效带宽
# ============================================================
print("\n【子问题(1)】计算理论带宽与有效带宽")
print("-" * 50)

# 理论带宽 = 总线宽度(字节) × 总线时钟频率(Hz)
theoretical_bandwidth_Bps = bus_width_bytes * bus_clock_freq_Hz
theoretical_bandwidth_GBs = theoretical_bandwidth_Bps / GB

print(f"总线宽度: {bus_width_bits}位 = {bus_width_bytes}字节")
print(f"总线时钟频率: {bus_clock_freq_MHz} MHz = {bus_clock_freq_Hz} Hz")
print(f"总线时钟周期: {bus_clock_period_ns} ns")
print(f"理论带宽 = {bus_width_bytes}字节 × {bus_clock_freq_Hz} Hz")
print(f"         = {theoretical_bandwidth_Bps} B/s")
print(f"         = {theoretical_bandwidth_GBs:.3f} GB/s")

# 有效带宽计算
# 一次突发传输的总线传输时间
total_bus_cycles = first_word_cycles + (burst_word_count - 1) * subsequent_word_cycles
bus_transfer_time_ns = total_bus_cycles * bus_clock_period_ns

print(f"\n突发传输参数:")
print(f"  每次突发传输字块数: {burst_word_count}")
print(f"  首字块周期数: {first_word_cycles}")
print(f"  后续字块周期数: {subsequent_word_cycles}")
print(f"  总线传输总周期数 = {first_word_cycles} + ({burst_word_count}-1) × {subsequent_word_cycles}")
print(f"                   = {total_bus_cycles} 个总线时钟周期")
print(f"  总线传输时间 = {total_bus_cycles} × {bus_clock_period_ns} ns = {bus_transfer_time_ns} ns")

# 有效带宽 = 一次突发传输的数据量 / 总线传输时间
# 注意：有效带宽仅考虑总线传输时间，不包含内存访问时间
burst_data_bytes = burst_word_count * bus_width_bytes
effective_bandwidth_Bps = burst_data_bytes / (bus_transfer_time_ns * 10**-9)
effective_bandwidth_GBs = effective_bandwidth_Bps / GB

print(f"\n一次突发传输数据量: {burst_word_count} × {bus_width_bytes} = {burst_data_bytes} 字节")
print(f"有效带宽 = {burst_data_bytes}字节 / {bus_transfer_time_ns}ns")
print(f"         = {burst_data_bytes} / ({bus_transfer_time_ns} × 10^-9) B/s")
print(f"         = {effective_bandwidth_Bps:.0f} B/s")
print(f"         = {effective_bandwidth_GBs:.3f} GB/s")

# ============================================================
# 子问题(2)：一次完整突发传输总耗时与CPU等待周期数
# ============================================================
print("\n\n【子问题(2)】计算一次完整突发传输总耗时与CPU等待周期数")
print("-" * 50)

# 总耗时 = 总线传输时间 + 内存访问时间（串行累加）
total_transfer_time_ns = bus_transfer_time_ns + memory_access_time_ns

print(f"总线传输时间: {bus_transfer_time_ns} ns")
print(f"内存访问时间: {memory_access_time_ns} ns")
print(f"总耗时（串行累加）= {bus_transfer_time_ns} + {memory_access_time_ns} = {total_transfer_time_ns} ns")

# CPU等待周期数 = 总耗时 / CPU时钟周期
cpu_wait_cycles = total_transfer_time_ns / cpu_clock_period_ns

print(f"\nCPU主频: {cpu_freq_GHz} GHz = {cpu_freq_Hz} Hz")
print(f"CPU时钟周期: {cpu_clock_period_ns} ns")
print(f"CPU等待周期数 = {total_transfer_time_ns} ns / {cpu_clock_period_ns} ns")
print(f"              = {cpu_wait_cycles:.0f} 个CPU时钟周期")

# ============================================================
# 子问题(3)：CPU有效执行时间占比
# ============================================================
print("\n\n【子问题(3)】计算CPU有效执行时间占比")
print("-" * 50)

# 每执行instructions_per_burst条指令，发起1次突发传输
# 理想指令执行时间（无等待）
ideal_execution_cycles = instructions_per_burst * avg_cpi

# 实际总执行时间 = 理想执行时间 + 等待时间
actual_total_cycles = ideal_execution_cycles + cpu_wait_cycles

# 有效执行时间占比
effective_ratio = ideal_execution_cycles / actual_total_cycles
effective_ratio_percent = effective_ratio * 100

print(f"访存比例: 每 {instructions_per_burst} 条指令发起1次突发传输")
print(f"平均CPI: {avg_cpi}")
print(f"\n理想指令执行时间（无等待）:")
print(f"  = {instructions_per_burst}条 × {avg_cpi} CPI = {ideal_execution_cycles} 个CPU周期")
print(f"\n一次突发传输的CPU等待时间: {cpu_wait_cycles:.0f} 个CPU周期")
print(f"\n实际总执行时间:")
print(f"  = {ideal_execution_cycles} + {cpu_wait_cycles:.0f} = {actual_total_cycles:.0f} 个CPU周期")
print(f"\n有效执行时间占比:")
print(f"  = {ideal_execution_cycles} / {actual_total_cycles:.0f}")
print(f"  = {effective_ratio:.4f}")
print(f"  = {effective_ratio_percent:.2f}%")

# 验证分数形式
from fractions import Fraction
frac = Fraction(ideal_execution_cycles, int(actual_total_cycles))
print(f"  = {frac.numerator}/{frac.denominator}（分数形式）")

# ============================================================
# 性能分析
# ============================================================
print("\n\n【性能分析】")
print("-" * 50)
print(f"1. 理论带宽: {theoretical_bandwidth_GBs:.3f} GB/s")
print(f"2. 有效带宽: {effective_bandwidth_GBs:.3f} GB/s")
print(f"   有效带宽仅为理论带宽的 {effective_bandwidth_GBs/theoretical_bandwidth_GBs*100:.1f}%")
print(f"   原因：突发传输的首字块需要额外的{first_word_cycles}个周期进行总线仲裁与地址建立")
print(f"3. 一次完整突发传输总耗时: {total_transfer_time_ns} ns")
print(f"   其中总线传输: {bus_transfer_time_ns} ns，内存访问: {memory_access_time_ns} ns")
print(f"   内存访问延迟占总耗时的 {memory_access_time_ns/total_transfer_time_ns*100:.1f}%")
print(f"4. CPU等待周期数: {cpu_wait_cycles:.0f} 个")
print(f"5. CPU有效执行时间占比: {effective_ratio_percent:.2f}%")
print(f"   即CPU仅有约{effective_ratio_percent:.2f}%的时间在执行指令，")
print(f"   其余{100-effective_ratio_percent:.2f}%的时间处于停滞状态等待数据")
print(f"\n结论：总线突发传输的初始化开销与内存访问延迟导致CPU长时间停滞，")
print(f"有效执行时间占比显著降低，总线与存储子系统成为系统性能瓶颈。")

print("\n" + "=" * 70)
print("【最终答案汇总】")
print("=" * 70)
print(f"(1) 理论带宽: {theoretical_bandwidth_GBs:.3f} GB/s")
print(f"    有效带宽: {effective_bandwidth_GBs:.3f} GB/s")
print(f"(2) 总耗时: {total_transfer_time_ns:.0f} ns")
print(f"    CPU等待周期数: {cpu_wait_cycles:.0f} 个")
print(f"(3) 有效执行时间占比: {effective_ratio_percent:.2f}%（或 {frac.numerator}/{frac.denominator}）")
print("=" * 70)
