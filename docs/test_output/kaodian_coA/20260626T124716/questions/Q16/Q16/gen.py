"""
Booth 算法（补码一位乘法）推演
x = -5/16, y = +6/16, 5 位补码, n=4, n+1=5 趟迭代
部分积双符号位（6 位寄存器）

关键建模思路：
  - 寄存器为整数取模表示，部分积 PP 宽度 PPW=6（双符号位）
  - 乘数 Y 宽度 N=5，附加位 y_extra 单独维护
  - 部分积(6位) || 乘数(5位) || 附加位(1位) 联合做算术右移（最高位复制）
  - 最终乘积取 PP 的高 5 位（去一个重复符号位）+ Y 的 5 位 = 10 位
  - 10 位定点小数：符号 1 位 + 数值 9 位，最低位权重 2^{-9}
"""

from fractions import Fraction

n = 4
N = n + 1              # 5 位字长（1 符号 + 4 数值）
PPW = N + 1            # 部分积寄存器宽度 = 6 位（2 符号 + 4 数值）
PPMOD = 1 << PPW       # 部分积模 2^6
NM = 1 << N            # 5 位数值模 2^5

# ===================== 工具函数 =====================
def to_complement(val, width):
    """定点小数 val（|val|<1, 最低位权重 2^{-(width-1)}）→ width 位补码整数"""
    scale = 1 << (width - 1)
    scaled = int(round(val * scale))
    return scaled % (1 << width)

def complement_to_val(cval, width):
    """width 位补码整数 → 定点小数值（最低位权重 2^{-(width-1)}）"""
    scale = 1 << (width - 1)
    if cval >= (1 << (width - 1)):
        cval -= (1 << width)
    return Fraction(cval, scale)

def to_bin(cval, width):
    """补码整数 → width 位二进制字符串"""
    return format(cval % (1 << width), f'0{width}b')

def extend_double_sign(cval_5, src_w=5, dst_w=6):
    """5 位补码扩展为 6 位双符号位：复制符号位"""
    sign_bit = (cval_5 >> (src_w - 1)) & 1
    # 高位填符号位，低位保持原值
    mask_high = ((1 << dst_w) - 1) ^ ((1 << src_w) - 1)
    return cval_5 | (sign_bit << (src_w - 1) if src_w < dst_w else 0) | ((sign_bit * mask_high) if dst_w > src_w else 0)

def extend_sign(cval, src_w, dst_w):
    """将 src_w 位补码整数符号扩展到 dst_w 位"""
    sign_bit = (cval >> (src_w - 1)) & 1
    result = cval
    if sign_bit:
        for bit in range(src_w, dst_w):
            result |= (1 << bit)
    return result % (1 << dst_w)

# ===================== PARAMS =====================
print("=== PARAMS ===")
print(f"x = -5/16, y = +6/16, N={N} 位补码, n={n}, n+1={N} 趟迭代")
print(f"部分积寄存器 {PPW} 位（双符号位）, 乘数寄存器 {N} 位 + 1 附加位")

x_frac = Fraction(-5, 16)
y_frac = Fraction(6, 16)

x_comp = to_complement(x_frac, N)    # [x]补 5 位
y_comp = to_complement(y_frac, N)    # [y]补 5 位
neg_x_comp = ((~x_comp) + 1) % NM    # [-x]补 = 取反加1

print(f"\n[x]_补 = {to_bin(x_comp, N)}  (整数={x_comp}, 值={complement_to_val(x_comp, N)})")
print(f"[y]_补 = {to_bin(y_comp, N)}  (整数={y_comp}, 值={complement_to_val(y_comp, N)})")
print(f"[-x]_补 = {to_bin(neg_x_comp, N)}  (整数={neg_x_comp}, 值={complement_to_val(neg_x_comp, N)})")

# 双符号位扩展：5位 → 6位
x_6 = extend_sign(x_comp, N, PPW)
neg_x_6 = extend_sign(neg_x_comp, N, PPW)

print(f"\n[+x]双符号位 = {to_bin(x_6, PPW)}  (整数={x_6}, 值={complement_to_val(x_6, PPW)})")
print(f"[-x]双符号位 = {to_bin(neg_x_6, PPW)}  (整数={neg_x_6}, 值={complement_to_val(neg_x_6, PPW)})")

# ===================== Booth 迭代 =====================
print("\n=== REASONING (Booth 迭代表格) ===")

PP = 0                       # 部分积（6 位寄存器）初值 0
Y = y_comp                   # 乘数寄存器（5 位）
y_extra = 0                  # 附加位 y_{-1} 初值 0

rows = []
ops_seen = set()
shift_check = []  # (趟号, 移前符号最高位, 移后符号最高位, 移前符号次高位, 移后符号次高位)

print(f"{'趟':>3} | {'操作':^8} | {'部分积(移前)':>14} | {'乘数+附加位':>12} | {'判断位':>6} | {'部分积(移后)':>14} | {'乘数+附加位(移后)':>16}")
print("-" * 100)

for i in range(N):  # 共 5 趟
    y0 = Y & 1
    judge = f"{y0}{y_extra}"

    # Booth 规则翻译：
    #   00 或 11 -> +0
    #   01       -> +[x]补
    #   10       -> +[-x]补
    if judge == "01":
        PP = (PP + x_6) % PPMOD
        op = "+[x]补"
        ops_seen.add("01")
    elif judge == "10":
        PP = (PP + neg_x_6) % PPMOD
        op = "+[-x]补"
        ops_seen.add("10")
    else:
        op = "+0"
        ops_seen.add(judge)

    pp_before_str = to_bin(PP, PPW)
    y_before_str = to_bin(Y, N) + str(y_extra)

    # 移前双符号位
    sb0 = (PP >> (PPW - 1)) & 1   # 最高符号位
    sb1 = (PP >> (PPW - 2)) & 1   # 次高符号位

    # 联合算术右移：部分积(6位) || 乘数(5位) || 附加位(1位) = 12 位整体
    total_w = PPW + N + 1   # 12
    combined = (PP << (N + 1)) | (Y << 1) | y_extra
    msb = (combined >> (total_w - 1)) & 1
    # 算术右移 1 位：最高位保持（复制符号），其余右移
    shifted = combined >> 1
    if msb:
        shifted |= (1 << (total_w - 1))
    shifted %= (1 << total_w)

    PP_shifted = (shifted >> (N + 1)) & ((1 << PPW) - 1)
    new_Y = (shifted >> 1) & ((1 << N) - 1)
    new_y_extra = shifted & 1

    # 移后双符号位
    sa0 = (PP_shifted >> (PPW - 1)) & 1
    sa1 = (PP_shifted >> (PPW - 2)) & 1

    pp_after_str = to_bin(PP_shifted, PPW)
    y_after_str = to_bin(new_Y, N) + str(new_y_extra)

    shift_check.append((i + 1, sb0, sa0, sb1, sa1))

    print(f"{i+1:>3} | {op:^8} | {pp_before_str:>14} | {y_before_str:>12} | {judge:>6} | {pp_after_str:>14} | {y_after_str:>16}")

    PP = PP_shifted
    Y = new_Y
    y_extra = new_y_extra

    rows.append({
        'step': i + 1, 'judge': judge, 'op': op,
        'pp_before': pp_before_str, 'y_before': y_before_str,
        'pp_after': pp_after_str, 'y_after': y_after_str,
    })

# ===================== 最终乘积 =====================
print("\n=== ANSWER ===")

# 最终乘积 [x×y]补：PP 低5位（去重复符号位）+ Y 5位 = 10 位
pp_5 = PP & ((1 << N) - 1)
product_bits = to_bin(pp_5, N) + to_bin(Y, N)
product_10bit = (pp_5 << N) | Y

print(f"最终部分积(双符号位) = {to_bin(PP, PPW)}")
print(f"最终乘数(含附加位)   = {to_bin(Y, N)}{y_extra}")
print(f"[x×y]_补 (10位) = {product_bits}")

# 10 位补码定点小数：1 符号位 + 8 数值位 + 1 附加零位
# 两个 n=4 数值位小数相乘 → 乘积 2n=8 个数值位，最低有效位权重 2^{-8}
# 10 位中：bit9=符号，bit8..bit1=8个数值位，bit0=附加零位
# 附加位恒为 0（右移末位），故 10 位整体作为补码整数 / 2^8 即可得真实值
assert (product_10bit & 1) == 0, f"附加位(最低位)应为0，实际={product_10bit & 1}"
def product10_to_frac(val10):
    """10 位补码定点小数 → 分数（数值位 2n=8 位，附加位恒 0）"""
    if val10 >= (1 << 9):       # 符号位（bit9）为 1
        val10 -= (1 << 10)
    return Fraction(val10, 1 << (2 * n))   # / 2^8

product_val = product10_to_frac(product_10bit)
expected = x_frac * y_frac

print(f"[x×y]_补 转十进制 = {product_val} = {float(product_val)}")
print(f"x × y = -5/16 × 6/16 = {expected} = {float(expected)}")
print(f"验证：product_val == x*y ? {product_val == expected}")

# ===================== ASSERT（通过条件）=====================

# 条件1：Booth 操作完整性 —— 至少一次 "01"(加[x]补) 和一次 "10"(加[-x]补)
assert "01" in ops_seen, f"通过条件1失败：未出现 '01' 模式（加[x]补），ops_seen={ops_seen}"
assert "10" in ops_seen, f"通过条件1失败：未出现 '10' 模式（加[-x]补），ops_seen={ops_seen}"
print(f"\n[ASSERT 通过] 条件1 Booth操作完整性: ops_seen={ops_seen} (含 01 和 10)")

# 条件2：[-x]补 正确性
neg_x_check = ((~x_comp) + 1) % NM
assert neg_x_check == neg_x_comp, "条件2失败：[-x]补 != 按位取反加1"
assert (x_comp + neg_x_comp) % NM == 0, "条件2失败：[x]补+[-x]补 != 0 (模2^5)"
print(f"[ASSERT 通过] 条件2 [-x]补正确性: [-x]补={to_bin(neg_x_comp,N)}, [x]补+[-x]补=0 (模2^5)")

# 条件3：乘积正确性
assert product_val == expected, f"条件3失败：乘积 {product_val} != {expected}"
assert abs(product_val) < 1, f"条件3失败：|乘积|={abs(product_val)} >= 1，溢出"
assert expected == Fraction(-15, 128), f"条件3失败：期望值 != -15/128"
assert expected == Fraction(-30, 256), f"条件3失败：期望值 != -30/256"
print(f"[ASSERT 通过] 条件3 乘积正确性: product={product_val}={float(product_val)}, |product|<1={abs(product_val)<1}")

# 条件4：每趟右移为算术右移
assert len(rows) == N, f"条件4失败：迭代趟数 {len(rows)} != {N}"
for step, sb0, sa0, sb1, sa1 in shift_check:
    assert sb0 == sa0, f"条件4失败：第{step}趟符号位(最高)右移后改变 {sb0}->{sa0}"
    assert sb1 == sa1, f"条件4失败：第{step}趟符号位(次高)右移后改变 {sb1}->{sa1}"
    assert sb0 == sb1, f"条件4失败：第{step}趟双符号位不一致 {sb0}!={sb1}（移前已不一致）"
print(f"[ASSERT 通过] 条件4 每趟算术右移: {N}趟均符号位保持一致")

print("\n*** 全部 ASSERT 通过 ***")
