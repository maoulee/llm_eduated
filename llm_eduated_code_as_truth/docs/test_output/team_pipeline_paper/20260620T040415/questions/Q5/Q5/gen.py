# 二叉树叶子结点数计算
# 题干：二叉树共 53 个结点，度为 1 的结点有 2 个，求叶子结点数

# PARAMS
n = 53       # 总结点数
n1 = 2       # 度为1的结点数

# REASONING
# 核心公式：n0 = n2 + 1
# 辅助公式：n = n0 + n1 + n2
# 联立：n = (n2 + 1) + n1 + n2 = 2*n2 + n1 + 1
# => n2 = (n - n1 - 1) / 2
# => n0 = n2 + 1

n2 = (n - n1 - 1) // 2
n0_correct = n2 + 1

# 干扰项计算
# B: 记错核心公式 n0 = n2（漏掉+1）
n0_B = n2
# C: 符号方向错误 n0 = n2 - 1
n0_C = n2 - 1
# D: 忽略度为1的结点，误用 n0 = n - n2
n0_D = n - n2

print(f"n2 = {n2}")
print(f"n0_correct = {n0_correct}")
print(f"n0_B = {n0_B}")
print(f"n0_C = {n0_C}")
print(f"n0_D = {n0_D}")

# 验证：n = n0 + n1 + n2
assert n0_correct + n1 + n2 == n, "结点总数验证失败"
# 验证：n0 = n2 + 1
assert n0_correct == n2 + 1, "核心公式验证失败"
# 验证：4选项互异
assert len({n0_correct, n0_B, n0_C, n0_D}) == 4, "选项碰撞"
# 验证：n2为整数（n - n1 - 1 为偶数）
assert (n - n1 - 1) % 2 == 0, "n2非整数"

# ANSWER
print(f"A. {n0_correct}")
print(f"B. {n0_B}")
print(f"C. {n0_C}")
print(f"D. {n0_D}")
print(f"正确答案: A")
