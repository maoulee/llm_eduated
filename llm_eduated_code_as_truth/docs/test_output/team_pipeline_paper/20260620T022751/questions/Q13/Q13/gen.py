"""
散列表拉链法构造与 ASL 计算
H(key) = key mod 13, 表长 m=13, 头插法
"""

# ========== PARAMS ==========
KEYS = [5, 18, 31, 44, 28, 41, 54, 67, 17, 33]
m = 13
n = len(KEYS)

print("=== PARAMS ===")
print(f"关键字序列: {KEYS}")
print(f"表长 m = {m}, 关键字个数 n = {n}")
print(f"散列函数: H(key) = key mod {m}")
print(f"冲突处理: 拉链法（头插法）")

# ========== 构造散列表（拉链法，头插）==========
print("\n=== REASONING: 构造散列表 ===")

# 初始化空表
table = [[] for _ in range(m)]

# 逐个插入（头插法）
for key in KEYS:
    h = key % m
    table[h].insert(0, key)  # 头插
    print(f"H({key}) = {key} mod {m} = {h}  → 插入桶 {h}, 链: {table[h]}")

# 打印完整散列表
print("\n散列表结构:")
for i in range(m):
    if table[i]:
        chain_str = " → ".join(str(k) for k in table[i])
        print(f"  桶 {i}: {chain_str}")
    else:
        print(f"  桶 {i}: (空)")

# ========== 计算 ASL 成功 ==========
print("\n=== REASONING: ASL 成功 ===")

# 对每个关键字，计算查找长度（在链中的位置，1-indexed）
asl_success_num = 0
for key in KEYS:
    h = key % m
    # 在链中找 key 的位置
    for pos, k in enumerate(table[h], 1):
        if k == key:
            asl_success_num += pos
            print(f"查找 {key}: 桶 {h}, 链中位置 {pos}, 比较 {pos} 次")
            break

asl_success = asl_success_num / n
print(f"ASL_success = {asl_success_num}/{n} = {asl_success}")

# ========== 计算 ASL 失败 ==========
print("\n=== REASONING: ASL 失败 ===")

# 拉链法失败 ASL：对每个桶，查找失败时的比较次数 = 该桶链的长度
# ASL_failure = sum(链长) / m
asl_failure_num = 0
for i in range(m):
    chain_len = len(table[i])
    asl_failure_num += chain_len
    print(f"桶 {i}: 链长 {chain_len}, 失败比较 {chain_len} 次")

asl_failure = asl_failure_num / m
print(f"ASL_failure = {asl_failure_num}/{m} = {asl_failure}")

# ========== 最终答案 ==========
print("\n=== ANSWER ===")
print(f"ASL_success = {asl_success_num}/{n}")
print(f"ASL_failure = {asl_failure_num}/{m}")

# ========== 验证（assert）==========
print("\n=== 验证 ===")

# 1. 至少 2 条链长度 >= 2
chains_ge2 = sum(1 for c in table if len(c) >= 2)
assert chains_ge2 >= 2, f"冲突不足: 仅 {chains_ge2} 条链长度>=2"
print(f"✓ 链长度>=2 的数量: {chains_ge2} (>=2)")

# 2. 最长链长度在 [2, 4]
max_chain = max(len(c) for c in table)
assert 2 <= max_chain <= 4, f"最长链长度 {max_chain} 不在 [2,4]"
print(f"✓ 最长链长度: {max_chain} (在 [2,4])")

# 3. 非空链表数量在 [2, 4]
non_empty = sum(1 for c in table if len(c) > 0)
assert 2 <= non_empty <= 4, f"非空链表数 {non_empty} 不在 [2,4]"
print(f"✓ 非空链表数: {non_empty} (在 [2,4])")

# 4. ASL 成功分母为 n
assert asl_success == asl_success_num / n
print(f"✓ ASL_success 分母为 n={n}")

# 5. ASL 失败分母为 m
assert asl_failure == asl_failure_num / m
print(f"✓ ASL_failure 分母为 m={m}")

# 6. 所有关键字都在表中
for key in KEYS:
    h = key % m
    assert key in table[h], f"关键字 {key} 未在桶 {h} 中找到"
print(f"✓ 所有 {n} 个关键字均在表中")

# 7. 表中元素总数 = n
total = sum(len(c) for c in table)
assert total == n, f"表中元素总数 {total} != n={n}"
print(f"✓ 表中元素总数: {total} = n")

print("\n所有验证通过 ✓")
