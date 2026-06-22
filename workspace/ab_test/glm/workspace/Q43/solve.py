"""
Q43 — Cache与流水线性能综合分析
完整的Python求解代码
"""

import math

print("=" * 70)
print("Q43 — Cache与流水线性能综合分析")
print("=" * 70)

# ============================================================
# 基本参数定义
# ============================================================
print("\n" + "=" * 70)
print("基本参数")
print("=" * 70)

# 时钟周期
T_clk_ns = 2  # ns

# 主存参数
main_mem_size_MB = 256  # MB
main_mem_size_B = main_mem_size_MB * 1024 * 1024  # 字节
addr_bits = int(math.log2(main_mem_size_B))
print(f"主存容量: {main_mem_size_MB} MB = {main_mem_size_B} B = 2^{addr_bits} B")
print(f"主存地址位数: {addr_bits} 位")

# Cache 参数 (L1I 和 L1D 结构相同)
cache_total_size_KB = 64  # KB
cache_total_size_B = cache_total_size_KB * 1024  # 字节
block_size_B = 64  # 块大小（行大小）
associativity = 4  # 4路组相联
cache_hit_time_cycles = 1  # Cache命中时间（时钟周期）

print(f"\nCache总容量: {cache_total_size_KB} KB = {cache_total_size_B} B = 2^{int(math.log2(cache_total_size_B))} B")
print(f"块大小: {block_size_B} B = 2^{int(math.log2(block_size_B))} B")
print(f"映射方式: {associativity}路组相联")
print(f"Cache命中时间: {cache_hit_time_cycles} 个时钟周期")

# 总线参数
bus_width_B = 8  # 总线宽度
burst_first_latency = 30  # 首次突发传输延迟（时钟周期）
burst_subsequent_latency = 1  # 后续每次突发传输延迟（时钟周期）

print(f"\n总线宽度: {bus_width_B} B")
print(f"首次突发传输延迟: {burst_first_latency} 个时钟周期")
print(f"后续突发传输延迟: {burst_subsequent_latency} 个时钟周期/次")

# 程序统计参数
icache_hit_rate = 0.95  # 指令Cache命中率
dcache_hit_rate = 0.90  # 数据Cache命中率
total_instructions = 20000  # 总指令数
load_store_ratio = 0.25  # load/store指令占比
base_CPI = 1  # 理想情况下的基准CPI

print(f"\n指令Cache命中率: {icache_hit_rate * 100}%")
print(f"数据Cache命中率: {dcache_hit_rate * 100}%")
print(f"总指令数: {total_instructions}")
print(f"load/store指令占比: {load_store_ratio * 100}%")
print(f"基准CPI: {base_CPI}")

# ============================================================
# 子问题 (1): Cache 主存地址格式推导
# ============================================================
print("\n" + "=" * 70)
print("子问题 (1): Cache 主存地址格式推导")
print("=" * 70)

# Offset 位数: 由块大小决定
offset_bits = int(math.log2(block_size_B))
print(f"\n【推导 Offset 位数】")
print(f"  块大小 = {block_size_B} B = 2^{offset_bits} B")
print(f"  → Offset = {offset_bits} 位")
print(f"  说明: 块内寻址需要 {offset_bits} 位来定位每个字节")

# Index 位数: 由组数决定
# 每组大小 = 块大小 × 相联度
size_per_set_B = block_size_B * associativity
num_sets = cache_total_size_B // size_per_set_B
index_bits = int(math.log2(num_sets))
print(f"\n【推导 Index 位数】")
print(f"  每组大小 = 块大小 × 相联度 = {block_size_B} B × {associativity} = {size_per_set_B} B = 2^{int(math.log2(size_per_set_B))} B")
print(f"  组数 = Cache总容量 / 每组大小 = {cache_total_size_B} / {size_per_set_B} = {num_sets} = 2^{index_bits}")
print(f"  → Index = {index_bits} 位")

# Tag 位数: 地址总位数 - Index - Offset
tag_bits = addr_bits - index_bits - offset_bits
print(f"\n【推导 Tag 位数】")
print(f"  主存地址位数 = log₂({main_mem_size_B}) = {addr_bits} 位")
print(f"  Tag = 地址位数 - Index - Offset = {addr_bits} - {index_bits} - {offset_bits} = {tag_bits} 位")

# 验证
total_check = tag_bits + index_bits + offset_bits
print(f"\n【验证】")
print(f"  Tag({tag_bits}) + Index({index_bits}) + Offset({offset_bits}) = {total_check} 位")
assert total_check == addr_bits, "地址位数验证失败!"
print(f"  {total_check} = {addr_bits} ✓ 验证通过!")

print(f"\n  地址格式:")
print(f"  ┌──────────────┬──────────┬──────────┐")
print(f"  │ Tag({tag_bits}位)  │Index({index_bits}位)│Offset({offset_bits}位)│")
print(f"  └──────────────┴──────────┴──────────┘")

# ============================================================
# 子问题 (2): 缺失损失 (Miss Penalty) 计算
# ============================================================
print("\n" + "=" * 70)
print("子问题 (2): 缺失损失 (Miss Penalty) 计算")
print("=" * 70)

print(f"\n【计算突发传输次数】")
print(f"  Cache块大小 = {block_size_B} B")
print(f"  总线宽度 = {bus_width_B} B")
burst_count = block_size_B // bus_width_B
print(f"  突发传输次数 = ⌈{block_size_B} / {bus_width_B}⌉ = {burst_count} 次")

print(f"\n【计算缺失损失】")
print(f"  缺失损失 = 首次传输延迟 + (突发传输次数 - 1) × 后续传输延迟")
print(f"  缺失损失 = {burst_first_latency} + ({burst_count} - 1) × {burst_subsequent_latency}")
miss_penalty = burst_first_latency + (burst_count - 1) * burst_subsequent_latency
print(f"  缺失损失 = {burst_first_latency} + {burst_count - 1} × {burst_subsequent_latency}")
print(f"  缺失损失 = {burst_first_latency} + {(burst_count - 1) * burst_subsequent_latency}")
print(f"  缺失损失 = {miss_penalty} 个时钟周期")

# ============================================================
# 子问题 (3): AMAT 计算
# ============================================================
print("\n" + "=" * 70)
print("子问题 (3): AMAT 计算 (平均访问时间)")
print("=" * 70)

# AMAT 公式: AMAT = 命中时间 + 缺失率 × 缺失损失
print(f"\n  AMAT 公式: AMAT = 命中时间 + 缺失率 × 缺失损失")

# 指令 Cache AMAT
icache_miss_rate = 1 - icache_hit_rate
print(f"\n【指令 Cache AMAT (AMAT_I)】")
print(f"  指令Cache命中率 = {icache_hit_rate} = {int(icache_hit_rate*100)}%")
print(f"  指令Cache缺失率 = 1 - {icache_hit_rate} = {icache_miss_rate} = {int(icache_miss_rate*100)}%")
print(f"  AMAT_I = {cache_hit_time_cycles} + {icache_miss_rate} × {miss_penalty}")
AMAT_I = cache_hit_time_cycles + icache_miss_rate * miss_penalty
print(f"  AMAT_I = {cache_hit_time_cycles} + {icache_miss_rate * miss_penalty}")
print(f"  AMAT_I = {AMAT_I} 个时钟周期")

# 数据 Cache AMAT
dcache_miss_rate = 1 - dcache_hit_rate
print(f"\n【数据 Cache AMAT (AMAT_D)】")
print(f"  数据Cache命中率 = {dcache_hit_rate} = {int(dcache_hit_rate*100)}%")
print(f"  数据Cache缺失率 = 1 - {dcache_hit_rate} = {dcache_miss_rate} = {int(dcache_miss_rate*100)}%")
print(f"  AMAT_D = {cache_hit_time_cycles} + {dcache_miss_rate} × {miss_penalty}")
AMAT_D = cache_hit_time_cycles + dcache_miss_rate * miss_penalty
print(f"  AMAT_D = {cache_hit_time_cycles} + {dcache_miss_rate * miss_penalty}")
print(f"  AMAT_D = {AMAT_D} 个时钟周期")

# ============================================================
# 子问题 (4): 总执行时间计算
# ============================================================
print("\n" + "=" * 70)
print("子问题 (4): 总执行时间计算")
print("=" * 70)

# ① 指令Cache缺失引起的总阻塞周期数
print(f"\n【① 指令Cache缺失引起的总阻塞周期数】")
print(f"  每条指令都需要一次指令Cache访问（在IF段）")
print(f"  指令总数 = {total_instructions}")
print(f"  指令Cache缺失率 = {icache_miss_rate} = 1/20")
icache_miss_count = int(total_instructions * icache_miss_rate)
print(f"  指令Cache缺失次数 = {total_instructions} × {icache_miss_rate} = {icache_miss_count}")
N_I_stall = icache_miss_count * miss_penalty
print(f"  N_I_stall = 缺失次数 × 缺失损失 = {icache_miss_count} × {miss_penalty} = {N_I_stall} 个周期")

# ② 数据Cache缺失引起的总阻塞周期数
print(f"\n【② 数据Cache缺失引起的总阻塞周期数】")
print(f"  仅load/store指令（占{load_store_ratio*100}%）会访问数据Cache（在MEM段）")
num_load_store = int(total_instructions * load_store_ratio)
print(f"  load/store指令数 = {total_instructions} × {load_store_ratio} = {num_load_store}")
print(f"  数据Cache缺失率 = {dcache_miss_rate} = 1/10")
dcache_miss_count = int(num_load_store * dcache_miss_rate)
print(f"  数据Cache缺失次数 = {num_load_store} × {dcache_miss_rate} = {dcache_miss_count}")
N_D_stall = dcache_miss_count * miss_penalty
print(f"  N_D_stall = 缺失次数 × 缺失损失 = {dcache_miss_count} × {miss_penalty} = {N_D_stall} 个周期")

# ③ 程序执行的总时钟周期数
print(f"\n【③ 程序执行的总时钟周期数】")
base_cycles = total_instructions * base_CPI
print(f"  基准周期数 = 指令总数 × 基准CPI = {total_instructions} × {base_CPI} = {base_cycles}")
N_total = base_cycles + N_I_stall + N_D_stall
print(f"  N_total = 基准周期 + I-stall + D-stall")
print(f"  N_total = {base_cycles} + {N_I_stall} + {N_D_stall}")
print(f"  N_total = {N_total} 个时钟周期")

# ④ 总执行时间
print(f"\n【④ 总执行时间】")
T_total_ns = N_total * T_clk_ns
T_total_us = T_total_ns / 1000
print(f"  T = N_total × T_clk = {N_total} × {T_clk_ns} ns = {T_total_ns} ns")
print(f"  T = {T_total_ns} ns = {T_total_us} μs")

# ============================================================
# 结果汇总
# ============================================================
print("\n" + "=" * 70)
print("最终结果汇总")
print("=" * 70)
print(f"\n  (1) 地址格式: Tag({tag_bits}位) | Index({index_bits}位) | Offset({offset_bits}位)  共{tag_bits+index_bits+offset_bits}位")
print(f"  (2) 缺失损失 (Miss Penalty) = {miss_penalty} 个时钟周期")
print(f"  (3) AMAT_I = {AMAT_I} 个时钟周期")
print(f"      AMAT_D = {AMAT_D} 个时钟周期")
print(f"  (4) 总执行时间 = {T_total_us} μs")
print(f"          = {T_total_ns} ns")
print(f"          = {N_total} 个时钟周期")
