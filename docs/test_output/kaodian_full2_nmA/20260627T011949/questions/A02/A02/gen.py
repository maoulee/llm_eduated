# -*- coding: utf-8 -*-
"""
IEEE 754 单精度浮点数表示转换 — x = -23.6875
建模：十进制 → 二进制 → 规格化 → 加偏置 → 拼装 32 位
底部打印完整数据流（PARAMS / PROCESS / RESULT + 各选项正确值/实际值/改错方式）
"""
import struct


def dec_to_ieee754(x):
    """严格按 IEEE 754 单精度规则转换，返回 (符号位, 阶码域, 尾数域, 32位整数)。"""
    sign = 1 if x < 0 else 0
    ax = abs(x)

    # ---- 十进制 → 二进制（整数部分 + 小数部分）----
    int_part = int(ax)
    frac_part = ax - int_part

    int_bits = bin(int_part)[2:]                      # 整数部分二进制

    frac_bits = ""
    temp = frac_part
    while temp != 0 and len(frac_bits) < 40:
        temp *= 2
        if temp >= 1:
            frac_bits += "1"
            temp -= 1
        else:
            frac_bits += "0"

    full_bits = int_bits + "." + frac_bits             # 完整二进制

    # ---- 规格化 ----
    # 找到前导 1 的位置，移到小数点前
    combined = int_bits + frac_bits
    dot_pos = len(int_bits)                            # 原小数点位置（在 combined 中）
    leading_one = combined.index("1")                  # 第一个 1 的位置
    exp = dot_pos - leading_one - 1                    # 真实指数
    normalized = combined[leading_one:]                # 去掉前导零，形式 1.f

    frac_field_bits = normalized[1:]                   # 去掉隐含的前导 1，取小数部分
    mantissa_field = frac_field_bits[:23].ljust(23, "0")  # 取 23 位，不足补零

    bias = 127
    exp_field = exp + bias                             # 阶码域 = 真实指数 + 127

    return sign, exp_field, int(mantissa_field, 2), mantissa_field


def assemble(sign, exp_field, mantissa_field):
    """拼装 32 位整数。"""
    val = (sign << 31) | (exp_field << 23) | mantissa_field
    return val


def to_hex(val):
    return f"0x{val & 0xFFFFFFFF:08X}"


# ============================================================
# 主流程
# ============================================================
x = -23.6875

# ---- A：严格转换 ----
sign_A, exp_A, mant_A_int, mant_A_bits = dec_to_ieee754(x)
val_A = assemble(sign_A, exp_A, mant_A_int)

# ---- B：偏置值误用 128（阶码域 = 真实指数 + 128 = exp_A + 1）----
sign_B = sign_A
mant_B_int = mant_A_int
exp_B = exp_A + 1                                       # 偏置 128 → 阶码比 A 多 1
val_B = assemble(sign_B, exp_B, mant_B_int)

# ---- C：遗漏隐含前导 1，尾数域含前导 1，阶码域不补偿（== A 阶码域）----
sign_C = sign_A
exp_C = exp_A                                           # 题干：阶码不做任何补偿
# C 尾数域 = (A 尾数域左移1位) | (1<<22)，丢弃 bit23 溢出
mant_C_int = ((mant_A_int << 1) | (1 << 22)) & 0x7FFFFF
val_C = assemble(sign_C, exp_C, mant_C_int)

# ---- D：符号位取反 ----
sign_D = 1 - sign_A
mant_D_int = mant_A_int
exp_D = exp_A
val_D = assemble(sign_D, exp_D, mant_D_int)


# ============================================================
# 底部：打印完整数据流
# ============================================================
print("=" * 60)
print("PARAMS:", {"x": x})
print("=" * 60)

print("\nPROCESS:")
print(f"  |x| = {abs(x)}")
print(f"  整数部分 {int(abs(x))} → 二进制 {bin(int(abs(x)))[2:]}")
print(f"  小数部分 {abs(x) - int(abs(x))} → 二进制 0.{mant_A_bits.rstrip('0') if mant_A_bits.strip('0') else '(none)'}")
print(f"    (小数部分乘2取整完整序列: {bin(int(abs(x)))[2:]}.{mant_A_bits[:23]})")
print(f"  规格化后: 1.{mant_A_bits} × 2^{exp_A - 127}")
print(f"  真实指数 E = {exp_A - 127}")
print(f"  阶码域 = E + 127 = {exp_A}")
print(f"  符号位 S = {sign_A}")
print(f"  尾数域(23bit) = {mant_A_bits}")

print(f"\nRESULT:")
print(f"  A = {to_hex(val_A)}")
print(f"  A 二进制 = {bin(val_A)[2:].zfill(32)}")
print(f"    S={sign_A}, 阶码={bin(exp_A)[2:].zfill(8)}({exp_A}), 尾数={mant_A_bits}")

print(f"\n  B = {to_hex(val_B)}")
print(f"    S={sign_B}, 阶码={bin(exp_B)[2:].zfill(8)}({exp_B}), 尾数={bin(mant_B_int)[2:].zfill(23)}")

print(f"\n  C = {to_hex(val_C)}")
print(f"    S={sign_C}, 阶码={bin(exp_C)[2:].zfill(8)}({exp_C}), 尾数={bin(mant_C_int)[2:].zfill(23)}")

print(f"\n  D = {to_hex(val_D)}")
print(f"    S={sign_D}, 阶码={bin(exp_D)[2:].zfill(8)}({exp_D}), 尾数={bin(mant_D_int)[2:].zfill(23)}")

print("\n" + "=" * 60)
print("OPTION_DETAILS:")
print(f"  OPTION_A: 正确值={to_hex(val_A)}, 实际值={to_hex(val_A)}, 改错方式=无（正确选项）")
print(f"  OPTION_B: 正确值={to_hex(val_A)}, 实际值={to_hex(val_B)}, 改错方式=偏置值误用128（阶码域+1）")
print(f"  OPTION_C: 正确值={to_hex(val_A)}, 实际值={to_hex(val_C)}, 改错方式=遗漏隐含前导1（尾数域含前导1，阶码不补偿）")
print(f"  OPTION_D: 正确值={to_hex(val_A)}, 实际值={to_hex(val_D)}, 改错方式=符号位取反")

# ---- 场景规则验证（打印供审核对照，不写 assert）----
print("\n" + "=" * 60)
print("RULE_CHECK:")
print(f"  规则1 格式合规: S={sign_A}∈{{0,1}}, 阶码域={exp_A}∈[1,254]? {1 <= exp_A <= 254}")
print(f"  规则2 规格化数: 阶码域={exp_A} ∈ [1,254]? {1 <= exp_A <= 254}")
vals = [val_A, val_B, val_C, val_D]
hex_vals = [to_hex(v) for v in vals]
print(f"  规则3 四选项互异: {len(set(hex_vals)) == 4}  ({hex_vals})")
print(f"  规则4 正确值唯一: A={to_hex(val_A)}")
print(f"  规则5 B=偏置错误: B符号={sign_B}==A符号={sign_A}? {sign_B==sign_A}; B尾数域={mant_B_int}==A尾数域={mant_A_int}? {mant_B_int==mant_A_int}; B阶码域={exp_B}==A阶码域+1={exp_A+1}? {exp_B==exp_A+1}")
print(f"  规则6 C=遗漏前导1: C符号={sign_C}==A符号={sign_A}? {sign_C==sign_A}; C阶码域={exp_C}==A阶码域={exp_A}? {exp_C==exp_A}; C尾数域={mant_C_int}==((A尾数左移1)|(1<<22))&0x7FFFFF={((mant_A_int<<1)|(1<<22))&0x7FFFFF}? {mant_C_int==((mant_A_int<<1)|(1<<22))&0x7FFFFF}")
print(f"  规则7 D=符号取反: D阶码域={exp_D}==A阶码域={exp_A}? {exp_D==exp_A}; D尾数域={mant_D_int}==A尾数域={mant_A_int}? {mant_D_int==mant_A_int}; D符号={sign_D}==1-A符号={1-sign_A}? {sign_D==1-sign_A}")

# ---- Python struct 交叉验证（验证 A 的正确性）----
expected_bytes = struct.pack('>f', x)
expected_int = struct.unpack('>I', expected_bytes)[0]
print(f"\n  交叉验证(struct.pack): x={x} → {to_hex(expected_int)}")
print(f"  A与struct.pack一致: {val_A == expected_int}")
