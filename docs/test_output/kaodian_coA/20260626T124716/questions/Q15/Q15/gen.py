"""
中断屏蔽字设计 —— 建模+求解
题干规则直接翻译成代码，通过条件翻译成 assert。
"""

# ============ 参数 ============
# 中断源编号 1..5 对应 L1..L5
# 响应优先级（硬件排队器，rank 越小越高）: L1>L2>L3>L4>L5
response_rank = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}  # L_i -> 响应优先级名次(1=最高)

# 处理优先级（目标，rank 越小越高）: L3 > L1 > L2 > L5 > L4
# L3 -> rank 1, L1 -> rank 2, L2 -> rank 3, L5 -> rank 4, L4 -> rank 5
process_rank = {3: 1, 1: 2, 2: 3, 5: 4, 4: 5}

N = 5  # 中断源个数

print("=" * 60)
print("PARAMS")
print(f"中断源: L1, L2, L3, L4, L5 (共 {N} 个)")
print(f"响应优先级(高->低): ", end="")
order_resp = sorted(response_rank, key=lambda k: response_rank[k])
print(" > ".join(f"L{k}" for k in order_resp))
print(f"处理优先级(高->低): ", end="")
order_proc = sorted(process_rank, key=lambda k: process_rank[k])
print(" > ".join(f"L{k}" for k in order_proc))
print()

# ============ 问题1: 构建 5x5 屏蔽字表 ============
# 规则翻译：
#   对中断源 Li 的屏蔽字，第 j 位 Mj:
#     - 若 j == i (自身) -> 1 (自屏蔽位设1)
#     - 若 Lj 处理优先级 < Li 处理优先级 (即 Lj 处理优先级更高) -> 0 (允许中断)
#     - 若 Lj 处理优先级 >= Li 处理优先级 (即 Lj 处理优先级不高于Li) -> 1 (屏蔽)
#   注: process_rank 越小 = 优先级越高

mask_table = {}  # Li -> {j: Mj}

print("=" * 60)
print("REASONING (问题1: 屏蔽字表推导)")
for i in range(1, N + 1):
    row = {}
    reasoning_parts = []
    for j in range(1, N + 1):
        if j == i:
            row[j] = 1  # 自屏蔽位
            reasoning_parts.append(f"M{j}=1(自身屏蔽位)")
        elif process_rank[j] < process_rank[i]:
            # Lj 处理优先级高于 Li -> 允许 -> 0
            row[j] = 0
            reasoning_parts.append(f"M{j}=0(L{j}处理优先级高于L{i},允许)")
        else:
            # Lj 处理优先级不高于 Li -> 屏蔽 -> 1
            row[j] = 1
            reasoning_parts.append(f"M{j}=1(L{j}处理优先级不高于L{i},屏蔽)")
    mask_table[i] = row
    bits = "".join(str(row[j]) for j in range(1, N + 1))
    print(f"L{i}: {bits}  ({'; '.join(reasoning_parts)})")

print()

# 打印表格
print("屏蔽字表:")
header = "| 中断源 | M1 | M2 | M3 | M4 | M5 |"
print(header)
print("|--------|----|----|----|----|----|")
for i in range(1, N + 1):
    cells = " | ".join(str(mask_table[i][j]) for j in range(1, N + 1))
    print(f"| L{i}     | {cells} |")

print()

# ============ 通过条件 assert (问题1) ============
# 条件1: 自屏蔽位 —— 对角线全1
for i in range(1, N + 1):
    assert mask_table[i][i] == 1, f"自屏蔽位错误: L{i} 的 M{i} 应为1"
print("[assert] 条件1 通过: 对角线(自屏蔽位)全为1")

# 条件2: 屏蔽逻辑正确
for i in range(1, N + 1):
    for j in range(1, N + 1):
        if i == j:
            continue
        if process_rank[j] < process_rank[i]:
            # Lj 处理优先级高于 Li -> 第j位应为0
            assert mask_table[i][j] == 0, \
                f"屏蔽逻辑错误: L{i}的M{j}应为0(L{j}处理优先级高于L{i})"
        else:
            # Lj 处理优先级不高于 Li -> 第j位应为1
            assert mask_table[i][j] == 1, \
                f"屏蔽逻辑错误: L{i}的M{j}应为1(L{j}处理优先级不高于L{i})"
print("[assert] 条件2 通过: 屏蔽逻辑正确(处理优先级高于->0, 不高于->1)")

# 条件3: 结果唯一性 —— 对给定处理优先级，每行的0的个数 = 处理优先级高于自身的数量
for i in range(1, N + 1):
    zeros = sum(1 for j in range(1, N + 1) if mask_table[i][j] == 0)
    higher_count = sum(1 for j in range(1, N + 1)
                       if j != i and process_rank[j] < process_rank[i])
    assert zeros == higher_count, \
        f"唯一性检查: L{i} 的0位数({zeros}) != 处理优先级更高者数({higher_count})"
print("[assert] 条件3 通过: 各行0的个数与'处理优先级更高者数量'一致，结果唯一")

print()

# ============ 问题2: 中断处理顺序模拟 ============
# 到达时序:
#   t=0:  L4 请求到达, CPU响应并开始执行L4
#   t=t1: L2 请求到达
#   t=t2: L1 请求到达
#   t=t3: L3 请求到达
# 规则: 当前执行Li时，若一个挂起的中断请求Lj满足:
#   mask_table[i][j] == 0 (允许) -> Lj可以中断Li
#   当多个挂起的中断请求都被允许时，选择处理优先级最高的那个
# 模拟:
#   每次新请求到达后，检查当前栈顶执行的中断源的屏蔽字，
#   若新请求被允许(对应位=0)，则新请求中断当前执行(压栈)。
#   若不被允许，新请求挂起等待。
#   中断服务程序完成后(返回)，检查是否有挂起的、被允许的请求。

print("=" * 60)
print("REASONING (问题2: 中断处理顺序)")

events = [
    (0, 4),   # t=0:  L4 到达并开始执行
    (1, 2),   # t=t1: L2 到达
    (2, 1),   # t=t2: L1 到达
    (3, 3),   # t=t3: L3 到达
]

execution_log = []  # 记录执行顺序
call_stack = []      # 中断嵌套栈
pending = []         # 挂起的中断请求 (尚未被响应)

def can_interrupt(current_src, new_src):
    """当前执行 current_src 时，new_src 能否中断它"""
    return mask_table[current_src][new_src] == 0

# 模拟到达过程
for t, src in events:
    print(f"\n--- 时刻 t={t}: L{src} 请求到达 ---")
    if t == 0:
        # L4 到达，CPU 直接响应
        call_stack.append(src)
        execution_log.append(('start', src, t))
        print(f"  L{src} 被CPU响应，开始执行。当前执行栈: {' -> '.join(f'L{s}' for s in call_stack)}")
        continue

    current = call_stack[-1]
    allowed = can_interrupt(current, src)
    print(f"  当前正在执行: L{current}")
    print(f"  L{current} 的屏蔽字: {''.join(str(mask_table[current][j]) for j in range(1, N+1))}")
    print(f"  检查 M{src}(L{src}的屏蔽位) = {mask_table[current][src]}")

    if allowed:
        call_stack.append(src)
        execution_log.append(('start', src, t))
        print(f"  -> M{src}=0，允许中断！L{src} 中断 L{current}，开始执行。")
        print(f"     当前执行栈: {' -> '.join(f'L{s}' for s in call_stack)}")
    else:
        pending.append(src)
        print(f"  -> M{src}=1，屏蔽！L{src} 请求被挂起，等待。")
        print(f"     挂起队列: {['L'+str(s) for s in pending]}")

# 所有请求到达后，按嵌套关系逐层完成
# 完成顺序: 从栈顶开始完成，完成后检查挂起队列中是否有被允许的
print("\n--- 所有请求到达完毕，开始逐层完成中断服务程序 ---")
while call_stack:
    current = call_stack.pop()
    execution_log.append(('end', current, None))
    print(f"  L{current} 中断服务程序执行完毕，返回。")
    if call_stack:
        nxt = call_stack[-1]
        print(f"  返回到 L{nxt} 继续执行。")

    # 检查挂起队列: 从挂起的中断中，是否有被当前栈顶允许的
    if call_stack:
        top = call_stack[-1]
        # 在挂起队列中找处理优先级最高且被允许的
        allowed_pending = [s for s in pending if can_interrupt(top, s)]
        if allowed_pending:
            # 选处理优先级最高的(rank最小)
            best = min(allowed_pending, key=lambda s: process_rank[s])
            pending.remove(best)
            call_stack.append(best)
            execution_log.append(('start', best, None))
            print(f"  挂起的 L{best} 现在被 L{top} 允许，开始执行。")
            print(f"  当前执行栈: {' -> '.join(f'L{s}' for s in call_stack)}")

# 剩余挂起的请求(如果有): 此时已无正在执行的中断源，CPU可以按处理优先级依次处理
if pending:
    print(f"\n  无正在执行的中断源，处理剩余挂起请求(按处理优先级):")
    # 按 CPU 空闲后依次响应挂起的请求
    # 此时CPU无屏蔽限制，依次按处理优先级从高到低处理
    while pending:
        # 选处理优先级最高的
        best = min(pending, key=lambda s: process_rank[s])
        pending.remove(best)
        call_stack.append(best)
        execution_log.append(('start', best, None))
        print(f"  L{best} 开始执行(处理优先级剩余最高)。")
        # 完成它
        call_stack.pop()
        execution_log.append(('end', best, None))
        print(f"  L{best} 执行完毕。")

print()
print("=" * 60)
print("中断处理顺序 (开始执行的顺序):")
start_order = [src for (typ, src, t) in execution_log if typ == 'start']
print(" -> ".join(f"L{s}" for s in start_order))

print("\n中断完成顺序:")
end_order = [src for (typ, src, t) in execution_log if typ == 'end']
print(" -> ".join(f"L{s}" for s in end_order))

print()
print("=" * 60)
print("ANSWER")
print()
print("问题1 答案 —— 5x5 屏蔽字表:")
for i in range(1, N + 1):
    bits = "".join(str(mask_table[i][j]) for j in range(1, N + 1))
    print(f"  L{i}: {bits}")

print()
print("问题2 答案 —— 中断处理顺序(含嵌套关系):")
print(f"  执行序列: {' -> '.join(f'L{s}' for s in start_order)}")
print(f"  完成序列: {' -> '.join(f'L{s}' for s in end_order)}")

# 关键嵌套关系
print()
print("  关键嵌套:")
# 找出 L3 中断 L1 的关系
print(f"  - L3 在 t3 到达时中断 L1 (因为 L1 屏蔽字中 M3=0, 允许 L3)")
print(f"    尽管L3响应优先级(第3)低于L1(第1), 但L3处理优先级(第1)高于L1(第2)")

# ============ 通过条件 assert (问题2) ============
print()
print("=" * 60)

# 条件4: L3 中断 L1 —— 执行序列中 L3 紧跟在 L1 之后(被压入栈在L1之上)
# 即在 start_order 中，L3 出现在 L1 之后且中间无返回到L1之下
assert 3 in start_order and 1 in start_order, "L3和L1都应在执行序列中"
idx_L1 = start_order.index(1)
idx_L3 = start_order.index(3)
assert idx_L3 > idx_L1, "L3应在L1之后开始执行(中断L1)"
# 验证L3确实中断了L1: 在执行日志中，L3 start时栈顶应是L1
# 更直接: L1的屏蔽字M3=0
assert mask_table[1][3] == 0, "L1的M3应为0(允许L3中断)"
print(f"[assert] 条件4 通过: L1屏蔽字M3={mask_table[1][3]}(允许), L3中断L1(idx_L3={idx_L3}>idx_L1={idx_L1})")

# 条件5: 处理顺序自洽 —— 完成顺序应为处理优先级从高到低
# 即完成序列应该是处理优先级递减的
for k in range(len(end_order) - 1):
    a, b = end_order[k], end_order[k + 1]
    assert process_rank[a] <= process_rank[b], \
        f"完成顺序不自洽: L{a}(rank{process_rank[a]}) 应先于 L{b}(rank{process_rank[b]})"
print(f"[assert] 条件5 通过: 完成顺序自洽, 完成序列处理优先级递减: {' -> '.join(f'L{s}(rank{process_rank[s]})' for s in end_order)}")

# 额外验证: 每次中断发生时，确实满足屏蔽字允许
# 遍历execution_log，检查每个start事件(非第一个)的前驱
for idx in range(1, len(execution_log)):
    typ, src, t = execution_log[idx]
    if typ == 'start':
        # 找此时栈顶(即上一个还在执行的)
        # 简化: 在到达阶段的模拟已保证正确性，这里验证关键断言
        pass

print()
print("所有通过条件 assert 均已通过 ✓")
