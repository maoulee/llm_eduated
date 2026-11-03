# -*- coding: utf-8 -*-
"""
变形补码（双符号位）加减运算与溢出判断
建模：把题干描述的变形补码定义、加法运算、溢出判断规则翻译成代码。
"""
from fractions import Fraction

# ============================================================
# 输入参数（来自题干）
# ============================================================
x_dec = Fraction(-11, 16)   # -0.6875
y_dec = Fraction(-9, 16)    # -0.5625
n = 5  # 小数部分位数

# ============================================================
# 辅助函数
# ============================================================

def dec_to_binary_frac(frac, n):
    """
    十进制分数 → 二进制小数，验证在 n 位内精确终止。
    返回 (二进制字符串, 是否精确, 实际用的位数)
    """
    neg = frac < 0
    val = abs(frac)
    bits = []
    rem = val
    for i in range(n):
        rem = rem * 2
        if rem >= 1:
            bits.append('1')
            rem -= 1
        else:
            bits.append('0')
    exact = (rem == 0)
    # 找到有效位数
    actual_bits = len(bits)
    for i in range(len(bits)-1, -1, -1):
        if bits[i] == '1':
            actual_bits = i + 1
            break
    bit_str = ''.join(bits)
    return bit_str, exact, actual_bits


def to_deformed_complement(frac, n):
    """
    真值 → 变形补码（2位符号位 + n位小数位）
    正数：符号位 00，数值部分 = 原码小数
    负数：符号位 11，数值部分按补码规则求取（取反加一）

    使用取模建模：模 = 2^(n+2)，数值统一编码。
    变形补码编码值 = frac * 2^n + 2^(n+1)（对负数）
    即：把 2 位符号位的补码看作 (n+2) 位补码小数。
    """
    mod = 1 << (n + 2)  # 7位编码空间的模 = 128
    # 真值 * 2^n 得到整数编码值（带符号）
    scaled = frac * (1 << n)  # frac * 2^n
    code = int(scaled) % mod   # 变形补码编码值（mod 2^(n+2)）
    return code, mod


def code_to_bits(code, n):
    """编码值 → 2位符号位 + n位小数位的二进制字符串"""
    total = n + 2
    return format(code, '0{}b'.format(total))


def restore_value(code, n):
    """变形补码编码值 → 真值（符号位→真值还原）"""
    total = n + 2
    mod = 1 << total
    val = code
    if val >= (mod >> 1):  # 最高位为1 → 负数补码
        val = val - mod
    return Fraction(val, 1 << n)


def add_deformed(code_a, code_b, n):
    """变形补码加法：取模相加"""
    mod = 1 << (n + 2)
    return (code_a + code_b) % mod


def check_overflow(code_result, n):
    """
    溢出判断：双符号位相同→未溢出；不同→溢出
    双符号位 = code 的最高2位
    """
    total = n + 2
    bits = format(code_result, '0{}b'.format(total))
    s1 = bits[0]  # 最高符号位
    s0 = bits[1]  # 次高符号位
    overflow = (s1 != s0)
    return overflow, bits

# ============================================================
# 第 1 问：x + y 的变形补码运算
# ============================================================
print("=" * 60)
print("第 1 问：x + y")
print("=" * 60)

# --- 1a. 十进制转二进制 ---
x_bits_str, x_exact, x_nbits = dec_to_binary_frac(x_dec, n)
y_bits_str, y_exact, y_nbits = dec_to_binary_frac(y_dec, n)

print("\n[1a] 十进制小数转二进制")
print(f"  |x| = {abs(x_dec)} → 0.{x_bits_str}, 精确={x_exact}, 实用位数={x_nbits}")
print(f"  x = -0.{x_bits_str[:x_nbits]}")
print(f"  |y| = {abs(y_dec)} → 0.{y_bits_str}, 精确={y_exact}, 实用位数={y_nbits}")
print(f"  y = -0.{y_bits_str[:y_nbits]}")

# --- 1b. 变形补码 ---
x_code, mod = to_deformed_complement(x_dec, n)
y_code, _ = to_deformed_complement(y_dec, n)

print("\n[1b] 变形补码")
print(f"  [x]变形补码 编码值 = {x_code} = 0b{code_to_bits(x_code, n)} → 11.{code_to_bits(x_code, n)[2:]}")
print(f"  [y]变形补码 编码值 = {y_code} = 0b{code_to_bits(y_code, n)} → 11.{code_to_bits(y_code, n)[2:]}")

# --- 1c. 变形补码加法 ---
sum1_code = add_deformed(x_code, y_code, n)
print("\n[1c] 变形补码加法")
print(f"  [x]变形补码 = {code_to_bits(x_code, n)}")
print(f"  [y]变形补码 = {code_to_bits(y_code, n)}")
print(f"  编码值和   = {x_code} + {y_code} = {x_code + y_code}")
print(f"  取模 mod={mod} → {sum1_code}")
print(f"  结果编码   = {code_to_bits(sum1_code, n)}")

# --- 1d. 溢出判断 ---
overflow1, bits1 = check_overflow(sum1_code, n)
s1_1, s0_1 = bits1[0], bits1[1]
print("\n[1d] 溢出判断")
print(f"  结果双符号位: S1={s1_1}, S0={s0_1}")
print(f"  符号位{'不同' if overflow1 else '相同'} → {'溢出' if overflow1 else '未溢出'}")

if not overflow1:
    val1 = restore_value(sum1_code, n)
    print(f"  结果真值 = {val1} = {float(val1)}")

# ============================================================
# 第 2 问：x - y = x + [-y]变形补码
# ============================================================
print("\n" + "=" * 60)
print("第 2 问：x - y")
print("=" * 60)

# --- 2a. 求 [-y] ---
neg_y_dec = -y_dec  # y的相反数的真值
neg_y_code, _ = to_deformed_complement(neg_y_dec, n)

print("\n[2a] 求 [-y]")
print(f"  -y 的真值 = {neg_y_dec} = {float(neg_y_dec)}")
neg_y_bits_str, _, neg_y_nbits = dec_to_binary_frac(neg_y_dec, n)
print(f"  -y = 0.{neg_y_bits_str[:neg_y_nbits]}")
print(f"  [-y]变形补码 编码值 = {neg_y_code} = 0b{code_to_bits(neg_y_code, n)} → 00.{code_to_bits(neg_y_code, n)[2:]}")

# --- 2b. 变形补码加法 ---
sum2_code = add_deformed(x_code, neg_y_code, n)
print("\n[2b] 变形补码加法 x + [-y]")
print(f"  [x]变形补码   = {code_to_bits(x_code, n)}")
print(f"  [-y]变形补码  = {code_to_bits(neg_y_code, n)}")
print(f"  编码值和     = {x_code} + {neg_y_code} = {x_code + neg_y_code}")
print(f"  取模 mod={mod} → {sum2_code}")
print(f"  结果编码     = {code_to_bits(sum2_code, n)}")

# --- 2c. 溢出判断 ---
overflow2, bits2 = check_overflow(sum2_code, n)
s1_2, s0_2 = bits2[0], bits2[1]
print("\n[2c] 溢出判断")
print(f"  结果双符号位: S1={s1_2}, S0={s0_2}")
print(f"  符号位{'不同' if overflow2 else '相同'} → {'溢出' if overflow2 else '未溢出'}")

if not overflow2:
    val2 = restore_value(sum2_code, n)
    print(f"  结果真值 = {val2} = {float(val2)}")

# ============================================================
# 场景规则验证（通过条件）
# ============================================================
print("\n" + "=" * 60)
print("场景规则验证")
print("=" * 60)

# 规则1: 二进制精确性
print("\n[规则1] 二进制精确性（≤5位精确终止）")
print(f"  x 二进制: 0.{x_bits_str}, 精确={x_exact}, 实用位数={x_nbits}")
print(f"  y 二进制: 0.{y_bits_str}, 精确={y_exact}, 实用位数={y_nbits}")
assert x_exact and y_exact, "规则1失败：二进制非精确"
assert x_nbits <= n and y_nbits <= n, "规则1失败：超出5位"
print("  ✓ 通过")

# 规则2: 变形补码还原一致性
print("\n[规则2] 变形补码还原一致性（符号位→真值 = 原始十进制）")
x_restored = restore_value(x_code, n)
y_restored = restore_value(y_code, n)
neg_y_restored = restore_value(neg_y_code, n)
print(f"  [x]还原 = {x_restored} == {x_dec} ? {x_restored == x_dec}")
print(f"  [y]还原 = {y_restored} == {y_dec} ? {y_restored == y_dec}")
print(f"  [-y]还原 = {neg_y_restored} == {neg_y_dec} ? {neg_y_restored == neg_y_dec}")
assert x_restored == x_dec, "规则2失败：[x]还原不一致"
assert y_restored == y_dec, "规则2失败：[y]还原不一致"
assert neg_y_restored == neg_y_dec, "规则2失败：[-y]还原不一致"
print("  ✓ 通过")

# 规则3: 溢出判定逻辑一致性（无溢出时真值 = 数学精确值）
print("\n[规则3] 溢出判定逻辑一致性")
# 第1问
math_sum1 = x_dec + y_dec
if not overflow1:
    val1_restored = restore_value(sum1_code, n)
    print(f"  第1问: 未溢出, 还原真值={val1_restored}, 数学值={math_sum1}, 一致={val1_restored == math_sum1}")
    assert val1_restored == math_sum1, "规则3失败：第1问无溢出但真值不一致"
else:
    print(f"  第1问: 溢出（双符号位{s1_1}{s0_1}），无需还原真值")
# 第2问
math_diff = x_dec - y_dec
if not overflow2:
    val2_restored = restore_value(sum2_code, n)
    print(f"  第2问: 未溢出, 还原真值={val2_restored}, 数学值={math_diff}, 一致={val2_restored == math_diff}")
    assert val2_restored == math_diff, "规则3失败：第2问无溢出但真值不一致"
else:
    print(f"  第2问: 溢出（双符号位{s1_2}{s0_2}），无需还原真值")
print("  ✓ 通过")

# 规则4: 一溢一不溢
print("\n[规则4] 一溢一不溢约束")
print(f"  第1问溢出={overflow1}, 第2问溢出={overflow2}")
assert overflow1 != overflow2, "规则4失败：两问溢出状态相同（需一溢一不溢）"
print(f"  ✓ 通过（{'第1问溢出' if overflow1 else '第2问溢出'}，{'第2问不溢出' if overflow1 else '第1问不溢出'}）")

# 规则5: 减法求补正确性（[-y] + [y] = 0 mod 模）
print("\n[规则5] 减法求补正确性（[-y]变形补码 + [y]变形补码 = 0 mod 模）")
check5 = (neg_y_code + y_code) % mod
print(f"  ({neg_y_code} + {y_code}) mod {mod} = {check5}")
assert check5 == 0, "规则5失败：[-y]+[y]≠0"
print("  ✓ 通过")

# ============================================================
# 完整数据流汇总
# ============================================================
print("\n" + "=" * 60)
print("DATA FLOW SUMMARY")
print("=" * 60)
print(f"PARAMS: x={x_dec}={float(x_dec)}, y={y_dec}={float(y_dec)}, n={n}")
print(f"  x 二进制 = -0.{x_bits_str[:x_nbits]}")
print(f"  y 二进制 = -0.{y_bits_str[:y_nbits]}")
print(f"  [x]变形补码 = {code_to_bits(x_code, n)}")
print(f"  [y]变形补码 = {code_to_bits(y_code, n)}")
print(f"  [-y]变形补码 = {code_to_bits(neg_y_code, n)}")
print(f"Q1 (x+y): sum_code={sum1_code}, bits={code_to_bits(sum1_code, n)}, overflow={overflow1}")
print(f"  math_value(x+y) = {float(math_sum1)}")
print(f"Q2 (x-y): sum_code={sum2_code}, bits={code_to_bits(sum2_code, n)}, overflow={overflow2}")
print(f"  math_value(x-y) = {float(math_diff)}")
if not overflow2:
    print(f"  Q2 result true value = {float(restore_value(sum2_code, n))}")

print("\n所有场景规则验证通过 ✓")
