from fractions import Fraction

def solve(keys, m, insert_method='head'):
    """
    构造散列表并计算ASL
    keys: 关键字序列
    m: 表长
    insert_method: 'head' 头插法, 'tail' 尾插法
    """
    n = len(keys)
    # 初始化散列表（拉链法）
    table = [[] for _ in range(m)]

    # 插入关键字
    for key in keys:
        idx = key % m
        if insert_method == 'head':
            table[idx].insert(0, key)  # 头插
        else:
            table[idx].append(key)  # 尾插

    # 计算 ASL_success
    total_success = 0
    for bucket in table:
        for i, key in enumerate(bucket):
            total_success += (i + 1)  # 第i个元素需要比较i+1次

    asl_success = Fraction(total_success, n)

    # 计算 ASL_fail
    total_fail = 0
    for bucket in table:
        total_fail += len(bucket)

    asl_fail = Fraction(total_fail, m)

    return table, asl_success, asl_fail, total_success, total_fail


# 参数
keys = [19, 32, 45, 58, 71, 20, 33, 46, 21, 34]
m = 13
n = len(keys)

# 正确解法（头插法）
table, asl_success, asl_fail, total_success, total_fail = solve(keys, m, 'head')

print("PARAMS")
print(f"keys = {keys}")
print(f"m = {m}")
print(f"n = {n}")

print("\nREASONING")
print("散列表构造（头插法）：")
for i, bucket in enumerate(table):
    if bucket:
        print(f"桶{i}: {' → '.join(map(str, bucket))}")

print(f"\nASL_success = {total_success}/{n} = {asl_success} = {float(asl_success):.4f}")
print(f"ASL_fail = {total_fail}/{m} = {asl_fail} = {float(asl_fail):.4f}")

# 干扰项设计（替换原尾插法干扰项）
# B: ASL_success 分母误用 m（而非 n）→ 产生不同值
asl_success_B = Fraction(total_success, m)

# C: ASL_fail 分母误用 n（而非 m）→ 产生不同值
asl_fail_C = Fraction(total_fail, n)

# D: 查找次数从0开始计数（错误路径：第k个元素比较k次而非k+1次）
total_success_D = sum(i for bucket in table for i in range(len(bucket)))
asl_success_D = Fraction(total_success_D, n)

print("\n干扰项：")
print(f"B: ASL_success 分母误用m = {asl_success_B} = {float(asl_success_B):.4f}")
print(f"C: ASL_fail 分母误用n = {asl_fail_C} = {float(asl_fail_C):.4f}")
print(f"D: 查找次数从0开始 = {asl_success_D} = {float(asl_success_D):.4f}")

print("\nANSWER")
print(f"ASL_success = {asl_success}")
print(f"ASL_fail = {asl_fail}")

# ========== 验证通过条件 ==========
print("\n验证：")

# 1. 散列表构造正确：10个关键字按 H(key)=key mod 13 分布
for key in keys:
    assert key % m == table[key % m][-1] or key in table[key % m], f"关键字 {key} 未在正确桶中"

# 2. 非空桶数量在合理范围（3-5个）
non_empty = sum(1 for bucket in table if bucket)
print(f"非空桶数量: {non_empty}")
assert 3 <= non_empty <= 5, f"非空桶数量 {non_empty} 不在 3-5 范围内"

# 3. 至少2个桶有≥2个元素
buckets_ge_2 = sum(1 for bucket in table if len(bucket) >= 2)
print(f"链表长度≥2的桶数量: {buckets_ge_2}")
assert buckets_ge_2 >= 2, f"链表长度≥2的桶数量 {buckets_ge_2} < 2"

# 4. ASL_success 分母为 n=10
assert asl_success == Fraction(total_success, n), f"ASL_success 分母应为 n={n}"

# 5. ASL_fail 分母为 m=13
assert asl_fail == Fraction(total_fail, m), f"ASL_fail 分母应为 m={m}"

# 6. ASL_success 与 ASL_fail 值互异
assert asl_success != asl_fail, "ASL_success 与 ASL_fail 应互异"

# 7. ASL 值为正分数
assert asl_success > 0, "ASL_success 应为正"
assert asl_fail > 0, "ASL_fail 应为正"

# 8. 选项互异（防撞值）——正确值 + 3个干扰项
options = {asl_success, asl_success_B, asl_fail_C, asl_success_D}
print(f"选项集合: {options}")
print(f"选项数量: {len(options)}")
assert len(options) == 4, f"选项数量 {len(options)} < 4，存在撞值"

# 9. 正确值不与任何干扰项撞值
assert asl_success != asl_success_B, "正确值与干扰项B撞值"
assert asl_success != asl_fail_C, "正确值与干扰项C撞值"
assert asl_success != asl_success_D, "正确值与干扰项D撞值"

print("所有验证通过！")
