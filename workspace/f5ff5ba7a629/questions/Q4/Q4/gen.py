#!/usr/bin/env python3
"""
Q6 参数搜索 + 求解数据流
优先选择非退化、有教学意义的模式串。
"""

import random

def compute_next(P):
    n = len(P)
    nxt = [0] * n
    if n >= 1:
        nxt[0] = 0
    if n >= 2:
        nxt[1] = 1
    for j in range(2, n):
        max_len = 0
        for k in range(j - 1, 0, -1):
            if P[0:k] == P[j-k:j]:
                max_len = k
                break
        nxt[j] = max_len
    return nxt

def compute_nextval(P, nxt):
    n = len(P)
    nextval = [0] * n
    nextval[0] = 0
    for j in range(1, n):
        if P[j] == P[nxt[j]]:
            nextval[j] = nextval[nxt[j]]
        else:
            nextval[j] = nxt[j]
    return nextval

def all_border_lengths(P_prefix):
    m = len(P_prefix)
    lengths = []
    for k in range(1, m):
        if P_prefix[0:k] == P_prefix[m-k:m]:
            lengths.append(k)
    return sorted(lengths)

def check_candidate(P, j):
    n = len(P)
    if n < 6 or n > 10:
        return None
    if j < 4 or j > n - 1:
        return None

    nxt = compute_next(P)
    nextval = compute_nextval(P, nxt)
    v = nxt[j]

    if v < 2 or v > 4:
        return None

    prefix = P[0:j]
    borders = all_border_lengths(prefix)
    shorter = [b for b in borders if b < v and b > 0]
    if len(shorter) == 0:
        return None
    short_val = shorter[-1]

    nv = nextval[j]
    if nv == v:
        return None

    opt_a = v
    opt_b = v - 1
    if opt_b == short_val or opt_b == nv:
        opt_b = v + 1
    if opt_b < 0:
        opt_b = v + 1
    opt_c = short_val
    opt_d = nv

    opts = [opt_a, opt_b, opt_c, opt_d]
    if len(set(opts)) != 4:
        return None
    if any(x < 0 or x > 5 for x in opts):
        return None

    # 计算非退化度评分
    unique_chars = len(set(P))
    distinct_next = len(set(nxt))

    return {
        'P': P, 'n': n, 'j': j,
        'next_j': v, 'opt_A': opt_a, 'opt_B': opt_b,
        'opt_C': opt_c, 'opt_D': opt_d,
        'nextval_j': nv, 'shorter_borders': shorter,
        'all_borders': borders,
        'full_next': nxt[:], 'full_nextval': nextval[:],
        'unique_chars': unique_chars,
        'distinct_next': distinct_next,
        'num_borders': len(borders),
    }

random.seed(123)
results = []
letters_pool = 'abcdef'

for _ in range(800000):
    n = random.randint(6, 10)
    P = ''.join(random.choice(letters_pool) for _ in range(n))
    for j in range(4, n):
        r = check_candidate(P, j)
        if r:
            key = (P, j)
            if key not in {(x['P'], x['j']) for x in results}:
                results.append(r)

# 手工测试经典结构
manual = [
    "abaabaa", "abaabaab", "abaabaaba",
    "abcabca", "abcabcab", "abcabcabc",
    "abacaba", "abacabac",
    "aabaab", "aabaaba", "aabaabaa", "aabaabaab",
    "abcabdab", "aabcaa", "aabcaab",
    "ababaa", "ababaab", "ababaaba", "ababaabab",
    "acabacab", "abacabab", "aabaaab", "aabaaaba",
    "aabacaa", "aabacaab", "aabacaaba",
    "abacaba", "abacabaa", "abacabaab",
    "abcabdabc", "abcabdabcd",
    "aabcaab", "aabcaabc",
    "abaabca", "abaabcab", "abaabcaba",
    "ababcab", "ababcaba", "ababcabab",
]
for P in manual:
    n = len(P)
    if n < 6 or n > 10:
        continue
    for j in range(4, n):
        r = check_candidate(P, j)
        if r:
            key = (P, j)
            if key not in {(x['P'], x['j']) for x in results}:
                results.append(r)

# 计算教学模式质量：重复块结构（如 abab, abcabc）更有教学意义
def is_repetitive_pattern(P, j):
    """检测 P[0:j] 是否为有教学意义的重复块结构（非单字符重复）"""
    prefix = P[0:j]
    # 单字符重复退化检测
    if len(set(prefix)) == 1:
        return 0
    # 2字符交替重复（如 ababab）
    if len(set(prefix)) == 2:
        for blk in range(2, j//2+1):
            if j % blk == 0:
                block = prefix[:blk]
                if all(prefix[k:k+blk] == block for k in range(0, j, blk)) and len(set(block)) == 2:
                    return 2  # 中等质量
    # 3+字符重复块（如 abcabc, abacaba 等）
    return 3  # 高质量

# 排序优先：教学模式质量 > 字母种类多 > next 值有变化 > border 数适中
results.sort(key=lambda r: (-is_repetitive_pattern(r['P'], r['j']), -r['unique_chars'], -r['distinct_next'], -r['num_borders']))

print(f"找到 {len(results)} 组满足约束的参数")

# 过滤掉太退化的（只有1-2种字符的）
good = [r for r in results if r['unique_chars'] >= 3]
print(f"其中字符种类>=3的有 {len(good)} 组")

if good:
    best = good[0]
else:
    best = results[0]

P = best['P']
j = best['j']
v = best['next_j']

print("\n===== 选定参数 =====")
print(f'模式串 P = "{P}"')
print(f"长度 n = {best['n']}")
print(f"求解位置 j = {j}")
print()

print("===== 求解数据流 =====")
prefix = P[0:j]
borders = best['all_borders']
print(f'P[0..{j-1}] = "{prefix}"')
print(f'P[0..{j-1}] 的所有相等真前后缀长度: {borders}')
for b in borders:
    print(f'  长度 {b}: 前缀 "{prefix[0:b]}" vs 后缀 "{prefix[len(prefix)-b:]}" ✓')
print(f'  → 最长相等真前后缀长度 = {max(borders)} = next[{j}]')
print()
print(f"next[{j}] = {v}")
print()
print(f"完整 next 数组:    {best['full_next']}")
print(f"完整 nextval 数组: {best['full_nextval']}")
print()

print("===== 选项构造 =====")
print(f"A (正确):     next[{j}] = {best['opt_A']}")
print(f"B (off-by-1): {best['opt_A']} - 1 = {best['opt_B']}")
print(f"C (取短):     较短前后缀长度 = {best['opt_C']}")
print(f"D (nextval):  nextval[{j}] = {best['opt_D']}")
print()

print("===== 验证 =====")
opts = [best['opt_A'], best['opt_B'], best['opt_C'], best['opt_D']]
assert len(set(opts)) == 4, "选项不互异"
assert all(0 <= x <= 5 for x in opts), "选项越界"
assert best['opt_D'] != best['opt_A'], "nextval == next"
assert best['opt_C'] < best['opt_A'], "短 >= 长"
assert best['opt_C'] > 0, "短 <= 0"
assert 2 <= best['opt_A'] <= 4, "非退化失败"
print("所有约束验证通过 ✓")

print(f"\n===== 前10组备选（字符种类>=3） =====")
for i, r in enumerate(good[:10]):
    print(f'  #{i+1}: P="{r["P"]}", j={r["j"]}, next[{r["j"]}]={r["next_j"]}, '
          f'borders={r["all_borders"]}, nextval[{r["j"]}]={r["nextval_j"]}, '
          f'uniq={r["unique_chars"]}')
