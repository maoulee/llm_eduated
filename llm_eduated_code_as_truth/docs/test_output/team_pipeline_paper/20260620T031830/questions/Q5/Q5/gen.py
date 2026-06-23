def solve(n):
    """模拟题干中的 C 语言循环"""
    sum_val = 0
    i = 1
    iterations = 0
    i_values = []
    while i <= n:
        sum_val += i
        i_values.append(i)
        iterations += 1
        i *= 2
    return sum_val, iterations, i_values

def solve_error_lt(n):
    """错误路径1：误用 i < n（严格小于），少算一轮"""
    sum_val = 0
    i = 1
    while i < n:
        sum_val += i
        i *= 2
    return sum_val

def solve_error_inclusive_power(n):
    """错误路径2：误以为 i 会增长到 2n（256），多算一轮"""
    sum_val = 0
    i = 1
    while i <= 2 * n:
        sum_val += i
        i *= 2
    return sum_val

def solve_error_off_by_one(n):
    """错误路径3：误用等比数列公式 2^n - 1 但 n 取错（n=9）"""
    return (1 << 9) - 1

# 注入参数
n = 128
correct_sum, iterations, i_values = solve(n)

# 验证通过条件
assert iterations == 8, f"循环应执行8轮，实际{iterations}轮"
assert i_values == [1, 2, 4, 8, 16, 32, 64, 128], f"i值序列错误: {i_values}"
assert correct_sum == 255, f"sum应为255，实际{correct_sum}"

# 生成选项（B=正确，A/C/D=干扰项）
A = solve_error_lt(n)        # 127: 误用 i < n
B = correct_sum               # 255: 正确值
C = solve_error_inclusive_power(n)  # 511: 多算一轮
D = solve_error_off_by_one(n)       # 511 冲突，改用 256

# 修正 D 避免与 C 重复
D = 256  # 误以为 sum = n * 2

# 验证选项
assert len({A, B, C, D}) == 4, f"选项不互异: A={A}, B={B}, C={C}, D={D}"
assert B == 255, f"B应为正确值255，实际{B}"

print(f"循环轮数: {iterations}")
print(f"i 取值序列: {i_values}")
print(f"sum 最终值: {correct_sum}")
print(f"选项: A={A}, B={B}, C={C}, D={D}")
print(f"正确答案: B ({B})")
