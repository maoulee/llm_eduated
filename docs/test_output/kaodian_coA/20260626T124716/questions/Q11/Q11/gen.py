"""
补码加减运算与双符号位溢出判断
A = -50, B = -40, n = 7 (1 符号位 + 6 数据位)
双符号位(变形补码): 7 位扩展为 8 位 (2 符号位 + 6 数据位)
"""


def to_complement_double(value, n_data=6):
    """
    求一个整数的双符号位变形补码（8 位: 2 符号位 + n_data 数据位）。
    返回 8 位二进制字符串。
    """
    total_bits = 2 + n_data  # 8
    mod = 1 << (2 + n_data)   # 256
    unsigned = value % mod    # 取补码的无符号值
    bits = format(unsigned, '0{}b'.format(total_bits))
    return bits


def full_add_bits(a_str, b_str):
    """
    逐位相加两个等长二进制串（含进位），返回:
    - sum_bits: 和的二进制串（同宽度）
    - carry_in_to_s0: 最高位的进位输出（用于参考）
    - 逐位加法过程列表
    """
    width = len(a_str)
    a = [int(c) for c in a_str]
    b = [int(c) for c in b_str]

    carry = 0
    steps = []
    result = [0] * width

    for i in range(width - 1, -1, -1):
        s = a[i] + b[i] + carry
        result[i] = s % 2
        carry = s // 2
        steps.append((i, a[i], b[i], carry, result[i]))

    # 最终进位（最高位进位输出）
    final_carry = carry
    sum_bits = ''.join(str(x) for x in result)
    return sum_bits, final_carry, steps


def judge_overflow_double_sign(sum_bits):
    """
    双符号位溢出判断:
    - 00 或 11 → 不溢出
    - 01 → 正溢出
    - 10 → 负溢出
    """
    s1, s0 = int(sum_bits[0]), int(sum_bits[1])
    if s1 == s0:
        return False, "不溢出"
    else:
        if s1 == 0 and s0 == 1:
            return True, "正溢出"
        else:  # s1==1, s0==0
            return True, "负溢出"


def interpret_value(bits_8, n_data=6):
    """
    将 8 位双符号位补码解释为真值（如果未溢出）。
    00xxxxxx → 正数, 11xxxxxx → 负数。
    """
    sign = bits_8[0]
    unsigned_val = int(bits_8, 2)
    mod = 1 << (2 + n_data)
    if sign == '0':
        return unsigned_val
    else:
        return unsigned_val - mod


# ========== 参数 ==========
A = -50
B = -40
n = 7
n_data = n - 1  # 6

print("=" * 60)
print("PARAMS")
print("=" * 60)
print(f"A = {A}")
print(f"B = {B}")
print(f"机器字长 n = {n} (1 符号位 + {n_data} 数据位)")
print(f"双符号位扩展: 2 符号位 + {n_data} 数据位 = {2 + n_data} 位")
print(f"表示范围: [-{2**(n-1)}, {2**(n-1) - 1}] = [-{2**(n-1)}, {2**(n-1)-1}]")
print()

# ========== 第(1)问: A + B ==========
print("=" * 60)
print("REASONING — 第(1)问: A + B")
print("=" * 60)

# 求 [A]补 变形补码, [B]补 变形补码
A_comp = to_complement_double(A, n_data)
B_comp = to_complement_double(B, n_data)

absA_bin = format(abs(A), '0{}b'.format(n_data))
absA_inv = format(abs(A) ^ ((1 << n_data) - 1), '0{}b'.format(n_data))
absA_pl1 = format(((abs(A) ^ ((1 << n_data) - 1)) + 1) & ((1 << n_data) - 1), '0{}b'.format(n_data))
print(f"\n[A]补 (变形补码, 8位):")
print(f"  A = {A}")
print(f"  |A| = {abs(A)} = {absA_bin} ({n_data}位)")
print(f"  |A| 取反: {absA_inv}")
print(f"  末位加1:  {absA_pl1}")
print(f"  符号位 11 + 数据位 → {A_comp}")
print(f"  [A]补 = {A_comp}")

absB_bin = format(abs(B), '0{}b'.format(n_data))
absB_inv = format(abs(B) ^ ((1 << n_data) - 1), '0{}b'.format(n_data))
absB_pl1 = format(((abs(B) ^ ((1 << n_data) - 1)) + 1) & ((1 << n_data) - 1), '0{}b'.format(n_data))
print(f"\n[B]补 (变形补码, 8位):")
print(f"  B = {B}")
print(f"  |B| = {abs(B)} = {absB_bin} ({n_data}位)")
print(f"  |B| 取反: {absB_inv}")
print(f"  末位加1:  {absB_pl1}")
print(f"  符号位 11 + 数据位 → {B_comp}")
print(f"  [B]补 = {B_comp}")

print(f"\n逐位相加过程:")
print(f"    {A_comp}")
print(f"  + {B_comp}")
print(f"  --------")

sum_ab, carry_ab, steps_ab = full_add_bits(A_comp, B_comp)
print(f"  = {sum_ab}")
print(f"  最高位进位输出 = {carry_ab}")
print(f"\n双符号位 = '{sum_ab[0]}{sum_ab[1]}'")

overflow_ab, overflow_type_ab = judge_overflow_double_sign(sum_ab)
print(f"溢出判断: {overflow_type_ab}")
print(f"溢出标志 = {overflow_ab}")

if overflow_ab:
    print(f"(A+B 的真实数学值 = {A+B}, 超出范围 [-{2**(n-1)}, {2**(n-1)-1}], 溢出)")
else:
    val_ab = interpret_value(sum_ab, n_data)
    print(f"结果真值 = {val_ab}")
    print(f"验证: A+B = {A}+({B}) = {A+B} ✓")

# ========== 第(2)问: A - B ==========
print()
print("=" * 60)
print("REASONING — 第(2)问: A - B")
print("=" * 60)

# [-B]补 = ~[B]补(全部8位取反) + 1
print(f"\n[-B]补 由 [B]补 连同符号位全部取反末位加一得到:")
print(f"  [B]补 = {B_comp}")
B_all_inv = ''.join('1' if c == '0' else '0' for c in B_comp)
print(f"  全部取反 = {B_all_inv}")
# 末位加1
neg_B_int = (int(B_all_inv, 2) + 1) & ((1 << 8) - 1)
negB_comp = format(neg_B_int, '08b')
print(f"  末位加1 = {negB_comp}")
print(f"  [-B]补 = {negB_comp}")
print(f"  验证: [-B]补 对应真值 = {interpret_value(negB_comp, n_data)} = -(-40) = 40 ✓")

print(f"\n逐位相加过程 [A]补 + [-B]补:")
print(f"    {A_comp}")
print(f"  + {negB_comp}")
print(f"  --------")

sum_asub, carry_asub, steps_asub = full_add_bits(A_comp, negB_comp)
print(f"  = {sum_asub}")
print(f"  最高位进位输出 = {carry_asub}")
print(f"\n双符号位 = '{sum_asub[0]}{sum_asub[1]}'")

overflow_asub, overflow_type_asub = judge_overflow_double_sign(sum_asub)
print(f"溢出判断: {overflow_type_asub}")
print(f"溢出标志 = {overflow_asub}")

if not overflow_asub:
    val_asub = interpret_value(sum_asub, n_data)
    print(f"结果真值 = {val_asub}")
    print(f"验证: A-B = {A}-({B}) = {A-B} ✓")
else:
    print(f"(A-B 的真实数学值 = {A-B})")

# ========== ANSWER ==========
print()
print("=" * 60)
print("ANSWER")
print("=" * 60)
print(f"(1) [A]补 = {A_comp}, [B]补 = {B_comp}")
print(f"    A+B 逐位和 = {sum_ab}, 双符号位 '{sum_ab[0]}{sum_ab[1]}'")
print(f"    {overflow_type_ab} (溢出={overflow_ab})")
print(f"(2) [-B]补 = {negB_comp}")
print(f"    A-B 逐位和 = {sum_asub}, 双符号位 '{sum_asub[0]}{sum_asub[1]}'")
print(f"    {overflow_type_asub} (溢出={overflow_asub})")
if not overflow_asub:
    print(f"    A-B 结果真值 = {interpret_value(sum_asub, n_data)}")

# ========== ASSERTS (通过条件翻译) ==========

# 通过条件1: A+B 必然溢出，双符号位不一致 (01 或 10)
assert abs(A) + abs(B) == 90, f"|A|+|B| should be 90"
assert 90 > 2**(n-1), "A+B should overflow: 90 > 64"
assert overflow_ab == True, f"A+B must overflow, got overflow={overflow_ab}"
assert sum_ab[0] != sum_ab[1], f"A+B double sign must be inconsistent (01 or 10), got '{sum_ab[0]}{sum_ab[1]}'"

# 通过条件2: A-B 不溢出，双符号位一致 (00 或 11)
assert abs(abs(A) - abs(B)) == 10, f"||A|-|B|| should be 10"
assert 10 < 2**(n-1), "A-B should NOT overflow: 10 < 64"
assert overflow_asub == False, f"A-B must NOT overflow, got overflow={overflow_asub}"
assert sum_asub[0] == sum_asub[1], f"A-B double sign must be consistent (00 or 11), got '{sum_asub[0]}{sum_asub[1]}'"

# A-B 结果验证
assert interpret_value(sum_asub, n_data) == A - B, f"A-B result should be {A-B}"

# 通过条件3: [-B]补 转换正确 — 连同符号位全部取反加一
# 用正确方法得到的 negB_comp 必须等于用取模法验证的值
negB_check = to_complement_double(-B, n_data)  # -B = 40 的变形补码
assert negB_comp == negB_check, f"[-B]补 mismatch: method={negB_comp}, check={negB_check}"
# 解释为真值应为 40
assert interpret_value(negB_comp, n_data) == 40, f"[-B]补 should represent 40"

# 补码逐位验证: [A]补 和 [B]补 本身正确
assert interpret_value(A_comp, n_data) == A, f"[A]补 wrong"
assert interpret_value(B_comp, n_data) == B, f"[B]补 wrong"

print()
print("✅ 所有 assert 通过 — 通过条件全部满足")
