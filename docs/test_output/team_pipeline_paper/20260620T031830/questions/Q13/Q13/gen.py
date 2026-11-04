"""拉链法散列表构造与 ASL 计算 — gen.py"""

# ==================== PARAMS ====================
m = 11
keys = [11, 22, 33, 1, 12, 2, 13, 24, 3, 14]
n = len(keys)

# ==================== 建模：拉链法散列表 ====================
# 每个桶是一个列表，新元素插入表头（index 0）
table = [[] for _ in range(m)]

def h(key):
    return key % m

# 按顺序插入
for key in keys:
    bucket = h(key)
    table[bucket].insert(0, key)  # 插入表头

# ==================== REASONING：打印构造过程 ====================
print("=== PARAMS ===")
print(f"表长 m = {m}")
print(f"关键字序列: {keys}")
print(f"关键字数 n = {n}")
print(f"装载因子 α = {n}/{m} = {n/m:.4f}")
print()

print("=== 散列表构造过程 ===")
for key in keys:
    bucket = h(key)
    print(f"H({key}) = {key} mod {m} = {bucket} → 插入桶 {bucket} 表头")
print()

print("=== 最终散列表结构 ===")
for i in range(m):
    if table[i]:
        print(f"桶 {i}: {' → '.join(str(k) for k in table[i])}")
    else:
        print(f"桶 {i}: (空)")
print()

# ==================== 计算 ASL_success ====================
# 查找成功：每个关键字的比较次数 = 其在链表中的位置（从1开始）
# 即链表第1个元素比较1次，第2个比较2次，...
total_success = 0
count_by_depth = {}  # 深度 → 关键字数
for i in range(m):
    for depth, key in enumerate(table[i], 1):
        total_success += depth
        count_by_depth[depth] = count_by_depth.get(depth, 0) + 1

asl_success = total_success / n

print("=== ASL_success 计算 ===")
print("各深度关键字数:", count_by_depth)
terms = " + ".join(f"{d} × {c}" for d, c in sorted(count_by_depth.items()))
print(f"总比较次数 = {terms} = {total_success}")
print(f"ASL_success = {total_success}/{n} = {asl_success}")
print()

# ==================== 计算 ASL_fail ====================
# 查找失败：对每个桶，比较次数 = 链表长度 + 1（走到NULL）
# 分母为表长 m
total_fail = 0
fail_details = []
for i in range(m):
    chain_len = len(table[i])
    comparisons = chain_len + 1
    total_fail += comparisons
    fail_details.append((i, chain_len, comparisons))

asl_fail = total_fail / m

print("=== ASL_fail 计算 ===")
for i, chain_len, comps in fail_details:
    print(f"桶 {i}: 链长={chain_len}, 失败比较次数={chain_len}+1={comps}")
print(f"总比较次数 = {total_fail}")
print(f"ASL_fail = {total_fail}/{m} = {total_fail}/{m} ≈ {asl_fail:.4f}")
print()

# ==================== ANSWER ====================
print("=== ANSWER ===")
print(f"ASL_success = {total_success}/{n} = {asl_success}")
print(f"ASL_fail = {total_fail}/{m} ≈ {asl_fail:.4f}")

# ==================== 验证段 ====================
# 验证1: 关键字数
assert n == 10, f"关键字数应为10，实际{n}"

# 验证2: 装载因子 < 1
assert n < m, f"装载因子应<1，实际{n}/{m}"

# 验证3: 冲突桶数在2-5范围内
non_empty_buckets = sum(1 for b in table if len(b) > 0)
conflict_buckets = sum(1 for b in table if len(b) > 1)
assert 2 <= conflict_buckets <= 5, f"冲突桶数应在2-5，实际{conflict_buckets}"

# 验证4: 链表长度分布不均匀（含长度2和3的链）
chain_lengths = [len(b) for b in table if len(b) > 0]
assert 2 in chain_lengths, "应有长度为2的链"
assert 3 in chain_lengths, "应有长度为3的链"

# 验证5: 具体分布 — 2个长度2的链、2个长度3的链、7个空桶
len_counts = {}
for b in table:
    l = len(b)
    len_counts[l] = len_counts.get(l, 0) + 1
assert len_counts.get(0, 0) == 7, f"空桶数应为7，实际{len_counts.get(0, 0)}"
assert len_counts.get(2, 0) == 2, f"长度2的链数应为2，实际{len_counts.get(2, 0)}"
assert len_counts.get(3, 0) == 2, f"长度3的链数应为2，实际{len_counts.get(3, 0)}"

# 验证6: ASL_success = 18/10 = 1.8
assert total_success == 18, f"成功总比较次数应为18，实际{total_success}"
assert asl_success == 1.8, f"ASL_success应为1.8，实际{asl_success}"

# 验证7: ASL_fail = 21/11
assert total_fail == 21, f"失败总比较次数应为21，实际{total_fail}"
assert abs(asl_fail - 21/11) < 1e-9, f"ASL_fail应为21/11，实际{asl_fail}"

# 验证8: 所有关键字互不相同
assert len(set(keys)) == n, "关键字应互不相同"

# 验证9: 所有关键字在0-100范围内
assert all(0 <= k <= 100 for k in keys), "关键字应在0-100范围内"

print("\n=== 所有验证通过 ===")
