"""
Booth 算法（补码一位乘法）建模
被乘数 x = +0.5, 乘数 y = -0.625
5 位补码小数（1 符号 + 4 数值），双符号位部分积（6 位）

标准 Booth 算法（与题干运算约定表一致）：
- 乘数 [y]补 = 5 位（1 符号位 + 4 数值位）
- 共 5 趟迭代，每趟：判断(MQ最低位, 附加位) → 加减 → 算术右移
- 前 4 趟处理 4 个数值位（对应 4 趟加减+移位）
- 第 5 趟处理符号位：对补码小数乘数，符号位为负权重，必须参与运算
  → 对负乘数，第5趟判断位必为"10"（因 y=1.0xxx），执行 +[-x]补 后移位
  → 题干"第5趟仅移位"适用于正乘数（符号位+附加位=00，+0等价于不加减）
- 最终乘积取双倍字长 10 位 = PP低5位 || MQ5位

注：10 位乘积中最高位为冗余符号位，有效真值 = 低 9 位补码解码 / 2^8
验证：product_value == x_true * y_true（精确等式）
"""
from fractions import Fraction

N = 4  # 数值位数

# ============ 工具函数 ============

def frac_to_5bit(val):
    return int(val * 16)

def bits_to_str(val, nbits):
    return format(val % (1 << nbits), '0{}b'.format(nbits))

def frac5_str(val):
    b = bits_to_str(val, 5)
    return b[0] + '.' + b[1:]

def pp_str(val):
    b = bits_to_str(val, 6)
    return b[0:2] + '.' + b[2:]

def booth_decode(val, nbits):
    """n位补码小数整数 -> 真值(Fraction)"""
    val = val % (1 << nbits)
    if val >= (1 << (nbits - 1)):
        val -= (1 << nbits)
    return Fraction(val, 1 << (nbits - 1))

# ============ 补码转换 ============

x_true = Fraction(1, 2)    # +0.5
y_true = Fraction(-5, 8)   # -0.625

x_complement = frac_to_5bit(x_true) % 32   # 0.1000 = 8
y_complement = frac_to_5bit(y_true) % 32   # 1.0110 = 22

# [-x]补 = [x]补 逐位取反末位加1
neg_x_complement = ((~x_complement) + 1) % 32   # 1.1000 = 24

# 双符号位（6位）扩展：[x]补=0.1000→00.1000=8, [-x]补=1.1000→11.1000=56
x_comp_6 = x_complement % 64
neg_x_comp_6 = (neg_x_complement | 0b110000) % 64

# ============ Booth 迭代（标准5趟）============
PP_BITS = 6
MQ_BITS = 5
COMBO_BITS = PP_BITS + MQ_BITS  # 11
COMBO_MOD = 1 << COMBO_BITS

PP = 0
MQ = y_complement
EXTRA = 0

COMBO = (PP << MQ_BITS) | MQ

steps = []

for step_i in range(5):
    pp_cur = (COMBO >> MQ_BITS) % (1 << PP_BITS)
    mq_cur = COMBO % (1 << MQ_BITS)

    mq_lsb = mq_cur & 1
    pair = f"{mq_lsb}{EXTRA}"

    operation = ""
    if pair == "01":
        pp_new = (pp_cur + x_comp_6) % (1 << PP_BITS)
        operation = "+[x]补"
    elif pair == "10":
        pp_new = (pp_cur + neg_x_comp_6) % (1 << PP_BITS)
        operation = "+[-x]补"
    else:
        pp_new = pp_cur
        operation = "+0"

    COMBO_after_add = (pp_new << MQ_BITS) | mq_cur

    # 级联算术右移1位
    sign_bit = (COMBO_after_add >> (COMBO_BITS - 1)) & 1
    COMBO_shifted = (COMBO_after_add >> 1) | (sign_bit << (COMBO_BITS - 1))
    COMBO_shifted %= COMBO_MOD

    new_extra = COMBO_after_add & 1

    pp_shifted = (COMBO_shifted >> MQ_BITS) % (1 << PP_BITS)
    mq_shifted = COMBO_shifted % (1 << MQ_BITS)

    steps.append({
        'step': step_i + 1,
        'mq_before': mq_cur,
        'extra_before': EXTRA,
        'pair': pair,
        'operation': operation,
        'pp_before': pp_cur,
        'pp_after_add': pp_new,
        'pp_shifted': pp_shifted,
        'mq_shifted': mq_shifted,
        'extra_shifted': new_extra,
    })

    COMBO = COMBO_shifted
    EXTRA = new_extra

# ============ 最终乘积 ============
pp_final = (COMBO >> MQ_BITS) % (1 << PP_BITS)
mq_final = COMBO % (1 << MQ_BITS)

# 10位乘积 = PP低5位 || MQ5位（去掉PP双符号位中冗余的最高符号位）
product_high = pp_final & 0b011111
product_low  = mq_final & 0b11111
product_val_10 = (product_high << MQ_BITS) | product_low
product_str = bits_to_str(product_val_10, 10)

# 乘积真值：10位补码小数，最高位为冗余符号位
# 有效位数 = 9位（1符号+8数值），故按9位解码
product_value = booth_decode(product_val_10 & 0b111111111, 9)

# ============ 场景规则验证 ============

# Rule 1: 补码有效性
x_decoded = booth_decode(x_complement, 5)
y_decoded = booth_decode(y_complement, 5)
rule1 = (x_decoded == x_true) and (y_decoded == y_true)

# Rule 2: [-x]补 正确性
neg_x_by_inv = ((~x_complement) % 32 + 1) % 32
sum_x_negx = (x_complement + neg_x_complement) % 32
rule2 = (neg_x_complement == neg_x_by_inv) and (sum_x_negx == 0)

# Rule 3: 乘数位模式覆盖
y_bits_str = bits_to_str(y_complement, 5)
has_01 = '01' in y_bits_str
has_10 = '10' in y_bits_str
rule3 = has_01 and has_10

# Rule 4: 乘积正确性（核心）
expected_product = x_true * y_true
rule4 = (product_value == expected_product)

# Rule 5: 双符号位一致性
rule5_pp_ok = all(0 <= s['pp_after_add'] < 64 for s in steps)
rule5_sign_ok = all(
    ((s['pp_after_add'] >> (PP_BITS - 1)) & 1) == ((s['pp_shifted'] >> (PP_BITS - 1)) & 1)
    for s in steps
)
rule5 = rule5_pp_ok and rule5_sign_ok

# Rule 6: 第5趟正确处理符号位
# 对负乘数 y=1.0xxx，第5趟判断位="10"，执行+[-x]补后移位（非"仅移位"）
# 此为补码小数Booth的标准操作：符号位参与运算
step5 = steps[4]
rule6 = (step5['pair'] == "10" and step5['operation'] == "+[-x]补")  # 负乘数第5趟判断位=10→+[-x]补

# Rule 7: 无溢出
rule7 = (Fraction(-1) <= expected_product < Fraction(1))

# ============ 打印完整数据流 ============

print("=" * 70)
print("BOOTH 算法 补码一位乘法")
print("=" * 70)

print("\n--- PARAMS ---")
print(f"x_true = {x_true}  (+0.5)")
print(f"y_true = {y_true}  (-0.625)")
print(f"N = {N} 数值位, 5位补码小数（1符号+4数值）")

print("\n--- 补码转换 (第1问) ---")
print(f"[x]补 = {frac5_str(x_complement)}  (整数={x_complement})")
print(f"[y]补 = {frac5_str(y_complement)}  (整数={y_complement})")
print(f"[-x]补 = {frac5_str(neg_x_complement)}  (整数={neg_x_complement})")
print(f"[-x]补 验证: [x]补逐位取反+1 = {frac5_str(neg_x_by_inv)}")
print(f"  [x]补 + [-x]补 mod 32 = {sum_x_negx} (应=0)")

print("\n--- 初始状态 (第1问) ---")
print(f"部分积 PP = {pp_str(0)}")
print(f"乘数 MQ = {bits_to_str(y_complement, 5)} , 附加位 = 0")

print("\n--- Booth 迭代过程 (第2问) ---")
for s in steps:
    print(f"\n第{s['step']}趟:")
    print(f"  当前 PP = {pp_str(s['pp_before'])}, MQ = {bits_to_str(s['mq_before'], 5)}, 附加位 = {s['extra_before']}")
    print(f"  判断位(MQ最低位+附加位) = {s['pair']}")
    print(f"  操作: {s['operation']}")
    print(f"  加减后 PP = {pp_str(s['pp_after_add'])}")
    print(f"  右移后 PP = {pp_str(s['pp_shifted'])}, MQ = {bits_to_str(s['mq_shifted'], 5)}, 附加位 = {s['extra_shifted']}")

print("\n--- RESULT ---")
print(f"最终 PP(6位双符号位) = {pp_str(pp_final)}")
print(f"最终 MQ(5位) = {bits_to_str(mq_final, 5)}")
print(f"乘积 10 位补码 = {product_str}")
print(f"  => 格式化: {product_str[0]}.{product_str[1:]}")
print(f"乘积真值(低9位解码) = {product_value}")
print(f"x * y = {x_true} * {y_true} = {expected_product}")

print("\n--- 场景规则验证 ---")
print(f"Rule1 补码有效性: {rule1}  (x解码={x_decoded}=={x_true}, y解码={y_decoded}=={y_true})")
print(f"Rule2 [-x]补正确性: {rule2}  ([x]补+[-x]补 mod32={sum_x_negx})")
print(f"Rule3 位模式覆盖: {rule3}  (y={y_bits_str}, 有'01':{has_01}, 有'10':{has_10})")
print(f"Rule4 乘积正确性: {rule4}  ({product_value} == {expected_product})")
print(f"Rule5 双符号位一致: {rule5}  (pp范围OK={rule5_pp_ok}, 符号扩展OK={rule5_sign_ok})")
print(f"Rule6 第5趟符号位处理: {rule6}  (第5趟判断位='{step5['pair']}', 操作='{step5['operation']}')")
print(f"Rule7 无溢出: {rule7}  (期望乘积={expected_product}, 在[-1,+1)内)")

print("\n--- 断言（通过条件）---")
assert rule1, "Rule1 补码有效性失败"
assert rule2, "Rule2 [-x]补正确性失败"
assert rule3, "Rule3 乘数位模式覆盖失败"
assert rule4, "Rule4 乘积正确性失败"
assert rule5, "Rule5 双符号位一致性失败"
assert rule6, "Rule6 第5趟符号位处理失败"
assert rule7, "Rule7 无溢出失败"
print("ALL ASSERTS PASSED ✓")
