"""
变形补码（双符号位补码）加减运算与溢出判断 —— 代码翻译
题干：x=11/16, y=7/16，4位小数部分 + 2位符号位 = 6位变形补码
建模方式：整数取模（6位 = mod 64），变形补码 = 正数00前缀，负数11前缀（补码值 = mod + 真值）
"""
import math

N = 6  # 总位数（2位符号位 + 4位小数部分）
MOD = 1 << N  # 64

x_val = 11 / 16  # 真值
y_val = 7 / 16   # 真值


def to_bianbu(val, n=N):
    """定点小数 → 变形补码（整数表示）。正数00前缀，负数11前缀(补码值=MOD+真值)。"""
    scaled = val * (1 << (n - 2))  # 放大到整数（乘以16）
    assert abs(scaled - round(scaled)) < 1e-9, f"无法精确表示: {val}"
    scaled = round(scaled)
    if val >= 0:
        return int(scaled) % MOD  # 正数：前缀00，低位=|x|
    else:
        return (MOD + int(scaled)) % MOD  # 负数：补码 = MOD - |x|，前缀11


def negate_bianbu(code, n=N):
    """场景规则3：[-y]变补 = [y]变补 全部位取反后最低位加1"""
    mask = (1 << n) - 1
    return ((~code & mask) + 1) % MOD


def add_bianbu(code_a, code_b, n=N):
    """变形补码加法（取模 n 位）"""
    return (code_a + code_b) % MOD


def get_sign_bits(code, n=N):
    """取双符号位（最高2位）"""
    return code >> (n - 2)


def overflow_info(code, n=N):
    """双符号位判溢出：两位不一致→溢出；01→上溢，10→下溢"""
    s = get_sign_bits(code, n)
    bits = format(s, '02b')
    if bits[0] == bits[1]:
        return False, "不溢出（双符号位一致: %s）" % bits
    elif bits == '01':
        return True, "上溢（符号位01）"
    elif bits == '10':
        return True, "下溢（符号位10）"
    return False, "不溢出"


def bits_str(code, n=N):
    """格式化为 n 位二进制串"""
    return format(code, '0{}b'.format(n))


# ============================================================
# 第(1)题：求 [x]变补 与 [y]变补
# ============================================================
x_code = to_bianbu(x_val)
y_code = to_bianbu(y_val)

# ============================================================
# 第(2)题：x + y
# ============================================================
sum_code = add_bianbu(x_code, y_code)
sum_overflow, sum_type = overflow_info(sum_code)
sum_sign = get_sign_bits(sum_code)

# ============================================================
# 第(3)题：x - y = [x]变补 + [-y]变补
# ============================================================
neg_y_code = negate_bianbu(y_code)
sub_code = add_bianbu(x_code, neg_y_code)
sub_overflow, sub_type = overflow_info(sub_code)
sub_sign = get_sign_bits(sub_code)

# ============================================================
# 场景规则验证（忠实实现并 print 对应量）
# ============================================================
# 规则1：精确可表示性
x_int = x_val * 16
y_int = y_val * 16
rule1 = (abs(x_int - round(x_int)) < 1e-9) and (abs(y_int - round(y_int)) < 1e-9)

# 规则2：恰好一组溢出
rule2 = (sum_overflow != sub_overflow)  # XOR：恰好一组溢出

# 规则3：[-y]变补 = 全部位取反+1；x-y = [x]+[-y]
neg_y_check = negate_bianbu(y_code)
sub_check = add_bianbu(x_code, neg_y_check)
rule3 = (neg_y_check == neg_y_code) and (sub_check == sub_code)

# 规则4：溢出那组符号位01（上溢）；不溢出那组两位一致
if sum_overflow:
    rule4 = (get_sign_bits(sum_code) == 0b01) and \
            (get_sign_bits(sub_code) in [0b00, 0b11])
else:
    rule4 = (get_sign_bits(sub_code) == 0b01) and \
            (get_sign_bits(sum_code) in [0b00, 0b11])

# ============================================================
# 底部数据流 print（PARAMS / PROCESS / RESULT + 场景规则量）
# ============================================================
print("=" * 60)
print("PARAMS:")
print("  x =", x_val, "=", "11/16")
print("  y =", y_val, "=", "7/16")
print("  总位数 N =", N, "（2位符号位 + 4位小数部分）")
print("  MOD =", MOD)
print("=" * 60)
print("PROCESS:")
print("  [第(1)题] 求变形补码：")
print("    x_scaled = x*16 =", x_int, "→ 二进制小数部分:", format(round(x_int), '04b'))
print("    [x]变补 =", bits_str(x_code), "(数值=%d)" % x_code)
print("    y_scaled = y*16 =", y_int, "→ 二进制小数部分:", format(round(y_int), '04b'))
print("    [y]变补 =", bits_str(y_code), "(数值=%d)" % y_code)
print()
print("  [第(2)题] x + y 变形补码加法：")
print("    [x]变补 =", bits_str(x_code))
print("  + [y]变补 =", bits_str(y_code))
print("  --------------------------------")
print("    和(6位) =", bits_str(sum_code), "(数值=%d)" % sum_code)
print("    双符号位 =", format(sum_sign, '02b'), "→", sum_type)
print()
print("  [第(3)题] x - y 变形补码减法：")
print("    [y]变补  =", bits_str(y_code))
print("    [-y]变补 = [y]全部位取反+1 =", bits_str(neg_y_code), "(数值=%d)" % neg_y_code)
print("    [x]变补  =", bits_str(x_code))
print("  + [-y]变补 =", bits_str(neg_y_code))
print("  --------------------------------")
print("    差(6位) =", bits_str(sub_code), "(数值=%d)" % sub_code)
print("    双符号位 =", format(sub_sign, '02b'), "→", sub_type)
print()
print("  [真值验证]")
print("    x+y 真值 =", x_val + y_val, "→", "溢出" if x_val + y_val > 1 or x_val + y_val < -1 else "不溢出")
print("    x-y 真值 =", x_val - y_val, "→", "溢出" if x_val - y_val > 1 or x_val - y_val < -1 else "不溢出")
print()
print("RESULT:")
print("  (1) [x]变补 =", bits_str(x_code), ", [y]变补 =", bits_str(y_code))
print("  (2) x+y 变形补码和 =", bits_str(sum_code), ",", sum_type)
print("  (3) [-y]变补 =", bits_str(neg_y_code), ", x-y 变形补码差 =", bits_str(sub_code), ",", sub_type)
print()
print("RULE_CHECK（场景规则）:")
print("  规则1 精确可表示性: x*16=%d, y*16=%d 均为整数 → %s" % (round(x_int), round(y_int), rule1))
print("  规则2 恰好一组溢出: x+y溢出=%s, x-y溢出=%s → 恰好一组=%s" % (sum_overflow, sub_overflow, rule2))
print("  规则3 运算一致性: [-y]=取反加1=%s, x-y=[x]+[-y]=%s → %s" % (neg_y_code == negate_bianbu(y_code), sub_code == add_bianbu(x_code, neg_y_code), rule3))
print("  规则4 溢出判定可区分: 溢出组符号位=01(上溢), 不溢出组符号位一致 → %s" % rule4)
