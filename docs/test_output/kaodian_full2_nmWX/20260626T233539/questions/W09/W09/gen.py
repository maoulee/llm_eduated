# -*- coding: utf-8 -*-
"""
指令流水线性能分析
5段流水线: IF=10, ID=10, EX=20(瓶颈), MEM=10, WB=10
N=200 条独立指令，无冒险
"""

# ============================================================
#  模型：把题干规则 + 场景规则翻译成代码
# ============================================================

def analyze_pipeline(stages, N):
    """
    stages: list[int] 各段时间(ns)
    N: 指令条数
    返回: 包含所有指标的 dict
    """
    k = len(stages)
    T = max(stages)                         # 规则1: 流水线周期 = 瓶颈段时间
    total_time = (k + N - 1) * T            # 规则2: 总执行时间 = (k+N-1)*T
    TP = N / total_time                     # 规则3: 实际吞吐率
    TP_max = 1 / T                          # 规则4: 最大吞吐率
    sum_stages = sum(stages)                # 单条指令顺序时间
    sequential_time = N * sum_stages        # 顺序执行总时间
    S = sequential_time / total_time        # 规则5: 加速比
    drain_time = (k - 1) * T                # 排空(填充)时间
    drain_ratio = drain_time / total_time   # 规则7: 排空占比
    return dict(
        k=k, N=N, stages=list(stages),
        sum_stages=sum_stages,
        T=T, total_time=total_time,
        TP=TP, TP_max=TP_max,
        sequential_time=sequential_time,
        S=S,
        drain_time=drain_time, drain_ratio=drain_ratio,
    )

def analyze_optimized(stages, N, split_index, split_into):
    """
    将 stages[split_index] 拆分为 split_into 个均等子段
    """
    orig = stages[split_index]
    assert orig % split_into == 0, "瓶颈段时间必须能均分"
    sub = orig // split_into
    new_stages = []
    for i, s in enumerate(stages):
        if i == split_index:
            new_stages += [sub] * split_into
        else:
            new_stages.append(s)
    return analyze_pipeline(new_stages, N)


# ============================================================
#  注入参数跑
# ============================================================
stages_5 = [10, 10, 20, 10, 10]   # IF ID EX MEM WB
N = 200

orig = analyze_pipeline(stages_5, N)
# 优化: S3(20ns) 拆成 2 个 10ns 子段 -> 6段全10ns
opt = analyze_optimized(stages_5, N, split_index=2, split_into=2)


# ============================================================
#  通过条件 (场景规则) assert
# ============================================================

# --- 通用约束 (规则1-7) ---
assert orig['T'] == max(stages_5), "规则1: T必须=max(各段时间)"
assert orig['total_time'] == (orig['k'] + N - 1) * orig['T'], "规则2: 总时间=(k+N-1)*T"
assert abs(orig['TP'] - N / orig['total_time']) < 1e-12, "规则3: TP=N/总时间"
assert abs(orig['TP_max'] - 1 / orig['T']) < 1e-12, "规则4: TP_max=1/T"
assert abs(orig['S'] - (N * orig['sum_stages']) / orig['total_time']) < 1e-12, "规则5: S=(N*ΣΔt)/总时间"
assert orig['TP'] <= orig['TP_max'], "规则6: TP<=TP_max"
assert orig['drain_ratio'] < 0.05, "规则7: 排空占比<5%"

# --- 优化后约束 (规则8-11) ---
opt_stages = [10, 10, 10, 10, 10, 10]
assert opt['T'] == 10 and opt['T'] == max(opt_stages), "规则8: 优化后T'=10"
assert opt['k'] == 6, "规则9: 优化后k'=6"
assert opt['total_time'] == (6 + N - 1) * 10, "规则10: 优化后总时间=(6+N-1)*10"
assert opt['TP'] > orig['TP'], "规则11: 优化后TP'>TP"

# --- 交叉验证 (规则12) ---
assert orig['S'] > 1, "规则12a: S>1"
assert orig['S'] < orig['k'], "规则12b: S<k"
assert opt['S'] > 1 and opt['S'] < opt['k'], "规则12: 优化后加速比也满足 1<S<k"

# 排空时间对比
orig_drain = (orig['k'] - 1) * orig['T']
opt_drain = (opt['k'] - 1) * opt['T']

# ============================================================
#  底部：完整数据流 print
# ============================================================
print("=" * 60)
print("【PARAMS】")
print(f"  stages = {stages_5}  (IF ID EX MEM WB)")
print(f"  N = {N}")
print("=" * 60)

print("\n【PROCESS - Q1 原始流水线】")
print(f"  k = {orig['k']}")
print(f"  各段时间 = {orig['stages']} ns")
print(f"  瓶颈段 = EX = 20 ns (= max(各段))")
print(f"  T = max(Δt) = {orig['T']} ns")
print(f"  排空时间 = (k-1)×T = {orig['k']-1}×{orig['T']} = {orig['drain_time']} ns")
print(f"  总执行时间 = (k+N-1)×T = ({orig['k']}+{N}-1)×{orig['T']} = {orig['total_time']} ns")

print("\n【PROCESS - Q2 吞吐率】")
print(f"  TP = N / 总时间 = {N} / {orig['total_time']} = {orig['TP']:.10f} 条/ns")
print(f"     = {orig['TP']*1e9/1e6:.4f} MIPS")
print(f"  TP_max = 1/T = 1/{orig['T']} = {orig['TP_max']:.10f} 条/ns")
print(f"         = {orig['TP_max']*1e9/1e6:.4f} MIPS")
print(f"  TP/TP_max = {orig['TP']/orig['TP_max']:.6f}  (排空占比={orig['drain_ratio']:.6f})")

print("\n【PROCESS - Q3 加速比】")
print(f"  ΣΔt = {orig['sum_stages']} ns (单条指令顺序时间)")
print(f"  顺序执行总时间 = N×ΣΔt = {N}×{orig['sum_stages']} = {orig['sequential_time']} ns")
print(f"  S = 顺序时间/流水线时间 = {orig['sequential_time']}/{orig['total_time']} = {orig['S']:.6f}")

print("\n【PROCESS - Q4 优化后(6段, 全10ns)】")
print(f"  优化后各段 = {opt['stages']} ns")
print(f"  k' = {opt['k']}")
print(f"  T' = max(各段) = {opt['T']} ns")
print(f"  总时间' = (k'+N-1)×T' = ({opt['k']}+{N}-1)×{opt['T']} = {opt['total_time']} ns")
print(f"  TP' = N/总时间' = {N}/{opt['total_time']} = {opt['TP']:.10f} 条/ns")
print(f"       = {opt['TP']*1e9/1e6:.4f} MIPS")
print(f"  排空时间' = (k'-1)×T' = {opt['k']-1}×{opt['T']} = {opt_drain} ns")

print("\n【RESULT 汇总】")
print(f"  原始: T={orig['T']}ns  总时间={orig['total_time']}ns  TP={orig['TP']:.6f}条/ns  TP_max={orig['TP_max']:.6f}条/ns  S={orig['S']:.4f}")
print(f"  优化: T'={opt['T']}ns  总时间'={opt['total_time']}ns  TP'={opt['TP']:.6f}条/ns")

print("\n【规则验证数据流】")
print(f"  规则1  T=max(段): {orig['T']} == {max(stages_5)}  ✓")
print(f"  规则2  总时间=(k+N-1)T: {orig['total_time']} == ({orig['k']}+{N}-1)*{orig['T']}={orig['total_time']}  ✓")
print(f"  规则6  TP<=TP_max: {orig['TP']:.6f} <= {orig['TP_max']:.6f}  ✓")
print(f"  规则7  排空占比<5%: {orig['drain_ratio']:.4%} < 5%  ✓")
print(f"  规则12 S在(1,k): 1 < {orig['S']:.4f} < {orig['k']}  ✓")
print(f"  规则8  T'=10: {opt['T']}  ✓")
print(f"  规则9  k'=6: {opt['k']}  ✓")
print(f"  规则10 总时间'=(6+N-1)*10: {opt['total_time']} == {(6+N-1)*10}  ✓")
print(f"  规则11 TP'>TP: {opt['TP']:.6f} > {orig['TP']:.6f}  ✓")
print(f"  排空对比: 原始排空={orig_drain}ns  优化排空={opt_drain}ns  增量={opt_drain-orig_drain}ns")
print("  所有通过条件 assert 已通过 ✓")
