def compute_next(s):
    """next[j] = s[0..j-1] 的最长相等真前后缀长度"""
    n = len(s)
    next_arr = [0] * n
    for j in range(1, n):
        sub = s[0:j]  # s[0..j-1]
        max_len = 0
        for length in range(1, len(sub)):  # 真前后缀: length < len(sub)
            if sub[:length] == sub[-length:]:
                max_len = length
        next_arr[j] = max_len
    return next_arr


def compute_nextval(s, next_arr):
    """nextval 优化数组"""
    n = len(s)
    nextval = [0] * n
    for j in range(1, n):
        if s[j] == s[next_arr[j]]:
            nextval[j] = nextval[next_arr[j]]
        else:
            nextval[j] = next_arr[j]
    return nextval


# ========== 主计算 ==========
s = "ababab"
k = 5

next_arr = compute_next(s)
nextval = compute_nextval(s, next_arr)

# 选项值
correct = next_arr[k]
b_val = nextval[k]
c_val = correct - 1
d_val = len(s[0:k])  # 忘记"真前后缀"，取子串本身长度

# ========== 验证 ==========
assert correct >= 2, f"next[{k}]={correct} 应 >= 2（非平凡）"
assert len({correct, b_val, c_val, d_val}) == 4, f"选项不互异: A={correct}, B={b_val}, C={c_val}, D={d_val}"
assert d_val == len(s[0:k]), f"D 应为子串 s[0..{k-1}] 的长度 {len(s[0:k])}"

# ========== 输出 ==========
print("PARAMS")
print(f"模式串: \"{s}\"")
print(f"目标位置: k={k}")
print()
print("REASONING")
print(f"next 数组: {next_arr}")
print(f"nextval 数组: {nextval}")
print(f"next[{k}] = {correct}  （s[0..{k-1}]=\"{s[0:k]}\" 的最长真前后缀长度）")
print(f"nextval[{k}] = {b_val}  （混淆 next 与 nextval）")
print(f"next[{k}] - 1 = {c_val}  （前后缀长度算错 1）")
print(f"忘记真前后缀约束 = {d_val}  （将 \"{s[0:k]}\" 本身当作相等前后缀）")
print()
print("ANSWER")
print(f"A. {correct}")
print(f"B. {b_val}")
print(f"C. {c_val}")
print(f"D. {d_val}")
