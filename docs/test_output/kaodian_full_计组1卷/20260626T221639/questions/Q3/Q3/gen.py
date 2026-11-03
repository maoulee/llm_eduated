# -*- coding: utf-8 -*-
"""
题目：给定十进制真值 -75，求 8 位原码表示。
建模：逐句翻译题干规则 + 4 选项各算正确值/干扰值。
"""


def to_signed(value, bits):
    """把整数解释为指定位宽的有符号数（二进制表示）。"""
    if value >= 0:
        return format(value, '0{}b'.format(bits))
    else:
        return format((1 << bits) + value, '0{}b'.format(bits))


def solve_original(truth_value, bits=8):
    """
    翻译题干"求原码"规则：
    - 符号位：负→1，正→0
    - 数值位：取绝对值的二进制
    """
    num_bits = bits - 1
    abs_val = abs(truth_value)
    sign_bit = 1 if truth_value < 0 else 0
    magnitude_bits = format(abs_val, '0{}b'.format(num_bits))
    original_code = str(sign_bit) + magnitude_bits
    return original_code


def solve_complement(truth_value, bits=8):
    """
    翻译题干干扰项 C 规则："按补码规则转换"。
    """
    if truth_value >= 0:
        return format(truth_value, '0{}b'.format(bits))
    else:
        return format((1 << bits) + truth_value, '0{}b'.format(bits))


def solve_with_magnitude_error(truth_value, bits=8, flip_bit=3):
    """
    翻译题干干扰项 D 规则："绝对值二进制转换中某位翻转"。
    flip_bit 指定翻转绝对值数值位的第几位（从最低位起 0-indexed）。
    补符号位 1（负数）。
    """
    num_bits = bits - 1
    abs_val = abs(truth_value)
    abs_bits = list(format(abs_val, '0{}b'.format(num_bits)))
    # flip_bit 从最低位起，转换为从左起的索引
    pos_from_left = num_bits - 1 - flip_bit
    abs_bits[pos_from_left] = '1' if abs_bits[pos_from_left] == '0' else '0'
    return '1' + ''.join(abs_bits)


# ===== 注入参数 =====
truth_value = -75
bits = 8
num_bits = bits - 1  # 7 位数值位
max_magnitude = (1 << num_bits) - 1  # 127

# ===== 计算 4 个选项 =====
# A: 正确的原码
A = solve_original(truth_value, bits)

# B: 符号位取 0，数值位与 A 相同
A_value_part = A[1:]  # 数值位
B = '0' + A_value_part

# C: 按补码规则转换 -75
C = solve_complement(truth_value, bits)

# D: 绝对值二进制某位翻转（翻转 bit3），补符号位 1
D = solve_with_magnitude_error(truth_value, bits, flip_bit=3)

# ===== 场景规则验证 =====
abs_val = abs(truth_value)
is_in_range = abs_val <= max_magnitude
is_power_of_two = (abs_val & (abs_val - 1)) == 0
all_options = [A, B, C, D]
all_distinct = len(set(all_options)) == 4

# ===== 底部：打印完整数据流 =====
print("=" * 60)
print("PARAMS:")
print("  机器字长: {} 位（{} 位符号 + {} 位数值）".format(bits, 1, num_bits))
print("  十进制真值: {}".format(truth_value))
print("  绝对值: {}".format(abs_val))
print("  8位原码最大可表示绝对值: {}".format(max_magnitude))
print()

print("PROCESS:")
print("  |−75| = 75 的二进制: {} ({} 位数值位)".format(
    format(abs_val, '0{}b'.format(num_bits)), num_bits))
print("  负数 → 符号位 = 1")
print("  原码 A = 符号位 + 数值位 = 1 + {} = {}".format(
    format(abs_val, '0{}b'.format(num_bits)), A))
print()
print("  干扰项 B: 符号位取 0，数值位不变 = 0 + {} = {}".format(A_value_part, B))
print()
print("  干扰项 C: 按补码规则转换 −75")
print("    −75 的 8 位补码: (2^8 + (−75)) = {} → {}".format(
    (1 << bits) + truth_value, C))
print()
print("  干扰项 D: |75| 二进制 bit3(0-indexed) 翻转")
print("    |75| 二进制: {}".format(format(abs_val, '0{}b'.format(num_bits))))
d_abs_bits = list(format(abs_val, '0{}b'.format(num_bits)))
pos_from_left = num_bits - 1 - 3
orig_bit = d_abs_bits[pos_from_left]
d_abs_bits[pos_from_left] = '1' if d_abs_bits[pos_from_left] == '0' else '0'
print("    翻转第 {} 位（从右起）：{} → {}".format(
    3, orig_bit, d_abs_bits[pos_from_left]))
print("    翻转后数值位: {} → 补符号位 1 → {}".format(
    ''.join(d_abs_bits), D))
print()

print("RESULT:")
print("  A = {}  （正确：−75 的 8 位原码）".format(A))
print("  B = {}  （符号位错误：取 0）".format(B))
print("  C = {}  （补码混淆：按补码规则）".format(C))
print("  D = {}  （数值位 bit3 翻转错误）".format(D))
print()

print("RULE_CHECK（场景规则）:")
print("  规则1 表示范围合法: |−75| = {} ≤ {} → {}".format(
    abs_val, max_magnitude, is_in_range))
print("  规则2 绝对值非纯2的幂: {} 是纯2的幂 → {} | 满足(非纯幂)={}".format(
    abs_val, is_power_of_two, not is_power_of_two))
print("  规则3 4选项互异: set(A,B,C,D)={} → 互异={}".format(
    set(all_options), all_distinct))
print("  规则4 正确值唯一: A 唯一确定 = {}".format(A))
print("  规则5 B与A仅符号位不同: A={} B={} → {}".format(
    A, B, A[1:] == B[1:] and A[0] != B[0]))
print("  规则5 C按补码规则: C={}".format(C))
print("  规则5 D与A数值位至少一位不同: A数值位={} D数值位={} → {}".format(
    A[1:], D[1:], A[1:] != D[1:]))

# 通过条件 assert（场景规则，非 answer-recipe）
assert is_in_range, "FAIL: 真值超出 8 位原码表示范围"
assert not is_power_of_two, "FAIL: 绝对值是纯 2 的幂，无出错空间"
assert all_distinct, "FAIL: 存在选项碰撞"
assert A[1:] == B[1:] and A[0] != B[0], "FAIL: B 未与 A 仅符号位不同"
assert C != A, "FAIL: 补码混淆项 C 与原码 A 相同"
assert A[1:] != D[1:], "FAIL: D 数值位与 A 完全相同"
print()
print("ALL_RULES_PASS: True")
