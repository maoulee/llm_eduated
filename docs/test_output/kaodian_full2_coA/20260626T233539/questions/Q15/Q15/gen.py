# -*- coding: utf-8 -*-
"""
中断屏蔽字设计（综合题，8分）
建模：根据处理优先级推导 5×5 屏蔽字矩阵 + 子问题2 嵌套分析。
"""

RESP_PRIORITY = ['L0', 'L1', 'L2', 'L3', 'L4']           # 响应优先级（硬件排队）
PROC_PRIORITY = ['L0', 'L3', 'L1', 'L4', 'L2']            # 处理优先级（屏蔽字决定）高→低
SOURCES = ['L0', 'L1', 'L2', 'L3', 'L4']

def proc_rank(src):
    return PROC_PRIORITY.index(src)

def build_mask_matrix():
    matrix = {}
    for cur in SOURCES:
        row = {}
        for tgt in SOURCES:
            # R2: 处理优先级(Li) >= 处理优先级(Lj) 即 proc_rank(cur) <= proc_rank(tgt) → 位=1
            if proc_rank(cur) <= proc_rank(tgt):
                row[tgt] = 1
            else:
                row[tgt] = 0
        matrix[cur] = row
    return matrix

def can_interrupt(cur_serving, intruder):
    """能否打断 = intruder 处理优先级严格高于 cur_serving。
       与 cur_serving 屏蔽字中第 intruder 位一致：位=0 允许打断，位=1 屏蔽。"""
    maskbit = matrix[cur_serving][intruder]
    by_rank = 1 if proc_rank(intruder) < proc_rank(cur_serving) else 0
    assert maskbit == (0 if by_rank == 1 else 1)
    return by_rank == 1

# ============ 子问题1：构建屏蔽字矩阵 ============
matrix = build_mask_matrix()

print("=" * 60)
print("PARAMS:")
print("  SOURCES:", SOURCES)
print("  RESP_PRIORITY:", RESP_PRIORITY)
print("  PROC_PRIORITY:", PROC_PRIORITY)
print()

print("PROCESS — 子问题1: 屏蔽字矩阵（逐行按处理优先级推导）")
print("  屏蔽规则: 处理优先级>=自身 → 位=1; <自身 → 位=0")
print()
print("  中断源 | L0  L1  L2  L3  L4")
print("  ------+--------------------")
for cur in SOURCES:
    bits = [matrix[cur][t] for t in SOURCES]
    print(f"  {cur:5s} |  {'   '.join(str(b) for b in bits)}")

print()
ones_count = {cur: sum(matrix[cur][t] for t in SOURCES) for cur in SOURCES}
print("PROCESS — 各行屏蔽字中 '1' 的个数:")
for cur in SOURCES:
    # R3: 优先级最高(rank=0)屏蔽全部5个，最低(rank=4)屏蔽1个(仅自身)
    #     优先级<=自身的中断源个数 = 5 - rank
    print(f"  {cur}: ones={ones_count[cur]}, rank={proc_rank(cur)} "
          f"(处理优先级排名, 0=最高), expect={5 - proc_rank(cur)}")

# ============ 场景规则断言 ============

# R1: 对角线自屏蔽位=1
for cur in SOURCES:
    assert matrix[cur][cur] == 1, f"R1 FAIL: {cur} 对角线位不为1"

# R2: 处理优先级一致性 — proc_priority(cur) >= proc_priority(tgt) 即 proc_rank(cur) <= proc_rank(tgt) → 位=1
for cur in SOURCES:
    for tgt in SOURCES:
        if proc_rank(cur) <= proc_rank(tgt):
            assert matrix[cur][tgt] == 1, f"R2 FAIL: {cur}->{tgt} 期望1"
        else:
            assert matrix[cur][tgt] == 0, f"R2 FAIL: {cur}->{tgt} 期望0"

# R3: ones = 处理优先级<=自身的中断源个数（含自身）= 5 - rank（rank从0=最高开始）
for cur in SOURCES:
    assert ones_count[cur] == 5 - proc_rank(cur), f"R3 FAIL: {cur}"

print()
print("RULE_CHECK: R1(自屏蔽位) / R2(优先级一致性) / R3(1的个数) 全部通过")

# ============ 子问题2：嵌套分析 ============
print()
print("=" * 60)
print("PROCESS — 子问题2: 中断时序分析")
print("  t1: L1 发出请求")
print("  t2: L3 发出请求（L1 正在被服务）")
print("  t3: L2 发出请求（L3 正在被服务）")
print()

# (a) t2: L3 能否打断 L1
a_intrusion = can_interrupt('L1', 'L3')
L1_mask_L3 = matrix['L1']['L3']
print(f"(a) t2: L1 屏蔽字第 L3 位 = {L1_mask_L3}")
print(f"    L3 处理优先级排名={proc_rank('L3')} vs L1 排名={proc_rank('L1')}")
print(f"    => L3 {'能' if a_intrusion else '不能'}打断 L1")

# (b) t3: L2 能否打断 L3
b_intrusion = can_interrupt('L3', 'L2')
L3_mask_L2 = matrix['L3']['L2']
print(f"(b) t3: L3 屏蔽字第 L2 位 = {L3_mask_L2}")
print(f"    L2 处理优先级排名={proc_rank('L2')} vs L3 排名={proc_rank('L3')}")
print(f"    => L2 {'能' if b_intrusion else '不能'}打断 L3")

print()
# (c) 服务开始顺序与完成顺序
print("(c) 服务开始顺序:")
print("    t1: L1 开始被服务")
print("    t2: L3 处理优先级高于 L1 → L3 打断 L1，L3 开始服务")
print("    t3: L2 处理优先级低于 L3 → L2 被屏蔽，不能打断 L3，等待")
print("    => 服务开始顺序: L1 → L3")
print()
print("    服务完成顺序（后开始先完成，按嵌套栈）:")
print("    L3 先完成返回 → CPU 回到 L1（L1 屏蔽字第 L2 位决定 L2 是否现在打断）")
L1_mask_L2 = matrix['L1']['L2']
print(f"    L1 屏蔽字第 L2 位 = {L1_mask_L2} "
      f"(L2 处理优先级排名={proc_rank('L2')} vs L1 排名={proc_rank('L1')})")
l2_beats_l1 = can_interrupt('L1', 'L2')
print(f"    L2 处理优先级 {'高于' if l2_beats_l1 else '低于'} L1 → "
      f"L2 {'能' if l2_beats_l1 else '不能'}打断 L1")
if l2_beats_l1:
    print("    => L3 完成 → L2 开始 → L2 完成 → L1 完成")
    finish_order = ['L3', 'L2', 'L1']
else:
    print("    => L3 完成 → 回到 L1，L2 继续被屏蔽 → L1 完成 → 最后 L2")
    finish_order = ['L3', 'L1', 'L2']
print(f"    => 服务完成顺序: {' → '.join(finish_order)}")

# ============ RESULT ============
print()
print("=" * 60)
print("RESULT:")
print("  子问题1 — 屏蔽字矩阵:")
for cur in SOURCES:
    bits = ''.join(str(matrix[cur][t]) for t in SOURCES)
    print(f"    {cur}: {bits}  (L0 L1 L2 L3 L4)")
print()
print(f"  子问题2(a): t2 L3 {'能' if a_intrusion else '不能'}打断 L1（L1屏蔽字第L3位={L1_mask_L3}）")
print(f"  子问题2(b): t3 L2 {'能' if b_intrusion else '不能'}打断 L3（L3屏蔽字第L2位={L3_mask_L2}）")
print(f"  子问题2(c): 服务开始顺序: L1 → L3")
print(f"  子问题2(c): 服务完成顺序: {' → '.join(finish_order)}")
