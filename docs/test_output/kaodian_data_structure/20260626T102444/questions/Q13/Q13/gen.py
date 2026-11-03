# -*- coding: utf-8 -*-
"""
散列表拉链法构造与 ASL 计算
题干翻译：H(key)=key%11, 拉链法, m=11
关键字序列: {19,14,23,1,68,20,84,27,55,11}
"""

# ===================== PARAMS =====================
KEYS = [19, 14, 23, 1, 68, 20, 84, 27, 55, 11]
P = 11  # 散列函数模值 = 散列表长度 m
N = len(KEYS)  # 关键字个数

# ===================== MODEL =====================
# 翻译："散列函数 H(key) = key % 11"
def H(key, p=P):
    return key % p

# 翻译："拉链法，各关键字按给定序列顺序依次插入"
#   - 对每个关键字算 H(key)，挂到对应地址链表末尾
def build_hashtable(keys, p=P):
    table = {i: [] for i in range(p)}  # 地址 0~(p-1), 每个地址一条链表
    for k in keys:
        addr = H(k, p)
        table[addr].append(k)
    return table

# 翻译："查找成功：各关键字的比较次数 = 该关键字在链表中的位置（从1算起）"
def success_cmp_count(table, key, p=P):
    """返回 key 在其链表中从链头算起的比较次数（含自身）"""
    addr = H(key, p)
    chain = table[addr]
    for idx, k in enumerate(chain):
        if k == key:
            return idx + 1  # 第1个比较1次, 第2个比较2次...
    return None  # not found

# 翻译："查找失败：每个地址的比较次数 = 该地址链表长度"
def failure_cmp_count(table, addr):
    """拉链法查找失败: 需遍历整条链表才能确认不在"""
    return len(table[addr])

# ===================== SOLVE =====================
table = build_hashtable(KEYS, P)

# --- Q1: 散列表存储结构 ---
print("=" * 50)
print("Q1: 散列表存储结构（拉链法）")
print("=" * 50)
for addr in range(P):
    chain = table[addr]
    if chain:
        chain_str = " -> ".join(str(k) for k in chain) + " -> NULL"
    else:
        chain_str = "NULL"
    print(f"  地址 {addr:2d}: {chain_str}")

# --- Q2: ASL_success ---
print()
print("=" * 50)
print("Q2: 查找成功 ASL")
print("=" * 50)
total_success_cmp = 0
for k in KEYS:
    cnt = success_cmp_count(table, k, P)
    addr = H(k, P)
    print(f"  key={k:2d}, H={addr}, 在链表中第 {cnt} 个位置, 比较次数={cnt}")
    total_success_cmp += cnt

ASL_success_num = total_success_cmp
ASL_success_den = N
ASL_success = ASL_success_num / ASL_success_den
print(f"  分子(各关键字比较次数之和) = {ASL_success_num}")
print(f"  分母(关键字个数 n) = {ASL_success_den}")
print(f"  ASL_success = {ASL_success_num}/{ASL_success_den} = {ASL_success:.4f}")

# --- Q3: ASL_failure ---
print()
print("=" * 50)
print("Q3: 查找失败 ASL")
print("=" * 50)
total_failure_cmp = 0
for addr in range(P):
    cnt = failure_cmp_count(table, addr)
    total_failure_cmp += cnt
    print(f"  地址 {addr:2d}: 链表长度 = {cnt}, 比较次数 = {cnt}")

ASL_failure_num = total_failure_cmp
ASL_failure_den = P
ASL_failure = ASL_failure_num / ASL_failure_den
print(f"  分子(各地址链表长度之和) = {ASL_failure_num}")
print(f"  分母(散列地址个数 p) = {ASL_failure_den}")
print(f"  ASL_failure = {ASL_failure_num}/{ASL_failure_den} = {ASL_failure:.4f}")

# ===================== ANSWER =====================
print()
print("=" * 50)
print("ANSWER")
print("=" * 50)
from fractions import Fraction
asl_s = Fraction(ASL_success_num, ASL_success_den)
asl_f = Fraction(ASL_failure_num, ASL_failure_den)
print(f"ASL_success = {asl_s} = {float(asl_s):.4f}")
print(f"ASL_failure = {asl_f} = {float(asl_f):.4f}")

# ===================== ASSERT（通过条件翻译） =====================
# 条件1: 散列表构造正确 — 至少2个地址链表长度>=2, 至少1个地址为空
chain_lengths = [len(table[addr]) for addr in range(P)]
ge2_count = sum(1 for c in chain_lengths if c >= 2)
empty_count = sum(1 for c in chain_lengths if c == 0)
assert ge2_count >= 2, f"条件1失败: 链表长度>=2的地址数={ge2_count}, 需要>=2"
assert empty_count >= 1, f"条件1失败: 空地址数={empty_count}, 需要>=1"

# 条件2: ASL_success 分子 = 各关键字比较次数之和; 分母 = n = 10
assert ASL_success_den == N, f"条件2失败: 成功ASL分母={ASL_success_den}, 需要={N}"
assert ASL_success * ASL_success_den == ASL_success_num, "条件2失败: ASL_success * 10 != 分子"

# 条件3: ASL_failure 分子 = 各地址链表长度之和; 分母 = 11
assert ASL_failure_den == P, f"条件3失败: 失败ASL分母={ASL_failure_den}, 需要={P}"
assert ASL_failure * ASL_failure_den == ASL_failure_num, "条件3失败: ASL_failure * 11 != 分子"

# 条件4: 成功/失败 ASL 分母不同 (10 != 11)
assert ASL_success_den != ASL_failure_den, f"条件4失败: 分母相同({ASL_success_den}), 应不同"

# 条件5: 分布均匀性 — 不存在单一地址链表长度 >= 4
max_chain = max(chain_lengths)
assert max_chain < 4, f"条件5失败: 最大链表长度={max_chain}, 需要<4"

# 补充验证: 每个关键字确实被正确放置到 H(key) 地址
for k in KEYS:
    assert k in table[H(k, P)], f"验证失败: key={k} 未在地址 {H(k,P)} 的链表中"

print()
print("✅ 所有通过条件 assert 均通过")
