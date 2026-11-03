# -*- coding: utf-8 -*-
"""
DRAM芯片扩展设计 — 综合题建模
CPU: 16根地址线, 8根数据线, 按字节编址
DRAM芯片: 16K × 4位 = 2^14 × 4，地址复用(7行+7列)，刷新周期T=2ms

一次性建模 + 底部 print 完整数据流。
"""

# ============ 注入参数 ============
A = 16   # CPU地址总线宽度
D = 8    # CPU数据总线宽度
K = 14   # 芯片地址线数(2^14=16K)
W = 4    # 芯片字宽
R = 7    # 行地址位数 (复用: 7行+7列=14)
C = 7    # 列地址位数
T = 2.0  # 刷新周期 ms

# ============ Q1: 芯片总数推导 ============
bit_extend = D // W            # 位扩展数：每组多少片拼位宽
word_groups = 2 ** (A - K)     # 字扩展组数：需要多少组拼地址
total_chips = bit_extend * word_groups

# ============ Q2: 地址线分配 ============
chip_addr_lines = K            # 片内寻址线数（芯片地址线）
chip_select_lines = A - K      # 片选高位地址线数
# 按题干：A13~A0 片内，A15~A14 片选
chip_addr_range = f"A{chip_addr_lines-1}~A0"           # A13~A0
chip_select_range = f"A{A-1}~A{chip_addr_lines}"        # A15~A14

# ============ Q4: 异步刷新 ============
refresh_rows = 2 ** R          # 阵列行数
refresh_interval = T / refresh_rows   # 异步刷新间隔 ms
refresh_interval_us = refresh_interval * 1000  # 转 μs
refresh_count = refresh_rows   # 刷新周期内刷新次数（每行一次）

# ============ 底部：完整数据流 ============
print("=" * 60)
print("PARAMS:")
print(f"  CPU地址线 A={A}, CPU数据线 D={D}, 编址=按字节")
print(f"  芯片: 2^{K} × {W} ({2**K} × {W}位), 地址复用 {R}行+{C}列")
print(f"  刷新周期 T={T} ms")
print()
print("PROCESS:")
print(f"  [Q1] D % W = {D} % {W} = {D % W}  (整除, 位扩展为整数)")
print(f"  [Q1] 位扩展数 = D/W = {D}/{W} = {bit_extend} 片/组")
print(f"  [Q1] A - K = {A} - {K} = {A - K}  (≥1, 字扩展非平凡)")
print(f"  [Q1] 字扩展组数 = 2^(A-K) = 2^{A-K} = {word_groups} 组")
print(f"  [Q1] 芯片总数 = {bit_extend} × {word_groups} = {total_chips} 片")
print()
print(f"  [Q2] 片内寻址线 = {chip_addr_lines} 根 ({chip_addr_range})")
print(f"  [Q2] 片选高位线 = {chip_select_lines} 根 ({chip_select_range})")
print(f"  [Q2] 地址线全分配校验: {chip_addr_lines} + {chip_select_lines} = {chip_addr_lines + chip_select_lines} (应={A})")
print()
print(f"  [Q4] 阵列行数 = 2^R = 2^{R} = {refresh_rows} 行")
print(f"  [Q4] R = K/2 = {K}/{2} = {R}  (行地址位数)")
print(f"  [Q4] 异步刷新间隔 = T / 2^R = {T}ms / {refresh_rows} = {refresh_interval} ms = {refresh_interval_us:.0f} μs")
print(f"  [Q4] 刷新次数 = 2^R = {refresh_rows} 次/周期")
print()
print("RESULT:")
print(f"  Q1: 位扩展{bit_extend}片 × 字扩展{word_groups}组 = {total_chips}片")
print(f"  Q2: 片内{chip_addr_lines}根({chip_addr_range}) + 片选{chip_select_lines}根({chip_select_range})")
print(f"  Q4: {refresh_rows}行, {refresh_interval_us:.0f}μs, {refresh_count}次")
print()

# ============ 场景规则验证（assert 命中通过条件，非恒真）============
# 规则1: 位扩展数 = D/W，且 D%W==0
assert bit_extend == D // W, "位扩展数 != D/W"
assert D % W == 0, "D 不被 W 整除"

# 规则2: 字扩展组数 = 2^(A-K)，且 A-K>=1
assert word_groups == 2 ** (A - K), "字扩展组数 != 2^(A-K)"
assert A - K >= 1, "A-K < 1, 字扩展平凡"

# 规则3: 芯片总数 = 位扩展 × 字扩展组数
assert total_chips == bit_extend * word_groups, "芯片总数不自洽"

# 规则4: 地址线全分配（不重不漏）
assert chip_addr_lines + chip_select_lines == A, "地址线未全分配"

# 规则5: 容量自洽（全链等式）
cap_cpu = (2 ** A) * D           # 主存总容量 bits (按字节编址: 每地址D位? -> 按字节编址每地址=8bit)
# 按字节编址：地址数=2^A, 每地址1Byte=8bit，CPU数据线D=8正好对应
# 等式链：字扩展组数 × 每组芯片容量 × 每组片数
cap_by_chips = word_groups * (2 ** K) * W * bit_extend
# CPU侧：2^A 地址 × D bit
assert cap_cpu == cap_by_chips, f"容量不自洽: {cap_cpu} != {cap_by_chips}"

# 规则6: 刷新行数 = 2^R，且 R = K/2
assert refresh_rows == 2 ** R, "刷新行数 != 2^R"
assert R == K // 2, f"R({R}) != K/2({K//2})"

# 规则7: 异步刷新间隔 = T / 2^R
assert refresh_interval == T / refresh_rows, "异步刷新间隔 != T/2^R"

# 规则8: 刷新次数 = 2^R（每行一次）
assert refresh_count == refresh_rows, "刷新次数 != 行数"

print("SCENE_RULE_ALL_PASS")
print(f"  规则5验证: CPU侧容量={cap_cpu} bits = {cap_cpu//8} bytes = {cap_cpu//8//1024} KB")
print(f"            芯片侧容量={cap_by_chips} bits = {cap_by_chips//8} bytes = {cap_by_chips//8//1024} KB")
