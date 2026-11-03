"""
补码加减运算与溢出判断 —— gen.py
题干：字长 6 位（2 符号位 + 4 数值位）变形补码（双符号位补码）定点小数
  x = -11/16,  y = -7/16
问题1：真值→变形补码
问题2：双符号位加法 x+y
问题3：双符号位溢出判断
"""

from fractions import Fraction

# ============ 参数（题干注入）============
x_val = Fraction(-11, 16)
y_val = Fraction(-7, 16)

NUM_DIGITS = 4                     # 数值位 4 位
TOTAL = 2 + NUM_DIGITS             # 总字长 6 位
MOD = 1 << (TOTAL)                 # = 64，双符号位补码取模空间
FRAC_DEN = 1 << NUM_DIGITS         # = 16，小数分母（分辨率 1/16）


# ============ 辅助函数 ============
def bits_to_str(bits):
    """整数列表 → 二进制字符串"""
    return ''.join(str(b) for b in bits)

def int_to_bits(val, width):
    """非负整数 → 指定宽度二进制列表（高位在前）"""
    return [(val >> (width - 1 - i)) & 1 for i in range(width)]

def sign_extend_value(complement_int, total_bits):
    """
    将 total_bits 位补码整数解释为真值（Fraction）。
    定点小数：小数点在数值位最高位之前。
    6 位格式： s1 s0 . d3 d2 d1 d0  （权值: -2 1 . 1/2 1/4 1/8 1/16）
    真值 = -s1*2 + s0*1 + d3/2 + d2/4 + d1/8 + d0/16
    """
    weights = [Fraction(-2), Fraction(1),
               Fraction(1,2), Fraction(1,4), Fraction(1,8), Fraction(1,16)]
    bits = int_to_bits(complement_int, total_bits)
    val = Fraction(0)
    for b, w in zip(bits, weights):
        val += b * w
    return val


# ============ 问题1：真值 → 变形补码 ============
def true_value_to_deform_complement(val, num_digits):
    """
    真值(定点小数) → 变形补码（双符号位）。
    题干规则：负数符号位为 11，数值位 = 绝对值数值位取反加 1。
    返回 6 位补码整数（用于取模运算），同时返回可读 6 位字符串。
    """
    frac_den = 1 << num_digits
    # 将定点小数真值转为"去掉小数点"的整数（相当于 ×16 取整）
    scaled = int(val * frac_den)            # 真值 × 16 的整数
    deform = scaled % (1 << (num_digits + 2))  # 取模得到双符号位补码整数（mod 64）
    bits = int_to_bits(deform, num_digits + 2)
    return deform, bits_to_str(bits)

# x 变形补码
[x_deform, x_bits_str] = true_value_to_deform_complement(x_val, NUM_DIGITS)
# y 变形补码
[y_deform, y_bits_str] = true_value_to_deform_complement(y_val, NUM_DIGITS)


# ============ 问题2：双符号位加法 x + y ============
def add_two_complement(a_int, b_int, total_bits):
    """
    双符号位补码加法（逐位模拟竖式）。
    返回 (result_int, result_bits_str, carry_out)
    """
    mod = 1 << total_bits
    result = (a_int + b_int) % mod
    bits = int_to_bits(result, total_bits)
    carry_out = 1 if (a_int + b_int) >= mod else 0
    return result, bits_to_str(bits), carry_out

[sum_result, sum_bits_str, cout] = add_two_complement(x_deform, y_deform, TOTAL)


# ============ 问题3：双符号位溢出判断 ============
def detect_overflow_deform(result_int, total_bits):
    """
    双符号位溢出判断：
      双符号位 "01" → 正溢出（上溢）
      双符号位 "10" → 负溢出（下溢）
      "00"/"11"    → 无溢出
    """
    bits = int_to_bits(result_int, total_bits)
    s1, s0 = bits[0], bits[1]          # 双符号位高位、低位
    sign_bits_str = f"{s1}{s0}"
    if s1 != s0:
        overflow = True
        if s1 == 1 and s0 == 0:
            otype = "下溢（负溢出）"
        else:  # s1==0, s0==1
            otype = "上溢（正溢出）"
    else:
        overflow = False
        otype = "无溢出"
    return overflow, otype, sign_bits_str

[overflow, overflow_type, dbl_sign] = detect_overflow_deform(sum_result, TOTAL)


# ============ 验证中间量（用于 solution 转写）============
x_true_check = sign_extend_value(x_deform, TOTAL)   # x 补码还原真值
y_true_check = sign_extend_value(y_deform, TOTAL)   # y 补码还原真值
xy_sum_true = x_val + y_val                         # x+y 真值
result_mod2 = (sum_result % MOD)                    # 运算结果整数
# 条件5描述的还原方式：取双符号位中低位作为有效符号位 + 4位数值位 = 5位单符号位补码
# 按单符号位补码解释真值（符号位权 -1，数值位权 1/2 1/4 1/8 1/16）
def single_sign_value(bits_str):
    """5位单符号位补码定点小数：s.d3d2d1d0, 真值 = -s + d3/2 + d2/4 + d1/8 + d0/16"""
    s = int(bits_str[0])
    d = [int(c) for c in bits_str[1:]]
    weights = [Fraction(-1), Fraction(1,2), Fraction(1,4), Fraction(1,8), Fraction(1,16)]
    val = Fraction(0)
    for b, w in zip([s] + d, weights):
        val += b * w
    return val

eff_bits = sum_bits_str[1:]   # 取低位符号位 + 4数值位 = 5位
result_true_trunc = single_sign_value(eff_bits)

# 逐位竖式加法过程（用于 solution 展示）
xa = int_to_bits(x_deform, TOTAL)
ya = int_to_bits(y_deform, TOTAL)
ra = int_to_bits(sum_result, TOTAL)
carry_trace = []
c = 0
for i in range(TOTAL - 1, -1, -1):
    s = xa[i] + ya[i] + c
    carry_trace.append((i, xa[i], ya[i], c, s % 2, s // 2))
    c = s // 2


# ===================== PRINT =====================
print("=" * 60)
print("PARAMS")
print("=" * 60)
print(f"x 真值 = {x_val} = {float(x_val)}")
print(f"y 真值 = {y_val} = {float(y_val)}")
print(f"数值位 n = {NUM_DIGITS}, 总字长 = {TOTAL}, 模 = {MOD}")
print()

print("=" * 60)
print("REASONING — 问题1：真值→变形补码")
print("=" * 60)
# 数值位细节
x_abs_scaled = int(abs(x_val) * FRAC_DEN)   # |x|×16 = 11
y_abs_scaled = int(abs(y_val) * FRAC_DEN)   # |y|×16 = 7
x_abs_bits = bits_to_str(int_to_bits(x_abs_scaled, NUM_DIGITS))  # 原码数值位
y_abs_bits = bits_to_str(int_to_bits(y_abs_scaled, NUM_DIGITS))
# 取反
x_inv = x_abs_scaled ^ ((1 << NUM_DIGITS) - 1)
y_inv = y_abs_scaled ^ ((1 << NUM_DIGITS) - 1)
x_inv_bits = bits_to_str(int_to_bits(x_inv, NUM_DIGITS))
y_inv_bits = bits_to_str(int_to_bits(y_inv, NUM_DIGITS))
# 取反加1
x_add1 = (x_inv + 1) % (1 << NUM_DIGITS)
y_add1 = (y_inv + 1) % (1 << NUM_DIGITS)
x_add1_bits = bits_to_str(int_to_bits(x_add1, NUM_DIGITS))
y_add1_bits = bits_to_str(int_to_bits(y_add1, NUM_DIGITS))

print(f"[x] 变形补码 = {x_bits_str}")
print(f"  |x| = 11/16, 数值位原码 = {x_abs_bits}")
print(f"  取反 → {x_inv_bits}, 加1 → {x_add1_bits}")
print(f"  符号位 11 + 数值位 {x_add1_bits} = {x_bits_str}")
print()
print(f"[y] 变形补码 = {y_bits_str}")
print(f"  |y| = 7/16, 数值位原码 = {y_abs_bits}")
print(f"  取反 → {y_inv_bits}, 加1 → {y_add1_bits}")
print(f"  符号位 11 + 数值位 {y_add1_bits} = {y_bits_str}")
print()

print("=" * 60)
print("REASONING — 问题2：双符号位加法 x+y")
print("=" * 60)
print(f"  {x_bits_str}   [x]变形补码")
print(f"+ {y_bits_str}   [y]变形补码")
print(f"  ------")
print(f"  {sum_bits_str}   运算结果")
print()
print("逐位运算过程（从低位到高位）：")
print("  位 | x | y | cin | sum | cout")
for pos, xb, yb, cin, s, cout_v in carry_trace:
    print(f"  d{pos} | {xb} | {yb} |  {cin}  |  {s}  |   {cout_v}")
print()
print(f"运算结果双符号位 = '{dbl_sign}'")
print(f"运算结果 6 位 = {sum_bits_str}")
print()

print("=" * 60)
print("REASONING — 问题3：溢出判断")
print("=" * 60)
print(f"双符号位 = '{dbl_sign}'")
print(f"s1={dbl_sign[0]}, s0={dbl_sign[1]}, s1≠s0 → 溢出")
print(f"x+y 真值 = {xy_sum_true} = {float(xy_sum_true)}")
print(f"|x+y| = {abs(xy_sum_true)} > 1, 且 x+y < 0")
print(f"溢出判断：{overflow}")
print(f"溢出类型：{overflow_type}")
print()

print("=" * 60)
print("ANSWER")
print("=" * 60)
print(f"问题1: [x]变形补码 = {x_bits_str}, [y]变形补码 = {y_bits_str}")
print(f"问题2: x+y = {sum_bits_str} (双符号位 '{dbl_sign}')")
print(f"问题3: 发生溢出, 类型 = {overflow_type}")
print()

print("=" * 60)
print("VERIFY DATA")
print("=" * 60)
print(f"x 补码还原真值 = {x_true_check}  (应 = {x_val})")
print(f"y 补码还原真值 = {y_true_check}  (应 = {y_val})")
print(f"x+y 真值 = {xy_sum_true}")
print(f"结果按补码解释真值 = {result_true_trunc}")
print(f"(x+y) mod 2 = {xy_sum_true % 2}")


# ===================== ASSERT（通过条件 → assert）=====================
# 条件1：参数精确可表示（分母整除 2^n，无循环小数）
assert (x_val * FRAC_DEN).denominator == 1, "x 不可精确表示"
assert (y_val * FRAC_DEN).denominator == 1, "y 不可精确表示"

# 条件2：负数补码正确性 —— 补码还原真值 = 原真值；符号位为 11
assert x_true_check == x_val, f"x 变形补码还原值 {x_true_check} ≠ {x_val}"
assert y_true_check == y_val, f"y 变形补码还原值 {y_true_check} ≠ {y_val}"
assert x_bits_str[:2] == "11", "x 为负数，变形补码符号位应为 11"
assert y_bits_str[:2] == "11", "y 为负数，变形补码符号位应为 11"

# 条件3：溢出必然触发 —— 双符号位为 "10"
assert dbl_sign == "10", f"双符号位应为 '10'(负溢出)，实际 '{dbl_sign}'"

# 条件4：溢出类型正确 —— 负溢出（下溢），|x+y|>1 且 x+y<0
assert overflow == True, "应发生溢出"
assert overflow_type == "下溢（负溢出）", f"溢出类型应为下溢，实际 {overflow_type}"
assert abs(xy_sum_true) > 1, f"|x+y| 应 >1，实际 {abs(xy_sum_true)}"
assert xy_sum_true < 0, f"x+y 应 <0，实际 {xy_sum_true}"

# 条件5：结果可还原 —— 结果真值 = (x+y) mod 2
assert result_true_trunc == (xy_sum_true % 2), \
    f"结果真值 {result_true_trunc} ≠ (x+y) mod 2 = {xy_sum_true % 2}"

print()
print("✅ 全部通过条件 assert 通过")
