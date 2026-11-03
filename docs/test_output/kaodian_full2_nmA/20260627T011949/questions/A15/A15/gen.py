# -*- coding: utf-8 -*-
"""
流水线吞吐率与加速比计算模型
题干：5 段流水线，各段 3/4/5/4/3 ns，连续执行 60 条指令。
建模 = 把题干公式逐句翻译成代码，底部 print 完整数据流 + assert 场景规则。
"""

# =================== 注入参数（来自题干） ===================
stages = [3, 4, 5, 4, 3]   # S1..S5 各段执行时间 (ns)
n = 60                     # 连续执行的指令条数
k = len(stages)            # 功能段数 = 5

# 瓶颈段拆分参数（第3题）
split_index = 2            # S3 是第 3 段（下标 2），值为 5 ns
S3a, S3b = 3, 2            # 拆分为 S3a=3ns, S3b=2ns

# =================== 第（1）题：流水线总执行时间 + 吞吐率 ===================
# 翻译：时钟周期 Δt = max(各段执行时间)
delta_t = max(stages)

# 翻译：流水线总执行时间 T_pipeline = (k + n − 1) × Δt
T_pipeline = (k + n - 1) * delta_t

# 翻译：吞吐率 TP = n / T_pipeline
TP = n / T_pipeline

# =================== 第（2）题：加速比 ===================
# 翻译：顺序执行总时间 T_sequential = (Σtᵢ) × n
sum_stages = sum(stages)
T_sequential = sum_stages * n

# 翻译：加速比 S = T_sequential / T_pipeline
S = T_sequential / T_pipeline

# =================== 第（3）题：瓶颈段拆分后重算 ===================
# 翻译：将 S3(split_index) 拆分为 S3a + S3b，新段列表
stages_new = stages[:split_index] + [S3a, S3b] + stages[split_index+1:]
k_new = len(stages_new)          # 拆分后段数 k' = k + 1
delta_t_new = max(stages_new)    # 拆分后新时钟周期 Δt' = max(所有新段)
T_pipeline_new = (k_new + n - 1) * delta_t_new   # 拆分后流水线总执行时间
TP_new = n / T_pipeline_new      # 拆分后吞吐率 TP'

# 拆分前后吞吐率变化
TP_ratio = TP_new / TP           # TP'/TP

# =================== 场景规则 assert（7 条，逐一检验） ===================
# 规则1：时钟周期 = max(各段)
assert delta_t == max(stages), f"规则1违反: Δt={delta_t} ≠ max={max(stages)}"

# 规则2：流水线总时间 = (k + n − 1) × Δt
assert T_pipeline == (k + n - 1) * delta_t, f"规则2违反: 流水线总时间公式不符"

# 规则3：顺序执行总时间 = (Σtᵢ) × n
assert T_sequential == sum(stages) * n, f"规则3违反: 顺序执行总时间公式不符"

# 规则4：加速比 S > 1（流水线应快于顺序执行）
assert S > 1, f"规则4违反: S={S} ≤ 1，流水线未加速"

# 规则5：吞吐率 TP = n / T_pipeline
assert abs(TP - n / T_pipeline) < 1e-12, f"规则5违反: 吞吐率公式不符"

# 规则6：拆分后段数 k'=k+1；新各段之和守恒；新时钟周期 ≤ 原次大段(4ns)
original_second_max = sorted(stages)[-2]  # 原次大段时间 = 4
assert k_new == k + 1, f"规则6违反: k'={k_new} ≠ k+1={k+1}"
assert S3a + S3b == stages[split_index], f"规则6违反: 拆分守恒 {S3a}+{S3b} ≠ {stages[split_index]}"
assert delta_t_new <= original_second_max, \
    f"规则6违反: Δt'={delta_t_new} > 原次大段{original_second_max}，瓶颈未消除"

# 规则7：拆分后吞吐率提升 TP' > TP
assert TP_new > TP, f"规则7违反: TP'={TP_new} ≤ TP={TP}，拆分未提升吞吐率"

# =================== 底部：打印完整数据流 ===================
print("=" * 60)
print("PARAMS:")
print(f"  各段执行时间 stages = {stages} (ns)")
print(f"  功能段数 k = {k}")
print(f"  指令条数 n = {n}")
print(f"  拆分参数: S3(index={split_index}, {stages[split_index]}ns) → S3a={S3a}ns, S3b={S3b}ns")
print()

print("=" * 60)
print("PROCESS（第1题）:")
print(f"  时钟周期 Δt = max({stages}) = {delta_t} ns")
print(f"  流水线总执行时间 T_pipeline = (k + n − 1) × Δt = ({k} + {n} − 1) × {delta_t} = {T_pipeline} ns")
print(f"  吞吐率 TP = n / T_pipeline = {n} / {T_pipeline} = {TP} (条/ns)")
print(f"    ≈ {TP:.6f} 条/ns ≈ {TP*1000:.4f} ×10⁻³ 条/ns")
print()

print("=" * 60)
print("PROCESS（第2题）:")
print(f"  各段之和 Σtᵢ = {' + '.join(str(s) for s in stages)} = {sum_stages} ns")
print(f"  顺序执行总时间 T_sequential = Σtᵢ × n = {sum_stages} × {n} = {T_sequential} ns")
print(f"  加速比 S = T_sequential / T_pipeline = {T_sequential} / {T_pipeline} = {S}")
print(f"    = {S:.6f}")
print()

print("=" * 60)
print("PROCESS（第3题）:")
print(f"  拆分后各段 stages_new = {stages_new}")
print(f"  拆分后段数 k' = {k_new}")
print(f"  拆分后时钟周期 Δt' = max({stages_new}) = {delta_t_new} ns")
print(f"  拆分后流水线总执行时间 T_pipeline' = (k' + n − 1) × Δt' = ({k_new} + {n} − 1) × {delta_t_new} = {T_pipeline_new} ns")
print(f"  拆分后吞吐率 TP' = n / T_pipeline' = {n} / {T_pipeline_new} = {TP_new} (条/ns)")
print(f"    ≈ {TP_new:.6f} 条/ns")
print(f"  原吞吐率 TP = {TP:.6f} 条/ns")
print(f"  吞吐率变化 TP'/TP = {TP_ratio:.6f}（提升 {(TP_ratio-1)*100:.2f}%）")
print(f"  原次大段时间 = {original_second_max} ns, 拆分后 Δt'={delta_t_new} ≤ {original_second_max} ✓")
print()

print("=" * 60)
print("RESULT:")
print(f"  第（1）题: T_pipeline = {T_pipeline} ns, TP = {TP} 条/ns ({TP:.6f})")
print(f"  第（2）题: S = {S} ({S:.6f})")
print(f"  第（3）题: TP' = {TP_new} 条/ns ({TP_new:.6f}), TP' > TP = {TP_new > TP}")
print()

print("=" * 60)
print("RULE_CHECK (场景规则逐条验证):")
print(f"  规则1: Δt = {delta_t} = max({stages}) ✓")
print(f"  规则2: T_pipeline = {T_pipeline} = ({k}+{n}-1)×{delta_t} = {(k+n-1)*delta_t} ✓")
print(f"  规则3: T_sequential = {T_sequential} = {sum_stages}×{n} = {sum_stages*n} ✓")
print(f"  规则4: S = {S:.6f} > 1 ✓")
print(f"  规则5: TP = {TP} = {n}/{T_pipeline} ✓")
print(f"  规则6: k'={k_new}=k+1={k+1}✓, S3a+S3b={S3a+S3b}=S3={stages[split_index]}✓, Δt'={delta_t_new}≤{original_second_max}✓")
print(f"  规则7: TP'={TP_new:.6f} > TP={TP:.6f} ✓")
print("  全部 7 条场景规则通过。")
