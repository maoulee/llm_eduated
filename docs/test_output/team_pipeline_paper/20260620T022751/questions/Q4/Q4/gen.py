"""
KMP next数组计算 + 干扰项派生
模式串 P = "ababacab" (1-based)
求 next[5]
"""

P = "ababacab"  # 1-based: P[1]='a', P[2]='b', P[3]='a', P[4]='b', P[5]='a', ...
j = 5

def compute_next_1based(pattern):
    """
    1-based next数组:
    next[1] = 0
    next[j] = len(最长相等真前后缀 of P[1..j-1]) + 1,  j > 1
    """
    n = len(pattern)
    nxt = [0] * (n + 1)  # 1-based, nxt[0] unused
    nxt[1] = 0
    for jj in range(2, n + 1):
        # 求 P[1..jj-1] 的最长相等真前后缀长度
        sub = pattern[0:jj - 1]  # P[1..jj-1] in 0-based slice
        best = 0
        for k in range(1, len(sub)):  # 真前后缀，长度从1到len-1
            if sub[:k] == sub[len(sub) - k:]:
                best = k
        nxt[jj] = best + 1
    return nxt

def compute_nextval_1based(pattern, nxt):
    """
    nextval数组:
    nextval[1] = 0
    nextval[j] = next[j] if P[j] != P[next[j]]
    nextval[j] = nextval[next[j]] if P[j] == P[next[j]]
    """
    n = len(pattern)
    nv = [0] * (n + 1)
    nv[1] = 0
    for jj in range(2, n + 1):
        if pattern[jj - 1] != pattern[nxt[jj] - 1]:  # P[j] vs P[next[j]], 1-based to 0-based
            nv[jj] = nxt[jj]
        else:
            nv[jj] = nv[nxt[jj]]
    return nv

# ========== 正确计算 ==========
nxt = compute_next_1based(P)
nv = compute_nextval_1based(P, nxt)

print(f"模式串 P = \"{P}\"")
print(f"1-based next数组: {nxt[1:]}")
print(f"1-based nextval数组: {nv[1:]}")
print(f"next[{j}] = {nxt[j]}")
print(f"nextval[{j}] = {nv[j]}")

# ========== 干扰项 ==========

# A: 正确值
A = nxt[j]
print(f"\nA (正确 next[{j}]): {A}")

# B: 索引混淆 — 将1-based误作0-based，计算next[4]而非next[5]
# 即把目标位置j=5当成0-based的索引4，实际计算的是next[4]
B = nxt[j - 1]  # next[4]
print(f"B (索引混淆 next[{j-1}]): {B}")

# C: 最长相等真前后缀识别错误
# 误认为 P[1..4]="abab" 的最长相等真前后缀为 "aba"(长度3) 而非 "ab"(长度2)
# 错误结果 = 3 + 1 = 4
sub_for_j = P[0:j - 1]  # P[1..j-1] = "abab"
print(f"  P[1..{j-1}] = \"{sub_for_j}\"")
# 正确最长真前后缀
correct_best = 0
for k in range(1, len(sub_for_j)):
    if sub_for_j[:k] == sub_for_j[len(sub_for_j) - k:]:
        correct_best = k
print(f"  正确最长真前后缀长度: {correct_best} -> next[{j}]={correct_best+1}")
# 错误：误认为"aba"是
C = 3 + 1  # 误认为最长真前后缀为"aba"(长度3)
print(f"C (前后缀识别错误，误认长度3): {C}")

# D: next/nextval混淆 — 计算nextval[5]而非next[5]
D = nv[j]
print(f"D (nextval[{j}]): {D}")

# ========== 验证通过条件 ==========
print(f"\n===== 验证通过条件 =====")

# 条件1: 参数约束
n = len(P)
assert 6 <= n <= 10, f"模式串长度 {n} 不在 [6,10]"
assert 2 <= j <= n - 2, f"目标位置 {j} 不在 [2, {n-2}]"
print(f"✓ 条件1: 模式串长度={n}, 目标位置={j}")

# 条件2: next[j] 值域
assert 2 <= A <= 4, f"next[{j}]={A} 不在 [2,4]"
print(f"✓ 条件2: next[{j}]={A} ∈ [2,4]")

# 条件3: 4选项互异
assert len({A, B, C, D}) == 4, f"选项碰撞: A={A}, B={B}, C={C}, D={D}"
print(f"✓ 条件3: 4选项互异 {{A={A}, B={B}, C={C}, D={D}}}")

# 条件4: next[j] != nextval[j]
assert A != D, f"next[{j}] == nextval[{j}] = {A}"
print(f"✓ 条件4: next[{j}]={A} != nextval[{j}]={D}")

# 条件5: 正确值唯一确定（由确定性算法保证，此处验证next数组一致性）
nxt2 = compute_next_1based(P)
assert nxt2[j] == A, "next值不唯一"
print(f"✓ 条件5: next[{j}] 唯一确定 = {A}")

# 条件6: 干扰项对应声明错误类型
assert B == nxt[j - 1], f"B 应等于 next[{j-1}]"
assert C == 4, f"C 应等于 4 (误认前后缀长度3+1)"
assert D == nv[j], f"D 应等于 nextval[{j}]"
print(f"✓ 条件6: 干扰项对应声明错误路径")

print(f"\n===== 全部通过 =====")
print(f"最终选项: A={A}, B={B}, C={C}, D={D}")
