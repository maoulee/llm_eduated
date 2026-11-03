# -*- coding: utf-8 -*-
"""
补码真值计算 —— 单项选择题建模
题干：8位补码 X = 10110101B，求十进制真值
4个选项：A=正确值；B=取反加一漏+1；C=补码当原码读；D=符号位权重符号取反
"""


def twos_complement_value(bits):
    """补码机器数 -> 十进制真值（加权求和，符号位权重 -2^(n-1)）"""
    n = len(bits)
    val = 0
    for i, b in enumerate(bits):
        weight = (2 ** (n - 1 - i))
        if i == 0:  # 符号位
            val += b * (-weight)
        else:
            val += b * weight
    return val


def complement_correct(bits):
    """补码求真值：正确方法（负数补码 -> 取反加一 -> 加负号）"""
    n = len(bits)
    raw = int(''.join(str(b) for b in bits), 2)
    if bits[0] == 0:
        return raw  # 正数
    # 负数：数值位取反加一得绝对值，加负号
    data_bits = bits[1:]
    inverted = [1 - b for b in data_bits]
    abs_val = int(''.join(str(b) for b in inverted), 2) + 1
    return -abs_val


def error_B_missing_plus1(bits):
    """错误路径B：取反加一法漏掉最后'+1'"""
    n = len(bits)
    data_bits = bits[1:]
    inverted = [1 - b for b in data_bits]
    abs_val = int(''.join(str(b) for b in inverted), 2)  # 漏掉 +1
    return -abs_val


def error_C_as_true_form(bits):
    """错误路径C：补码机器数当作原码直接读取"""
    n = len(bits)
    # 原码：符号位表正负，数值位直接读
    sign = -1 if bits[0] == 1 else 1
    data_bits = bits[1:]
    mag = int(''.join(str(b) for b in data_bits), 2)
    return sign * mag


def error_D_sign_weight_positive(bits):
    """错误路径D：加权求和时符号位权重取 +2^(n-1) 而非 -2^(n-1)"""
    n = len(bits)
    val = 0
    for i, b in enumerate(bits):
        weight = 2 ** (n - 1 - i)
        val += b * weight  # 所有位都正权重，包括符号位
    return val


def solve():
    bits = [int(c) for c in "10110101"]
    n = len(bits)

    A = complement_correct(bits)
    B = error_B_missing_plus1(bits)
    C = error_C_as_true_form(bits)
    D = error_D_sign_weight_positive(bits)

    return A, B, C, D


# ---- 注入参数跑 ----
A, B, C, D = solve()
bits = [int(c) for c in "10110101"]
n = len(bits)

# ---- 底部：打印完整数据流 ----
print("=" * 60)
print("PARAMS:")
print("  补码机器数 X = 10110101B")
print("  机器字长 n =", n)
print("  符号位 =", bits[0], "(负数)")
print("  数值位 =", ''.join(str(b) for b in bits[1:]))

print()
print("PROCESS (正确路径: 负数补码取反加一):")
data_bits = bits[1:]
inverted = [1 - b for b in data_bits]
print("  数值位:", ''.join(str(b) for b in data_bits))
print("  取反后:", ''.join(str(b) for b in inverted))
print("  取反后的值:", int(''.join(str(b) for b in inverted), 2))
print("  +1后  :", int(''.join(str(b) for b in inverted), 2) + 1)
print("  加负号:", -(int(''.join(str(b) for b in inverted), 2) + 1), "(= A 正确真值)")

print()
print("PROCESS (错误路径B: 取反加一漏+1):")
print("  取反后的值:", int(''.join(str(b) for b in inverted), 2), "(漏掉+1)")
print("  加负号:", -int(''.join(str(b) for b in inverted), 2))

print()
print("PROCESS (错误路径C: 补码当原码读):")
print("  符号位=1 -> 负, 数值位直接读:", int(''.join(str(b) for b in data_bits), 2))
print("  原码真值:", -int(''.join(str(b) for b in data_bits), 2))

print()
print("PROCESS (错误路径D: 加权求和符号位权重取+2^7):")
w_sum = 0
for i, b in enumerate(bits):
    w = 2 ** (n - 1 - i)
    contrib = b * w
    print(f"  bit[{i}]={b}, 权重=2^{n-1-i}={w}, 贡献={contrib}")
    w_sum += contrib
print("  加权总和(全正权重):", w_sum)

print()
print("=" * 60)
print("RESULT (各选项真值):")
print(f"  A (正确) = {A}")
print(f"  B (取反加一漏+1) = {B}")
print(f"  C (补码当原码读) = {C}")
print(f"  D (符号位权重取正) = {D}")

print()
print("RULE_CHECK (题目成立条件):")
all_vals = [A, B, C, D]
print(f"  四选项值: {all_vals}")
print(f"  四选项互异: {len(set(all_vals)) == 4}")
print(f"  A为负数: {A < 0}")

# 验证补码正确性：A 应等于加权求和（符号位负权重）的结果
correct_weighted = 0
for i, b in enumerate(bits):
    w = 2 ** (n - 1 - i)
    if i == 0:
        correct_weighted += b * (-w)
    else:
        correct_weighted += b * w
print(f"  交叉验证(加权求和符号位负权重) = {correct_weighted}")
print(f"  A == 交叉验证: {A == correct_weighted}")
