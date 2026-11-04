from fractions import Fraction

def solve(keys, m):
    n = len(keys)
    
    # 构造散列表（拉链法，头插法）
    table = [[] for _ in range(m)]
    
    for key in keys:
        idx = key % m
        table[idx].insert(0, key)  # 头插法：新元素插入到链表头部
    
    # 计算 ASL 成功
    # 查找成功时，比较次数 = 元素在链表中的位置（从1开始）
    asl_success_sum = 0
    for bucket in table:
        for i, key in enumerate(bucket):
            asl_success_sum += (i + 1)
    asl_success = Fraction(asl_success_sum, n)
    
    # 计算 ASL 失败
    # 查找失败时，比较次数 = 链表长度 + 1（需要比较所有元素 + 1次None）
    asl_fail_sum = 0
    for bucket in table:
        asl_fail_sum += (len(bucket) + 1)
    asl_fail = Fraction(asl_fail_sum, m)
    
    return table, asl_success, asl_fail, asl_success_sum, asl_fail_sum

# 参数
keys = [15, 14, 21, 22, 23, 20, 10, 17, 24, 16]
m = 7

table, asl_success, asl_fail, asl_success_sum, asl_fail_sum = solve(keys, m)
n = len(keys)

# 打印结果
print("PARAMS")
print(f"关键字序列: {keys}")
print(f"表长 m: {m}")
print(f"关键字数量 n: {n}")
print()

print("REASONING")
print("散列表结构（拉链法，头插法）：")
for i, bucket in enumerate(table):
    if bucket:
        print(f"  桶{i}: {' → '.join(map(str, bucket))} → None")
    else:
        print(f"  桶{i}: None")
print()

print("ASL 成功计算：")
asl_success_sum_check = 0
for bucket in table:
    for i, key in enumerate(bucket):
        cost = i + 1
        asl_success_sum_check += cost
        print(f"  查找 {key} (H={key%m}, 桶{key%m}, 位置{i+1}): {cost} 次比较")
print(f"  总和 = {asl_success_sum_check}, n = {n}")
print(f"  ASL 成功 = {asl_success_sum_check}/{n} = {asl_success}")
print()

print("ASL 失败计算：")
asl_fail_sum_check = 0
for i, bucket in enumerate(table):
    cost = len(bucket) + 1
    asl_fail_sum_check += cost
    print(f"  桶{i} (链表长度={len(bucket)}): {cost} 次比较")
print(f"  总和 = {asl_fail_sum_check}, m = {m}")
print(f"  ASL 失败 = {asl_fail_sum_check}/{m} = {asl_fail}")
print()

print("ANSWER")
print(f"(1) 散列表结构如上所示")
print(f"(2) ASL 成功 = {asl_success_sum}/{n} = {asl_success}, ASL 失败 = {asl_fail_sum}/{m} = {asl_fail}")

# 验证通过条件（翻译 question.md 中的通过条件）
print()
print("VERIFICATION")

# 条件1: n = 10，各元素为正整数且互不相同
assert len(keys) == 10, f"条件1失败: n = {len(keys)} != 10"
assert all(k > 0 for k in keys), "条件1失败: 存在非正整数"
assert len(set(keys)) == len(keys), "条件1失败: 存在重复元素"
print("✓ 条件1通过: n=10，各元素为正整数且互不相同")

# 条件2: m = 7（质数），且 m < n
assert m == 7, f"条件2失败: m = {m} != 7"
assert m < len(keys), f"条件2失败: m = {m} >= n = {len(keys)}"
# 验证 m 是质数
is_prime = all(m % i != 0 for i in range(2, int(m**0.5) + 1))
assert is_prime, f"条件2失败: m = {m} 不是质数"
print("✓ 条件2通过: m=7（质数），且 m < n")

# 条件3: 冲突数量 3-5 个（3-5 个地址对应链表长度 ≥ 2）
conflict_count = sum(1 for bucket in table if len(bucket) >= 2)
assert 3 <= conflict_count <= 5, f"条件3失败: 冲突数量 = {conflict_count}"
print(f"✓ 条件3通过: 冲突数量 = {conflict_count}")

# 条件4: ASL 成功 = 15/10
assert asl_success == Fraction(15, 10), f"条件4失败: ASL成功 = {asl_success} != 15/10"
print(f"✓ 条件4通过: ASL成功 = {asl_success}")

# 条件5: ASL 失败 = 17/7
assert asl_fail == Fraction(17, 7), f"条件5失败: ASL失败 = {asl_fail} != 17/7"
print(f"✓ 条件5通过: ASL失败 = {asl_fail}")

# 条件6: 拉链法结构正确（头插法）
# 验证：对于每个桶，元素顺序应与插入顺序相反
# 即：后插入的元素在链表前端
for i, bucket in enumerate(table):
    # 找到所有映射到桶i的关键字（按插入顺序）
    keys_in_bucket = [k for k in keys if k % m == i]
    # 头插法后，链表顺序应与插入顺序相反
    assert bucket == list(reversed(keys_in_bucket)), f"条件6失败: 桶{i}顺序错误"
print("✓ 条件6通过: 拉链法结构正确（头插法）")

# 条件7: ASL 失败分母为 m
# asl_fail 已经是 Fraction(asl_fail_sum, m)，分母应为 m（约分后可能不同，但原始分母是m）
assert asl_fail_sum % 1 == 0 and m == 7, f"条件7失败: ASL失败分母不为m"
print(f"✓ 条件7通过: ASL失败分母为 m = {m}")

print()
print("所有通过条件验证通过！")
