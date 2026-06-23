def compute_next(S):
    """
    计算 KMP 算法的 next 数组（严蔚敏定义）
    下标从 1 开始
    next[1] = 0, next[2] = 1
    next[j] = 前 j-1 个字符的最长相等真前后缀长度 + 1
    """
    n = len(S)
    next_arr = [0] * (n + 1)  # 下标 1 到 n
    next_arr[1] = 0
    if n >= 2:
        next_arr[2] = 1

    for j in range(3, n + 1):
        # 求前 j-1 个字符的最长相等真前后缀长度
        prefix = S[:j-1]  # 前 j-1 个字符
        max_len = 0
        for k in range(1, len(prefix)):  # 真前后缀，长度从 1 到 len-1
            if prefix[:k] == prefix[-k:]:
                max_len = k
        next_arr[j] = max_len + 1

    return next_arr


def solve(S, j_target):
    """
    计算模式串 S 的 next 数组中第 j_target 位的值
    """
    next_arr = compute_next(S)
    return next_arr[j_target]


# ========== 主程序 ==========
S = "abcabc"
j_target = 5

answer = solve(S, j_target)

print(f"模式串: {S}")
print(f"目标位置: j={j_target}")
print(f"next 数组: {compute_next(S)[1:]}")
print(f"next[{j_target}] = {answer}")

# ========== 验证通过条件 ==========
# 条件1: len(S) ∈ [6, 10]
assert 6 <= len(S) <= 10, f"模式串长度 {len(S)} 不在 [6,10] 范围内"

# 条件2: 目标位置 j ∈ [5, 8]
assert 5 <= j_target <= 8, f"目标位置 {j_target} 不在 [5,8] 范围内"

# 条件3: next[j] > 1（非平凡值）
assert answer > 1, f"next[{j_target}] = {answer} 应为非平凡值 (>1)"

# 条件4: S 中存在重复字符
assert len(set(S)) < len(S), "模式串应包含重复字符"

# ========== 选择题专属验证 ==========
OPTIONS = {"A": 1, "B": 2, "C": 3, "D": 4}
CORRECT_OPTION = "B"
assert len(set(OPTIONS.values())) == 4, "选项值应互不相同"
assert OPTIONS[CORRECT_OPTION] == answer, f"正确选项{CORRECT_OPTION}的值{OPTIONS[CORRECT_OPTION]}应等于答案{answer}"

print(f"\n选项: {OPTIONS}")
print(f"正确选项: {CORRECT_OPTION}")
