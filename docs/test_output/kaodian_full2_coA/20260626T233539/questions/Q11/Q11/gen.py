"""
补码加减运算与溢出判断 — gen.py
将题干规则翻译为代码，底部打印完整数据流，并 assert 场景规则。

题干核心：
  - n=3 数据位 + 2 符号位 = 5 位变形补码（双符号位）
  - A=-5, B=-6（均在 n+1=4 位补码范围 [-8,7] 内）
  - 第1问：求 A、B 的变形补码（5位）
  - 第2问：A+B，双符号位判溢（负溢出，结果-11超出[-8,7]）
  - 第3问：A-B = A + (-B)，双符号位判溢（不溢出，结果1在[-8,7]内）

建模方法（整数取模）：
  - 变形补码（双符号位）：总共 n+2=5 位，模 M = 2^5 = 32。
  - 真值 x 的变形补码 = x % M（Python 自动取模）。
  - 加法 = 模 M 整数加法。
  - [-B]变补 由 [B]变补 连同符号位取反加一得到。
  - 双符号位 = 结果最高两位；S1≠S0 则溢出。
  - 有效表示范围 = n+1 位补码范围 = [-2^n, 2^n-1] = [-8, 7]。
"""

n = 3
total_bits = n + 2       # 5
M = 1 << total_bits       # 32

A = -5
B = -6

# 有效表示范围（n+1 位补码，即 n 位数据 + 1 位有效符号）
RANGE_LO = -(1 << n)          # -8
RANGE_HI = (1 << n) - 1       # 7


def true_to_duo(x):
    """真值 -> 变形补码整数（模 M 取模）"""
    return x % M


def duo_bits(val, bits=total_bits):
    """变形补码整数 -> 定长二进制字符串"""
    return format(val, '0{}b'.format(bits))


def invert_add1(val):
    """连同符号位取反加一（对变形补码整体取负）"""
    inverted = (~val) & (M - 1)          # 按位取反（限定 total_bits 位）
    return (inverted + 1) % M


def sign_bits(val):
    """取双符号位 -> (S1, S0)，S1=最高位，S0=次高位"""
    s1 = (val >> (total_bits - 1)) & 1
    s0 = (val >> (total_bits - 2)) & 1
    return s1, s0


def overflow_judge(val):
    """双符号位判溢：S1!=S0 溢出"""
    s1, s0 = sign_bits(val)
    ss = '{}{}'.format(s1, s0)
    if s1 != s0:
        if ss == '01':
            return ('overflow', '正溢出（上溢）')
        else:
            return ('overflow', '负溢出（下溢）')
    else:
        return ('no_overflow', '未溢出')


def to_true(val):
    """变形补码整数（未溢出时）-> 真值"""
    s1, s0 = sign_bits(val)
    if s1 == s0:
        if s1 == 0:
            return val            # 正数
        else:
            return val - M        # 负数（减模）
    else:
        return None               # 溢出，无真值


# ============================================================
# 第 1 问：求 A、B 的变形补码
# ============================================================
A_duo = true_to_duo(A)           # -5 % 32 = 27 = 11011
B_duo = true_to_duo(B)           # -6 % 32 = 26 = 11010

# 取反加一路径验证（n 位绝对值取反加一 + 符号扩展）
A_abs = abs(A)
A_mag_bits = duo_bits(A_abs, n)                              # 5 = 101
A_inv_bits = duo_bits((~A_abs) & ((1 << n) - 1), n)         # 取反 = 010
A_compl_val = ((~A_abs & ((1 << n) - 1)) + 1) % (1 << n)    # 加一 = 011
A_check_duo = (0b11 << n) | A_compl_val                      # 11 011 = 11011

B_abs = abs(B)
B_mag_bits = duo_bits(B_abs, n)
B_inv_bits = duo_bits((~B_abs) & ((1 << n) - 1), n)
B_compl_val = ((~B_abs & ((1 << n) - 1)) + 1) % (1 << n)
B_check_duo = (0b11 << n) | B_compl_val

# ============================================================
# 第 2 问：A + B
# ============================================================
AB_sum = (A_duo + B_duo) % M
AB_true = A + B                        # 真值 = -11
AB_ov = overflow_judge(AB_sum)
AB_range_ok = (RANGE_LO <= AB_true <= RANGE_HI)    # -11 在 [-8,7]? False

# ============================================================
# 第 3 问：A - B = A + (-B)
# ============================================================
# [-B]变补：由 [B]变补 连同符号位取反加一
negB_duo = invert_add1(B_duo)
# 验证：[-B]变补 也应等于 (-B) % M = 6 的变形补码
negB_check = true_to_duo(-B)           # 6 % 32 = 6 = 00110

AB_diff = (A_duo + negB_duo) % M
AB_diff_true = A - B                   # 真值 = 1
AB_diff_ov = overflow_judge(AB_diff)
AB_diff_range_ok = (RANGE_LO <= AB_diff_true <= RANGE_HI)   # 1 在 [-8,7]? True
AB_diff_restored = to_true(AB_diff)    # 未溢出时还原真值

# ============================================================
# 场景规则 assert（翻译 question.md 的 4 条场景规则）
# ============================================================

# 规则1：表示范围约束 — A、B 均在 n 位补码可表示范围内
assert RANGE_LO <= A <= RANGE_HI, "A 超出表示范围"
assert RANGE_LO <= B <= RANGE_HI, "B 超出表示范围"

# 规则2：溢出必现约束 — A+B 和 A-B 中至少一组溢出
assert (not AB_range_ok) or (not AB_diff_range_ok), \
    "A+B 和 A-B 均未溢出，违反溢出必现约束"

# 规则3：减法转加法一致性 — 取反加一路径 == 直接求(-B)变形补码
assert negB_duo == negB_check, \
    "[-B]变补 取反加一路径与直接求(-B)变形补码不一致"
# 未溢出时还原真值 == 真值
assert AB_diff_restored == AB_diff_true, \
    "A-B 未溢出时还原真值与实际真值不一致"

# 规则4：双符号位判溢一致性 — 判溢结论 == 真值是否超出表示范围
assert (AB_ov[0] == 'overflow') == (not AB_range_ok), \
    "A+B 双符号位判溢与真值范围不一致"
assert (AB_diff_ov[0] == 'overflow') == (not AB_diff_range_ok), \
    "A-B 双符号位判溢与真值范围不一致"

# ============================================================
# 底部数据流打印
# ============================================================
print("=" * 60)
print("PARAMS:", {"A": A, "B": B, "n(数据位)": n, "total_bits": total_bits, "M": M})
print("有效表示范围(n+1位补码): [{}, {}]".format(RANGE_LO, RANGE_HI))

print("\n--- 第1问：变形补码 ---")
print("A=-5:")
print("  |A|={} 三位绝对值: {}".format(A_abs, A_mag_bits))
print("  取反: {}".format(A_inv_bits))
print("  加一: {} (3位补码)".format(duo_bits(A_compl_val, n)))
print("  符号扩展(双符号位11): {} -> 5位变形补码 = {}".format(
    duo_bits(A_check_duo), duo_bits(A_duo)))
print("B=-6:")
print("  |B|={} 三位绝对值: {}".format(B_abs, B_mag_bits))
print("  取反: {}".format(B_inv_bits))
print("  加一: {} (3位补码)".format(duo_bits(B_compl_val, n)))
print("  符号扩展(双符号位11): {} -> 5位变形补码 = {}".format(
    duo_bits(B_check_duo), duo_bits(B_duo)))

print("\n--- 第2问：A+B ---")
print("  [A]变补 = {} (={})".format(duo_bits(A_duo), A_duo))
print("  [B]变补 = {} (={})".format(duo_bits(B_duo), B_duo))
print("  逐位相加:")
print("    {} + {} = {} (={}), mod {} = {} (={})".format(
    duo_bits(A_duo), duo_bits(B_duo),
    format(A_duo + B_duo, '0{}b'.format(total_bits + 1)), A_duo + B_duo,
    M, duo_bits(AB_sum), AB_sum))
print("  双符号位 S1S0 = {}".format(
    '{}{}'.format(sign_bits(AB_sum)[0], sign_bits(AB_sum)[1])))
print("  溢出判断: {} {}".format(AB_ov[0], AB_ov[1]))
print("  真值 A+B = {}".format(AB_true))
print("  真值是否超出范围[{},{}]: {} (超出即溢出)".format(
    RANGE_LO, RANGE_HI, not AB_range_ok))

print("\n--- 第3问：A-B ---")
print("  [B]变补   = {} (={})".format(duo_bits(B_duo), B_duo))
print("  取反      = {} (={})".format(
    duo_bits((~B_duo) & (M - 1)), (~B_duo) & (M - 1)))
print("  加一[-B]  = {} (={})".format(duo_bits(negB_duo), negB_duo))
print("  验证(-B直接): {} (={})".format(duo_bits(negB_check), negB_check))
print("  [A]变补   = {} (={})".format(duo_bits(A_duo), A_duo))
print("  逐位相加:")
print("    {} + {} = {} (={}), mod {} = {} (={})".format(
    duo_bits(A_duo), duo_bits(negB_duo),
    format(A_duo + negB_duo, '0{}b'.format(total_bits + 1)), A_duo + negB_duo,
    M, duo_bits(AB_diff), AB_diff))
print("  双符号位 S1S0 = {}".format(
    '{}{}'.format(sign_bits(AB_diff)[0], sign_bits(AB_diff)[1])))
print("  溢出判断: {} {}".format(AB_diff_ov[0], AB_diff_ov[1]))
print("  真值 A-B = {}".format(AB_diff_true))
print("  真值是否超出范围[{},{}]: {}".format(
    RANGE_LO, RANGE_HI, not AB_diff_range_ok))
print("  还原真值(未溢出时): {}".format(AB_diff_restored))

print("\n--- 场景规则验证 ---")
print("规则1 表示范围: A={} in [{},{}]={}, B={} in [{},{}]={}".format(
    A, RANGE_LO, RANGE_HI, RANGE_LO <= A <= RANGE_HI,
    B, RANGE_LO, RANGE_HI, RANGE_LO <= B <= RANGE_HI))
print("规则2 溢出必现: A+B溢出={}, A-B溢出={}, 至少一组={}".format(
    not AB_range_ok, not AB_diff_range_ok,
    (not AB_range_ok) or (not AB_diff_range_ok)))
print("规则3 减法转加法一致性: negB_duo={} == negB_check={} -> {}".format(
    negB_duo, negB_check, negB_duo == negB_check))
print("规则4 双符号位判溢一致性:")
print("  A+B: 双符号位判溢={} | 真值超出范围={} | 一致={}".format(
    AB_ov[0], not AB_range_ok, (AB_ov[0] == 'overflow') == (not AB_range_ok)))
print("  A-B: 双符号位判溢={} | 真值超出范围={} | 一致={}".format(
    AB_diff_ov[0], not AB_diff_range_ok,
    (AB_diff_ov[0] == 'overflow') == (not AB_diff_range_ok)))

print("\n" + "=" * 60)
print("RESULT:")
print("  第1问: [A]变补={}, [B]变补={}".format(
    duo_bits(A_duo), duo_bits(B_duo)))
print("  第2问: [A+B]={}, 双符号位={}, {} ({})".format(
    duo_bits(AB_sum),
    '{}{}'.format(sign_bits(AB_sum)[0], sign_bits(AB_sum)[1]),
    AB_ov[0], AB_ov[1]))
print("  第3问: [A-B]={}, 双符号位={}, {} ({})".format(
    duo_bits(AB_diff),
    '{}{}'.format(sign_bits(AB_diff)[0], sign_bits(AB_diff)[1]),
    AB_diff_ov[0], AB_diff_ov[1]))
if AB_diff_restored is not None:
    print("         A-B真值还原 = {}".format(AB_diff_restored))
print("\n所有场景规则 assert 通过 ✓")
