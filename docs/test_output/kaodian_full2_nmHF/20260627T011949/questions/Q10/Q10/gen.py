# -*- coding: utf-8 -*-
"""
指令流水线吞吐率计算 —— 建模码
5 级不等时流水线，N=50 条指令，求吞吐率 TP（单位 ×10^8 条/秒）。
"""

# ============ 参数 ============
delays = [3, 2, 5, 2, 3]   # S1..S5 各段延迟 (ns)
k = len(delays)             # 流水线段数 = 5
N = 50                      # 指令条数
clock = 1                   # 时钟周期 (ns)，各段延迟为整数个时钟周期

# ============ 场景规则中的关键量 ============
sum_dt = sum(delays)                  # ΣΔtᵢ = 15 ns
dt_max = max(delays)                  # Δt_max = 5 ns（瓶颈段 S3）
avg_dt = sum_dt / k                   # 平均延迟 = 3.0 ns

# ============ 正确路径：A ============
# 场景规则1: T = ΣΔtᵢ + (N-1) × Δt_max
T_correct = sum_dt + (N - 1) * dt_max   # 总执行时间 (ns)
# 场景规则2: TP = N / T
TP_correct_raw = N / T_correct          # 单位: 条/ns = 10^9 条/s
TP_correct_1e8 = TP_correct_raw * 10    # 换算到 ×10^8 条/s

# ============ 错误路径 B：加速比混用 ============
# 场景规则3: S = N × ΣΔtᵢ / T （把 S 数值误当作 TP）
S_speedup = N * sum_dt / T_correct      # 加速比（无量纲）
S_as_TP_1e8 = S_speedup * 10            # 误当 TP，换算到 ×10^8 单位

# ============ 错误路径 C：取算术平均延迟 ============
# 场景规则7-C: T_avg = ΣΔtᵢ + (N-1) × avg
T_avg_path = sum_dt + (N - 1) * avg_dt
TP_C_raw = N / T_avg_path               # 用平均延迟算出的"吞吐率"
TP_C_1e8 = TP_C_raw * 10

# ============ 错误路径 D：遗漏首条指令填充时间 ============
# 场景规则7-D: T_missing = N × Δt_max （遗漏 ΣΔtᵢ）
T_missing = N * dt_max
TP_D_raw = N / T_missing
TP_D_1e8 = TP_D_raw * 10

# ============ 场景规则 assert（打到特征，禁恒真）============
# 规则4: 瓶颈段唯一性 —— Δt_max 严格大于其余各段
non_bottleneck = [d for d in delays if d != dt_max]
assert all(d < dt_max for d in non_bottleneck), "瓶颈段不唯一，取max与取avg可能重合"
assert len([d for d in delays if d == dt_max]) == 1, "存在多个瓶颈段"

# 规则5: 四选项互异（×10^8 单位下四值不同）
vals_1e8 = [TP_correct_1e8, S_as_TP_1e8, TP_C_1e8, TP_D_1e8]
assert len(set(vals_1e8)) == 4, f"选项值有重复: {vals_1e8}"

# ============ 底部：完整数据流 ============
print("=" * 60)
print("PARAMS:")
print(f"  delays  = {delays} (ns)")
print(f"  k       = {k}")
print(f"  N       = {N}")
print(f"  clock   = {clock} ns")
print()
print("PROCESS（场景规则关键量）:")
print(f"  ΣΔtᵢ    = {sum_dt} ns")
print(f"  Δt_max  = {dt_max} ns  (瓶颈段 S3)")
print(f"  avg     = {avg_dt} ns")
print(f"  T_correct = ΣΔtᵢ + (N-1)×Δt_max = {sum_dt} + {N-1}×{dt_max} = {T_correct} ns")
print(f"  T_avg     = ΣΔtᵢ + (N-1)×avg    = {sum_dt} + {N-1}×{avg_dt} = {T_avg_path} ns")
print(f"  T_missing = N×Δt_max              = {N}×{dt_max} = {T_missing} ns")
print(f"  S (加速比) = N×ΣΔtᵢ / T = {N}×{sum_dt}/{T_correct} = {S_speedup}")
print()
print("RESULT（×10^8 条/秒）:")
print(f"  A (正确 TP)         = N/T = {N}/{T_correct} = {TP_correct_raw:.6f} 条/ns = {TP_correct_1e8:.4f} ×10^8 条/s")
print(f"  B (加速比误当TP)    = S×10 = {S_as_TP_1e8:.4f} ×10^8")
print(f"  C (取平均延迟)      = N/T_avg = {TP_C_raw:.6f} 条/ns = {TP_C_1e8:.4f} ×10^8 条/s")
print(f"  D (遗漏填充时间)    = N/(N×Δt_max) = {TP_D_raw:.6f} 条/ns = {TP_D_1e8:.4f} ×10^8 条/s")
print()
print("OPTION_CHECK:")
print(f"  OPTION_A: 正确值={TP_correct_1e8:.4f}, 实际值={TP_correct_1e8:.4f}, 改错方式=无（正确选项）")
print(f"  OPTION_B: 正确值={TP_correct_1e8:.4f}, 实际值={S_as_TP_1e8:.4f},   改错方式=加速比S误当TP")
print(f"  OPTION_C: 正确值={TP_correct_1e8:.4f}, 实际值={TP_C_1e8:.4f},     改错方式=取平均延迟替代最大延迟")
print(f"  OPTION_D: 正确值={TP_correct_1e8:.4f}, 实际值={TP_D_1e8:.4f},     改错方式=遗漏首条指令填充时间")
print()
print("RULE_CHECK（审核对照场景规则）:")
print(f"  规则1 T = ΣΔtᵢ+(N-1)×Δt_max = {sum_dt}+{N-1}×{dt_max} = {T_correct} ✓")
print(f"  规则2 TP = N/T = {N}/{T_correct} = {TP_correct_raw:.6f} 条/ns ✓")
print(f"  规则3 S = N×ΣΔtᵢ/T = {N}×{sum_dt}/{T_correct} = {S_speedup:.6f} ✓")
print(f"  规则4 瓶颈段唯一: max={dt_max}, 其余={non_bottleneck} ✓")
print(f"  规则5 四选项互异: {sorted(set(vals_1e8))} 共{len(set(vals_1e8))}个不同值 ✓")
print("=" * 60)
