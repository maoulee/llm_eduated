# ===== 题目参数定义 =====
WORD_SIZE = 16  # 16位字长
R1 = 0x0001
R2 = 0x7FFF
MASK = (1 << WORD_SIZE) - 1  # 16位掩码 0xFFFF

# ===== 子问题(1)：真值转换 =====
# 有符号整数（补码）
def twos_complement(value, bits):
    """将位模式解释为有符号整数（补码）"""
    if value & (1 << (bits - 1)):  # 最高位为1，负数
        return value - (1 << bits)
    else:
        return value

R1_signed = twos_complement(R1, WORD_SIZE)
R1_unsigned = R1
R2_signed = twos_complement(R2, WORD_SIZE)
R2_unsigned = R2

print("===== 子问题(1) =====")
print(f"R1 = {R1:#06X}H")
print(f"  有符号整数: {R1_signed}")
print(f"  无符号整数: {R1_unsigned}")
print(f"R2 = {R2:#06X}H")
print(f"  有符号整数: {R2_signed}")
print(f"  无符号整数: {R2_unsigned}")

# ===== 子问题(2)：加法运算与标志位 =====
def add16(a, b):
    """16位加法，返回 (结果, CF, OF)"""
    full_sum = a + b
    
    # 结果截断到16位
    result = full_sum & MASK
    
    # CF（进位标志）：无符号加法溢出
    # CF = 1 当且仅当 第16位有进位（即 full_sum >= 2^16）
    CF = 1 if full_sum >= (1 << WORD_SIZE) else 0
    
    # OF（溢出标志）：有符号加法溢出
    # OF = 1 当且仅当两个操作数符号相同但结果符号不同
    a_sign = (a >> (WORD_SIZE - 1)) & 1
    b_sign = (b >> (WORD_SIZE - 1)) & 1
    result_sign = (result >> (WORD_SIZE - 1)) & 1
    if a_sign == b_sign:
        OF = 1 if a_sign != result_sign else 0
    else:
        OF = 0
    
    return result, CF, OF

# R3 = R1 + R2
R3, CF3, OF3 = add16(R1, R2)
print(f"\n===== 子问题(2) =====")
print(f"R3 = R1 + R2 = {R1:#06X}H + {R2:#06X}H")
print(f"  完整和: {R1 + R2}")
print(f"  R3 = {R3:#06X}H")
print(f"  CF = {CF3}, OF = {OF3}")

# R4 = R3 + R2
R4, CF4, OF4 = add16(R3, R2)
print(f"R4 = R3 + R2 = {R3:#06X}H + {R2:#06X}H")
print(f"  完整和: {R3 + R2}")
print(f"  R4 = {R4:#06X}H")
print(f"  CF = {CF4}, OF = {OF4}")

# R5 = R4 + R2
R5, CF5, OF5 = add16(R4, R2)
print(f"R5 = R4 + R2 = {R4:#06X}H + {R2:#06X}H")
print(f"  完整和: {R4 + R2}")
print(f"  R5 = {R5:#06X}H")
print(f"  CF = {CF5}, OF = {OF5}")

# ===== 子问题(3)：溢出判断 =====
print(f"\n===== 子问题(3) =====")
print("有符号整数溢出判断（OF=1表示溢出）：")
print(f"  R3: OF={OF3} → {'溢出' if OF3 else '不溢出'}")
print(f"  R4: OF={OF4} → {'溢出' if OF4 else '不溢出'}")
print(f"  R5: OF={OF5} → {'溢出' if OF5 else '不溢出'}")

print("无符号整数溢出判断（CF=1表示溢出）：")
print(f"  R3: CF={CF3} → {'溢出' if CF3 else '不溢出'}")
print(f"  R4: CF={CF4} → {'溢出' if CF4 else '不溢出'}")
print(f"  R5: CF={CF5} → {'溢出' if CF5 else '不溢出'}")

# 验证：有符号范围 [-32768, 32767]，无符号范围 [0, 65535]
print(f"\n验证：")
print(f"  有符号范围: [{-(1 << 15)}, {(1 << 15) - 1}]")
print(f"  无符号范围: [0, {(1 << 16) - 1}]")

# 验证R3有符号溢出：1 + 32767 = 32768 > 32767
print(f"  R3有符号: {R1_signed} + {R2_signed} = {R1_signed + R2_signed} > 32767 → 溢出")
print(f"  R3无符号: {R1_unsigned} + {R2_unsigned} = {R1_unsigned + R2_unsigned} <= 65535 → 不溢出")

# 验证R4：R3=8000H（有符号-32768）+ 32767 = -1，在范围内
R3_signed = twos_complement(R3, WORD_SIZE)
print(f"  R4有符号: {R3_signed} + {R2_signed} = {R3_signed + R2_signed}，范围[-32768,32767] → 不溢出")
print(f"  R4无符号: {R3} + {R2} = {R3 + R2} <= 65535 → 不溢出")

# 验证R5：R4=FFFFH（有符号-1）+ 32767 = 32766，在范围内
R4_signed = twos_complement(R4, WORD_SIZE)
print(f"  R5有符号: {R4_signed} + {R2_signed} = {R4_signed + R2_signed}，范围[-32768,32767] → 不溢出")
print(f"  R5无符号: {R4} + {R2} = {R4 + R2} > 65535 → 溢出")

# ===== 最终输出 =====
print(f"\n===== 最终答案 =====")
print(f"R3 = {R3:#06X}H, CF={CF3}, OF={OF3}")
print(f"R4 = {R4:#06X}H, CF={CF4}, OF={OF4}")
print(f"R5 = {R5:#06X}H, CF={CF5}, OF={OF5}")
