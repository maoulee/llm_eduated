"""
补码加减运算与溢出判断 —— 双符号位建模
题干规则逐句翻译为代码，底部 print 完整数据流。

双符号位补码小数格式: SS.dddd (2符号位 + 4数值位 = 6位)
6位整数代表 v * 2^4 的补码表示，取模空间 mod = 64。
负数 v 的补码 = (mod + round(v * 2^n)) % mod
"""
from fractions import Fraction

# ============================================================
# 参数（来自题干）
# ============================================================
x_val = Fraction(-11, 16)   # -0.6875 = -0.1011b
y_val = Fraction(-9, 16)    # -0.5625 = -0.1001b
n = 4                       # 数值位数
total_bits = n + 2          # 总位数 = 6（双符号位 + 4 数值位）
mod = 1 << total_bits       # 6 位取模空间 = 64
scale = 1 << n              # 小数→整数的缩放因子 = 16

# ============================================================
# 辅助函数
# ============================================================
def bits_to_str(val_bits, width=total_bits):
    """整数（取模空间内）→ width 位二进制字符串"""
    return format(val_bits % mod, '0{}b'.format(width))

def neg_all(a_bits):
    """连同符号位按位取反再末位加1（=求补/取负操作）→ (mod - a_bits) % mod"""
    return (mod - a_bits) % mod

def negate_numerical_part(true_code_bits):
    """
    由原码求补码（仅对数值部分取反加1，符号位不变）。
    原码格式: 符号位在高位(n+1, n位)，数值部分在低n位。
    对负数: 符号位=11, 数值位=绝对值二进制。
    补码: 符号位不变(11)，数值部分取反加1。
    """
    sign_part = true_code_bits >> n          # 取符号位(高位)
    num_part = true_code_bits & ((1 << n) - 1)  # 取数值部分(低n位)
    # 数值部分取反加1
    num_complement = ((1 << n) - num_part) % (1 << n)  # = 2^n - num_part
    return (sign_part << n) | num_complement

def add_with_carry(a_str, b_str):
    """逐位加法（从低位到高位），返回（和的6位串，步骤列表，最高进位）"""
    assert len(a_str) == len(b_str) == total_bits
    carry = [0] * total_bits
    result = ['0'] * total_bits
    c = 0
    steps = []
    for i in range(total_bits - 1, -1, -1):
        s = int(a_str[i]) + int(b_str[i]) + c
        result[i] = str(s % 2)
        carry[i] = s // 2
        c = s // 2
        steps.append({
            'bit_pos': i,
            'a_bit': a_str[i],
            'b_bit': b_str[i],
            'carry_in': carry[i] if i > 0 else 0,  # carry_in 是进到当前位的
            'carry_out': carry[i],
            'sum': result[i],
        })
    return ''.join(result), steps, c

def carry_in_list(steps):
    """从steps重建每个位的carry_in（实际输入该位的进位）"""
    # steps[0] 是最低位(total_bits-1)，最后一步是最高位0
    # carry_out of step[i] = carry_in of step[i-1]... 不对
    # steps按从低位到高位存，steps[0]=位5(最低)，steps[5]=位0(最高)
    # 初始carry_in[最低位]=0
    c_in = [0] * len(steps)
    c = 0
    for i, st in enumerate(steps):
        c_in[i] = c  # 该位的carry_in = 上一步的carry_out
        c = st['carry_out']
    return c_in

def double_sign_interpret(val_bits):
    """解读双符号位补码小数"""
    s = bits_to_str(val_bits, total_bits)
    sign_str = s[0:2]
    if sign_str == '00':
        sem = Fraction(val_bits, scale)
    elif sign_str == '11':
        sem = Fraction(val_bits - mod, scale)
    else:
        sem = None  # 溢出
    return sign_str, sem

# ============================================================
# 第1问：求 [x]_补 和 [y]_补
# ============================================================
# |x| = 0.1011b, |y| = 0.1001b
x_abs_int = int(abs(x_val) * scale)   # = 11 = 0b1011
y_abs_int = int(abs(y_val) * scale)   # = 9  = 0b1001

# 原码（双符号位）: 负数 → 符号位=11, 数值=绝对值
x_true_code = (0b11 << n) | x_abs_int   # 11_1011 = 59
y_true_code = (0b11 << n) | y_abs_int   # 11_1001 = 57

# 负数补码：符号位不变(11)，数值部分按位取反 + 末位加1
x_num_orig = x_true_code & ((1<<n)-1)         # 1011
x_num_inv = x_num_orig ^ ((1<<n)-1)           # 0100 (取反)
x_num_complement = (x_num_inv + 1) & ((1<<n)-1)  # 0101 (加1)
x_complement = (0b11 << n) | x_num_complement    # 11_0101 = 53

y_num_orig = y_true_code & ((1<<n)-1)         # 1001
y_num_inv = y_num_orig ^ ((1<<n)-1)           # 0110
y_num_complement = (y_num_inv + 1) & ((1<<n)-1)  # 0111
y_complement = (0b11 << n) | y_num_complement    # 11_0111 = 55

# 交叉验证: 补码语义值应 == 原值
_, x_comp_sem = double_sign_interpret(x_complement)
_, y_comp_sem = double_sign_interpret(y_complement)

# SR1: [-v]_补 = [v]_补 连同符号位取反加1 → 对补码整体取负
neg_x_complement = neg_all(x_complement)
neg_y_complement = neg_all(y_complement)

# ============================================================
# 第2问：[x+y]_补 = [x]_补 + [y]_补
# ============================================================
x_comp_str = bits_to_str(x_complement)
y_comp_str = bits_to_str(y_complement)

sum_xy_bits = (x_complement + y_complement) % mod
sum_xy_addstr, sum_xy_steps, sum_xy_final_carry = add_with_carry(x_comp_str, y_comp_str)
sum_xy_str = bits_to_str(sum_xy_bits)
sum_xy_sign, sum_xy_sem = double_sign_interpret(sum_xy_bits)
sr2_overflow = sum_xy_sign not in ('00', '11')

# ============================================================
# 第3问：[x-y]_补 = [x]_补 + [-y]_补
# ============================================================
# [-y]_补 = [y]_补 连同符号位取反加1
neg_y_comp_str = bits_to_str(neg_y_complement)

sum_xmy_bits = (x_complement + neg_y_complement) % mod
sum_xmy_addstr, sum_xmy_steps, sum_xmy_final_carry = add_with_carry(x_comp_str, neg_y_comp_str)
sum_xmy_str = bits_to_str(sum_xmy_bits)
sum_xmy_sign, sum_xmy_sem = double_sign_interpret(sum_xmy_bits)
sr3_no_overflow = sum_xmy_sign in ('00', '11')

# SR4: [y]_补 + [-y]_补 的低6位 = 0
sr4_check = (y_complement + neg_y_complement) % mod

# SR5: 数值精确表示
x_exact = (abs(x_val) * scale).denominator == 1
y_exact = (abs(y_val) * scale).denominator == 1

# SR6: 参数范围
sr6_x = Fraction(1,2) <= abs(x_val) <= Fraction(99,100)
sr6_y = Fraction(1,2) <= abs(y_val) <= Fraction(99,100)

# ============================================================
# 底部：打印完整数据流
# ============================================================
print("=" * 60)
print("PARAMS:")
print("  x_val =", x_val, "=", float(x_val), "= -0.1011b")
print("  y_val =", y_val, "=", float(y_val), "= -0.1001b")
print("  n(数值位数) =", n, " 总位数 =", total_bits, " mod =", mod, " scale =", scale)

print("\n" + "=" * 60)
print("PROCESS [第1问] 求补码:")
print("  |x| = 0.1011b → 4位数值:", format(x_abs_int, '04b'), "(=%d)" % x_abs_int)
print("  |y| = 0.1001b → 4位数值:", format(y_abs_int, '04b'), "(=%d)" % y_abs_int)
print()
print("  --- 求 [x]_补 ---")
print("  x原码(双符号位):", bits_to_str(x_true_code), "= 11." + format(x_abs_int, '04b'))
print("  数值部分取反:   ", format(x_abs_int, '04b'), "→", format(x_num_inv, '04b'))
print("  末位加1:        ", format(x_num_inv, '04b'), "→", format(x_num_complement, '04b'))
print("  [x]_补 =", bits_to_str(x_complement), "(=11." + format(x_num_complement, '04b') + ", 整数=%d)" % x_complement)
print()
print("  --- 求 [y]_补 ---")
print("  y原码(双符号位):", bits_to_str(y_true_code), "= 11." + format(y_abs_int, '04b'))
print("  数值部分取反:   ", format(y_abs_int, '04b'), "→", format(y_num_inv, '04b'))
print("  末位加1:        ", format(y_num_inv, '04b'), "→", format(y_num_complement, '04b'))
print("  [y]_补 =", bits_to_str(y_complement), "(=11." + format(y_num_complement, '04b') + ", 整数=%d)" % y_complement)
print()
print("  SR1验证: [x]_补=%s 语义值=%s (应=%s) → %s" % (
    bits_to_str(x_complement), x_comp_sem, x_val, "OK" if x_comp_sem == x_val else "FAIL"))
print("  SR1验证: [y]_补=%s 语义值=%s (应=%s) → %s" % (
    bits_to_str(y_complement), y_comp_sem, y_val, "OK" if y_comp_sem == y_val else "FAIL"))
print("  SR1验证: [x]_补取负→[%d]=%s 语义值=%s (应为+0.6875)" % (
    neg_x_complement, bits_to_str(neg_x_complement), Fraction(neg_x_complement, scale)))

print("\n" + "=" * 60)
print("PROCESS [第2问] [x+y]_补 加法:")
print("  [x]_补 =", x_comp_str, "(=11.0101)")
print("  [y]_补 =", y_comp_str, "(=11.0111)")
c_in_list = carry_in_list(sum_xy_steps)
print("  逐位加法(高位→低位展示):")
for idx in range(len(sum_xy_steps)-1, -1, -1):
    st = sum_xy_steps[idx]
    print("    位%d: %s + %s + 进位%d = 本位%s, 向高位的进位%d" % (
        st['bit_pos'], st['a_bit'], st['b_bit'], c_in_list[idx], st['sum'], st['carry_out']))
print("  最高位向外进位:", sum_xy_final_carry)
print("  和(6位) =", sum_xy_addstr, "(整数=%d)" % sum_xy_bits)
print("  双符号位 Sf1Sf0 =", sum_xy_sign)
print("  语义值:", sum_xy_sem if sum_xy_sem is not None else "(溢出，无效)")
print("  SR2: x+y溢出 =", sr2_overflow, "(双符号位≠00且≠11 → 溢出)")
if sr2_overflow:
    if sum_xy_sign == '10':
        print("       → 下溢（负溢出）: 两负数相加，结果<-1，超出可表示范围")
    elif sum_xy_sign == '01':
        print("       → 上溢（正溢出）")

print("\n" + "=" * 60)
print("PROCESS [第3问] [x-y]_补 = [x]_补 + [-y]_补:")
print("  [y]_补 =", y_comp_str, "(整数=%d)" % y_complement)
print("  [y]_补连同符号位取反加1(求补):")
print("    取反:", bits_to_str(y_complement ^ (mod-1)), " 加1:", neg_y_comp_str)
print("  [-y]_补 =", neg_y_comp_str, "(整数=%d)" % neg_y_complement, " 语义值=%s" % Fraction(neg_y_complement, scale))
print()
print("  [x]_补 =", x_comp_str)
print("  [-y]_补 =", neg_y_comp_str)
c_in_list2 = carry_in_list(sum_xmy_steps)
print("  逐位加法(高位→低位展示):")
for idx in range(len(sum_xmy_steps)-1, -1, -1):
    st = sum_xmy_steps[idx]
    print("    位%d: %s + %s + 进位%d = 本位%s, 向高位的进位%d" % (
        st['bit_pos'], st['a_bit'], st['b_bit'], c_in_list2[idx], st['sum'], st['carry_out']))
print("  最高位向外进位:", sum_xmy_final_carry)
print("  和(6位) =", sum_xmy_addstr, "(整数=%d)" % sum_xmy_bits)
print("  双符号位 Sf1Sf0 =", sum_xmy_sign)
print("  语义值:", sum_xmy_sem)
print("  SR3: x-y不溢出 =", sr3_no_overflow, "(双符号位∈{00,11} → 无溢出)")

print("\n" + "=" * 60)
print("RESULT:")
print("  [x]_补 =", bits_to_str(x_complement), "= 11.0101 (6位双符号位)")
print("  [y]_补 =", bits_to_str(y_complement), "= 11.0111 (6位双符号位)")
print("  [-y]_补 =", neg_y_comp_str, "= 00.1001 (6位双符号位)")
print("  [x+y]_补 =", sum_xy_str, "双符号位=%s → %s" % (sum_xy_sign, "溢出(下溢)" if sr2_overflow else "无溢出"))
print("  [x-y]_补 =", sum_xmy_str, "双符号位=%s → %s" % (sum_xmy_sign, "无溢出" if sr3_no_overflow else "溢出"))

print("\n" + "=" * 60)
print("SCENARIO_RULE_CHECK:")
print("  SR1(补码可逆): x_comp_sem==x_val:", x_comp_sem == x_val,
      "| y_comp_sem==y_val:", y_comp_sem == y_val)
print("  SR2(x+y溢出): 双符号位=%s, 溢出=%s (应为True)" % (sum_xy_sign, sr2_overflow))
print("  SR3(x-y不溢出): 双符号位=%s, 无溢出=%s (应为True)" % (sum_xmy_sign, sr3_no_overflow))
print("  SR4([-y]正确): [y]_补+[-y]_补 mod %d = %d (应为0)" % (mod, sr4_check))
print("  SR5(精确表示): x_exact=%s, y_exact=%s (均应为True)" % (x_exact, y_exact))
print("  SR6(参数范围): x∈[0.5,0.99]=%s, y∈[0.5,0.99]=%s (均应为True)" % (sr6_x, sr6_y))

# ============================================================
# assert 场景规则（打到特征，非恒真）
# ============================================================
assert x_comp_sem == x_val, "SR1: [x]_补语义值≠x"
assert y_comp_sem == y_val, "SR1: [y]_补语义值≠y"
assert neg_x_complement == x_abs_int, "SR1: [x]_补取负≠[+|x|]补码"
assert sr2_overflow, "SR2: x+y应溢出(双符号位≠00且≠11)"
assert sum_xy_sign == '10', "SR2: 双符号位应=10(下溢)"
assert sr3_no_overflow, "SR3: x-y不应溢出(双符号位∈{00,11})"
assert sum_xmy_sign == '11', "SR3: 双符号位应=11(正常负数)"
assert sr4_check == 0, "SR4: [y]_补+[-y]_补≠0"
assert x_exact and y_exact, "SR5: 数值未精确表示"
assert sr6_x and sr6_y, "SR6: 参数超出范围"

print("\n>>> ALL ASSERTS PASSED <<<")
