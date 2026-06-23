"""
KMP next 数组计算 — 严蔚敏版（next[1]=0, next[2]=1, j从1开始）
模式串 P = "abacababc"，求 next[9]
"""
P = "abacababc"
n = len(P)  # 9

def compute_next(s):
    """严蔚敏版 next 数组（1-based），返回 next[1..n]"""
    m = len(s)
    nxt = [0] * (m + 1)  # nxt[1..m]
    nxt[1] = 0
    nxt[2] = 1
    for j in range(3, m + 1):
        # 求 P[1..j-1] 的最长相等前后缀长度 k
        k = 0
        for length in range(j - 1, 0, -1):
            prefix = s[0:length]       # P[1..length] (0-based: 0..length-1)
            suffix = s[j - 1 - length:j - 1]  # P[j-length..j-1] (0-based)
            if prefix == suffix:
                k = length
                break
        nxt[j] = k + 1
    return nxt

def compute_lps(s):
    """0-based LPS array (lps[i] = 最长相等前后缀长度 for s[0..i])"""
    m = len(s)
    lps = [0] * m
    length = 0
    i = 1
    while i < m:
        if s[i] == s[length]:
            length += 1
            lps[i] = length
            i += 1
        else:
            if length != 0:
                length = lps[length - 1]
            else:
                lps[i] = 0
                i += 1
    return lps

nxt = compute_next(P)
lps = compute_lps(P)

j = 9  # 求 next[9]

# === A: 正确答案 ===
A = nxt[j]

# === B: 忘记 +1（直接输出最长相等前后缀长度 k）===
# k = nxt[j] - 1
B = nxt[j] - 1

# === C: off-by-one，0-based 下标偏移 ===
# 0-based 的 lps[j-1] 就是 P[0..j-1] 的最长相等前后缀长度
# 此值本身没有 +1，与 B 不同的情况出现在不对称串中
C = lps[j - 1]

# === D: 位置混淆——取 next[j-1] = next[8] ===
D = nxt[j - 1]

print(f"模式串 P = \"{P}\"，长度 n = {n}")
print(f"next 数组（1-based）: {nxt[1:]}")
print(f"LPS 数组（0-based）:  {lps}")
print(f"j = {j}")
print(f"A (next[{j}] 正确值)   = {A}")
print(f"B (忘记+1, k)         = {B}")
print(f"C (0-based lps 偏移)  = {C}")
print(f"D (next[{j-1}] 位置混淆) = {D}")
print()

# === 验证段（assert 打到通过条件）===

# 条件1: 4选项互异
assert len({A, B, C, D}) == 4, f"选项不互异: A={A} B={B} C={C} D={D}"

# 条件2: A = next[j] 正确值
assert A == nxt[j], f"A != next[{j}]"

# 条件3: B = k (未+1), 与 A 相差 1
assert B == nxt[j] - 1, f"B 应等于 k = next[{j}]-1"
assert A - B == 1, "A与B应相差1"

# 条件4: D = next[j-1]
assert D == nxt[j - 1], f"D 应等于 next[{j-1}]"

# 条件5: 答案非平凡 next[j] >= 3
assert A >= 3, f"next[{j}] = {A}, 应 >= 3"

print("=== 所有 assert 通过 ===")
