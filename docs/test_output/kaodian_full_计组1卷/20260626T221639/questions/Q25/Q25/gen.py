"""
补码加减运算与溢出判断
A = 0x9C (-100), B = 0xD8 (-40), n=8
"""
n = 8
mod = 1 << n  # 256

A_byte = 0x9C
B_byte = 0xD8

# ---- 8位补码 → 十进制 ----
def to_signed(byte_val, nbits=8):
    if byte_val >= (1 << (nbits - 1)):
        return byte_val - (1 << nbits)
    return byte_val

A_dec = to_signed(A_byte, n)
B_dec = to_signed(B_byte, n)

# ---- 双符号位法（变形补码法）----
def double_sign(byte_val, nbits=8):
    """取 8 位补码的最高位（符号位），扩展为 2 位符号位，返回 9~10 位整数表示"""
    s = (byte_val >> (nbits - 1)) & 1  # 原符号位
    extended = (s << nbits) | byte_val  # 符号位扩展: 0x000~0x0FF 或 0x100~0x1FF
    return extended

def add_double_sign(x_byte, y_byte, nbits=8):
    """双符号位法加法判断溢出"""
    dx = double_sign(x_byte, nbits)
    dy = double_sign(y_byte, nbits)
    raw = dx + dy
    trunc = raw & ((1 << (nbits + 1)) - 1)  # 取低 9 位（含2符号位）
    s_hi = (trunc >> nbits) & 1
    s_lo = (trunc >> (nbits - 1)) & 1
    overflow = (s_hi != s_lo)  # 双符号位不同 → 溢出
    result_byte = trunc & ((1 << nbits) - 1)
    return {
        "变形补码_x": dx,
        "变形补码_y": dy,
        "加法原始值": raw,
        "截断(双符号位域)": trunc,
        "双符号位": (s_hi, s_lo),
        "双符号位相同": s_hi == s_lo,
        "溢出": overflow,
        "结果8位": result_byte,
    }

# ---- 进位判别法 ----
def carry_overflow(x_byte, y_byte, nbits=8):
    """进位判别法：溢出 = 最高位进位 ⊕ 次高位进位"""
    raw = x_byte + y_byte
    carry_into_sign = (x_byte + y_byte) >> nbits & 1           # 最高位向外的进位
    # 次高位进位：看 bit6 相加产生的进位
    low_mask = (1 << (nbits - 1)) - 1   # 低7位掩码
    carry_out_of_bit6 = ((x_byte & low_mask) + (y_byte & low_mask)) >> (nbits - 1) & 1
    carry_out_of_sign = raw >> nbits & 1
    overflow = (carry_out_of_sign != carry_out_of_bit6)
    result_byte = raw & ((1 << nbits) - 1)
    return {
        "最高位进位Cs": carry_out_of_sign,
        "次高位进位Cp": carry_out_of_bit6,
        "Cs_xor_Cp": carry_out_of_sign ^ carry_out_of_bit6,
        "溢出": overflow,
        "结果8位": result_byte,
    }

# =====================================================
#  第(1)题：[A+B]补 + 溢出判断
# =====================================================
AplusB_raw = A_byte + B_byte
AplusB_byte = AplusB_raw & (mod - 1)       # mod 256 截断
AplusB_double = add_double_sign(A_byte, B_byte, n)
AplusB_carry = carry_overflow(A_byte, B_byte, n)

# =====================================================
#  第(2)题：[−B]补 → [A−B]补 + 溢出判断
# =====================================================
negB_byte = ((~B_byte) + 1) & (mod - 1)     # [−B]补 = ~B + 1
AminusB_raw = A_byte + negB_byte
AminusB_byte = AminusB_raw & (mod - 1)
AminusB_double = add_double_sign(A_byte, negB_byte, n)
AminusB_carry = carry_overflow(A_byte, negB_byte, n)

# ---- 真实值（用于溢出说明）----
real_sum = A_dec + B_dec        # 真实和
real_diff = A_dec - B_dec       # 真实差

# ---- result 截断后的十进制值 ----
result_sum_signed = to_signed(AplusB_byte, n)
result_diff_signed = to_signed(AminusB_byte, n)

# =====================================================
#  打印完整数据流
# =====================================================
print("=" * 60)
print("PARAMS:")
print("  n =", n, " mod =", mod)
print("  [A]补 = 0x%02X → A_decimal = %d" % (A_byte, A_dec))
print("  [B]补 = 0x%02X → B_decimal = %d" % (B_byte, B_dec))
print()

print("=" * 60)
print("第(1)题 [A+B]补:")
print("-" * 40)
print("PROCESS:")
print("  真实值 A+B = %d + %d = %d" % (A_dec, B_dec, real_sum))
print("  表示范围: [-128, +127] → 真实值 %d 超出范围 → 溢出" % real_sum)
print()
print("  模256加法: 0x%02X + 0x%02X = 0x%03X → 截断8位 = 0x%02X" % (A_byte, B_byte, AplusB_raw, AplusB_byte))
print()

print("  【双符号位法】:")
for k, v in AplusB_double.items():
    print("    %s = %s" % (k, v))
print()

print("  【进位判别法】:")
for k, v in AplusB_carry.items():
    print("    %s = %s" % (k, v))
print()

print("RESULT_Q1:")
print("  [A+B]补 = 0x%02X (十进制: %d)" % (AplusB_byte, result_sum_signed))
print("  溢出: %s (双符号位法=%s, 进位判别法=%s)" % (
    AplusB_double["溢出"], AplusB_double["溢出"], AplusB_carry["溢出"]))
print()

print("=" * 60)
print("第(2)题 [A−B]补:")
print("-" * 40)
print("PROCESS:")
print("  求[−B]补: ~0x%02X + 1 = 0x%02X + 1 = 0x%02X" % (B_byte, (~B_byte) & (mod-1), negB_byte))
print("  验证逆元: [−B]补 + [B]补 = 0x%02X + 0x%02X = 0x%03X (mod 256 = %s)" % (
    negB_byte, B_byte, negB_byte + B_byte, (negB_byte + B_byte) % mod))
print()
print("  真实值 A−B = %d − %d = %d" % (A_dec, B_dec, real_diff))
print("  表示范围: [-128, +127] → 真实值 %d 在范围内 → 不溢出" % real_diff)
print()
print("  模256加法: [A]补 + [−B]补 = 0x%02X + 0x%02X = 0x%03X → 截断8位 = 0x%02X" % (
    A_byte, negB_byte, AminusB_raw, AminusB_byte))
print()

print("  【双符号位法】(对 [A]+[−B]):")
for k, v in AminusB_double.items():
    print("    %s = %s" % (k, v))
print()

print("  【进位判别法】(对 [A]+[−B]):")
for k, v in AminusB_carry.items():
    print("    %s = %s" % (k, v))
print()

print("RESULT_Q2:")
print("  [−B]补 = 0x%02X" % negB_byte)
print("  [A−B]补 = 0x%02X (十进制: %d)" % (AminusB_byte, result_diff_signed))
print("  溢出: %s (双符号位法=%s, 进位判别法=%s)" % (
    AminusB_double["溢出"], AminusB_double["溢出"], AminusB_carry["溢出"]))
print()

# =====================================================
#  场景规则验证（数据流可读，不写独立 assert）
# =====================================================
print("=" * 60)
print("RULE_CHECK (对照场景规则):")
print("  规则1 A,B均为负数: A_dec=%d<0, B_dec=%d<0 → %s" % (A_dec, B_dec, A_dec < 0 and B_dec < 0))
print("  规则2 非平凡值: A∉{0,-1}, B∉{0,-1} → %s" % (A_dec not in (0,-1) and B_dec not in (0,-1)))
print("  规则3 [−B]补是[B]补逆元: ([−B]+[B]) mod 256 = %d → %s" % (
    (negB_byte + B_byte) % mod, (negB_byte + B_byte) % mod == 0))
print("  规则4 (1)溢出: 真实值%d超出[-128,127] → %s" % (real_sum, AplusB_double["溢出"]))
print("  规则5 (2)不溢出: 真实值%d在[-128,127]内 → %s" % (real_diff, not AminusB_double["溢出"]))
print("  规则6 双符号位法==进位判别法:")
print("    Q1: 双符号位法溢出=%s, 进位判别法溢出=%s → 一致=%s" % (
    AplusB_double["溢出"], AplusB_carry["溢出"], AplusB_double["溢出"] == AplusB_carry["溢出"]))
print("    Q2: 双符号位法溢出=%s, 进位判别法溢出=%s → 一致=%s" % (
    AminusB_double["溢出"], AminusB_carry["溢出"], AminusB_double["溢出"] == AminusB_carry["溢出"]))
print("  规则7 运算正确性(mod 2^8):")
print("    [A+B]补=0x%02X == (A+B) mod 256 = 0x%02X → %s" % (
    AplusB_byte, AplusB_raw % mod, AplusB_byte == AplusB_raw % mod))
print("    [A−B]补=0x%02X == (A+negB) mod 256 = 0x%02X → %s" % (
    AminusB_byte, AminusB_raw % mod, AminusB_byte == AminusB_raw % mod))
