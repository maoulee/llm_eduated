# -*- coding: utf-8 -*-
"""
KMP next 数组：给定模式串 P="abaabac"，求 next[6]。
408 标准约定：next[0]=-1, next[1]=0, j>=2 时 next[j]=P[0..j-1] 最长相等真前后缀长度。
"""

P = "abaabac"
n = len(P)
j_target = 6


def longest_proper_border(s):
    """求字符串 s 的最长相等真前后缀长度。
    真前后缀：前缀长度 k 满足 1<=k<=len(s)-1，且 s[:k]==s[len(s)-k:]。
    """
    L = len(s)
    for k in range(L - 1, 0, -1):
        if s[:k] == s[L - k:]:
            return k
    return 0


def compute_next(pattern):
    """按 408 标准约定计算 next 数组。"""
    m = len(pattern)
    nxt = [0] * m
    nxt[0] = -1
    if m >= 2:
        nxt[1] = 0
    for j in range(2, m):
        nxt[j] = longest_proper_border(pattern[:j])
    return nxt


def next_with_take_j_error(pattern, j):
    """错误路径B：忽略真前缀限制，误认为 next[j]=j。"""
    return j


def next_with_off_by_one_error(pattern, j):
    """错误路径C：差一位误算——考生在匹配过程中多/少匹配一个字符，
    得到的长度比正确值少 1（correct-1）。
    场景：考生认为 "abaaba" 的最长相等真前后缀是长度 2（只对齐了前两字符判断，
    误以为第三字符不匹配），反映"差一位"的典型错误。
    """
    correct = longest_proper_border(pattern[:j])
    return correct - 1 if correct >= 1 else 0


def next_with_misunderstand_error(pattern, j):
    """错误路径D：根本误解定义——认为不存在匹配。"""
    return 0


# ========== 建模计算 ==========

print("=== PARAMS ===")
print(f"模式串 P = \"{P}\", 长度 n = {n}")
print(f"目标位置 j = {j_target}")
print(f"前缀子串 P[0..{j_target-1}] = \"{P[:j_target]}\"")

nxt = compute_next(P)
print(f"\n完整 next 数组: {nxt}")
for idx in range(n):
    print(f"  next[{idx}] = {nxt[idx]}")

correct = nxt[j_target]
print(f"\n=== REASONING ===")
print(f"求 next[{j_target}]：在 P[0..{j_target-1}] = \"{P[:j_target]}\" 上找最长相等真前后缀。")
sub = P[:j_target]
L = j_target
print(f"真前后缀长度 k 从大到小尝试：")
found_k = 0
for k in range(L - 1, 0, -1):
    prefix_part = sub[:k]
    suffix_part = sub[L - k:]
    match = prefix_part == suffix_part
    tag = " <-- 命中(最长)" if (match and found_k == 0) else ""
    if match and found_k == 0:
        found_k = k
    print(f"  k={k}: 前缀\"{prefix_part}\" vs 后缀\"{suffix_part}\" => {'相等' if match else '不等'}{tag}")

print(f"\n最长相等真前后缀 = \"{sub[:correct]}\" (长度 {correct})")
print(f"故 next[{j_target}] = {correct}")

# ========== 选项派生 ==========
A = correct
B = next_with_take_j_error(P, j_target)
C = next_with_off_by_one_error(P, j_target)
D = next_with_misunderstand_error(P, j_target)

print(f"\n=== ANSWER ===")
print(f"A = {A}  (正确值)")
print(f"B = {B}  (错误路径：忽略真前缀限制，取 next[j]=j)")
print(f"C = {C}  (错误路径：差一位匹配长度，比正确值少1)")
print(f"D = {D}  (错误路径：根本误解/不存在匹配)")
print(f"\n正确答案：A. {A}")

# ========== 通过条件 assert ==========

# 条件1: 正确值唯一确定，A = 计算出的 next[6]
assert A == correct, f"A选项({A})应等于next[{j_target}]的正确值({correct})"

# 条件2: 4选项互异
assert len({A, B, C, D}) == 4, f"4选项必须互异，实际: A={A},B={B},C={C},D={D}"

# 条件3: 干扰项对应声明错误路径
assert B == j_target, f"B应等于j={j_target}(忽略真前缀限制取j路径), 实际B={B}"
assert C == correct - 1, f"C应等于正确值-1={correct-1}(差一位路径), 实际C={C}"
assert D == 0, f"D应等于0(根本误解路径), 实际D={D}"

# 条件4: 干扰项非负且合理（不等于正确值）
for label, val in [("B", B), ("C", C), ("D", D)]:
    assert val != correct, f"干扰项{label}={val}不能等于正确值{correct}"

# 条件5: 正确值 >= 2（非平凡匹配）
assert correct >= 2, f"正确值{correct}应>=2，保证非平凡考察意义"

# 额外验证：next数组与 longest_proper_border 一致性已通过 compute_next 保证
# 验证 "abaaba" 的最长相等真前后缀确实为 "aba"
assert sub[:correct] == "aba", f"最长相等真前后缀应为'aba'，实际'{sub[:correct]}'"

print("\n=== 所有通过条件 assert 全部通过 ===")
