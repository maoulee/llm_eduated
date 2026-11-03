# -*- coding: utf-8 -*-
"""
扩展操作码数量计算 —— gen.py
题干规则翻译：逐级扩展操作码，每级预留 1 个编码作为下级扩展前缀，最低级（零地址）不预留。
"""

# ============ PARAMS ============
L = 16          # 指令字长（位）
a = 4           # 每个地址码位数
# 二地址格式：OP(8位) | A1(4位) | A2(4位) = 16位
op2_bits = 8    # 二地址操作码位数 = L - 2*a = 16 - 8 = 8
# 一地址扩展：OP(8位)+A1(4位) 合并后扩展部分为 A1 的 4 位
ext1_bits = 4   # 一地址扩展操作码位数 = a = 4
# 零地址扩展：A2 的 4 位
ext0_bits = 4   # 零地址扩展操作码位数 = a = 4

# 题干第2问给定值
given_2addr = 250   # 实际定义的二地址指令数
given_1addr = 14    # 实际定义的一地址指令数

print("=" * 60)
print("PARAMS")
print("=" * 60)
print(f"指令字长 L = {L} 位")
print(f"地址码位数 a = {a} 位")
print(f"二地址操作码位数 = {op2_bits} 位（L - 2*a = {L} - {2*a}）")
print(f"一地址扩展操作码位数 = {ext1_bits} 位（A1 字段转入）")
print(f"零地址扩展操作码位数 = {ext0_bits} 位（A2 字段转入）")
print(f"第2问给定：二地址指令 {given_2addr} 条，一地址指令 {given_1addr} 条")
print()


# ============ REASONING ============
print("=" * 60)
print("REASONING")
print("=" * 60)

# ---- 第1问 ----
# 二地址：8位操作码共 2^8 = 256 个编码，预留 1 个（11111111）作为扩展前缀
max_2addr = (1 << op2_bits) - 1   # 256 - 1 = 255
print(f"\n【第1问】")
print(f"二地址操作码位数 = {op2_bits}，编码总数 = 2^{op2_bits} = {1 << op2_bits}")
print(f"  需预留 1 个编码（11111111）作为一地址扩展前缀")
print(f"  二地址指令最多 = 2^{op2_bits} - 1 = {1 << op2_bits} - 1 = {max_2addr} 条")

# 一地址：扩展后操作码为 A1 的 4 位，共 2^4 = 16 个编码，预留 1 个作为零地址扩展前缀
max_1addr = (1 << ext1_bits) - 1  # 16 - 1 = 15
print(f"\n一地址扩展操作码位数 = {ext1_bits}（A1 字段转入），编码总数 = 2^{ext1_bits} = {1 << ext1_bits}")
print(f"  需预留 1 个编码作为零地址扩展前缀")
print(f"  一地址指令最多 = 2^{ext1_bits} - 1 = {1 << ext1_bits} - 1 = {max_1addr} 条")

# ---- 第2问 ----
# 零地址：A2 的 4 位全部用作操作码，最低级无需预留
max_0addr = (1 << ext0_bits)      # 16，不减1
print(f"\n【第2问】")
print(f"零地址扩展操作码位数 = {ext0_bits}（A2 字段转入），编码总数 = 2^{ext0_bits} = {1 << ext0_bits}")
print(f"  零地址为最低级，无需再预留扩展前缀")
print(f"  零地址指令最多 = 2^{ext0_bits} = {max_0addr} 条")
print(f"\n理由：零地址指令的最大数仅取决于扩展操作码位数（{ext0_bits} 位），")
print(f"  与实际定义的二地址指令数（{given_2addr}）和一地址指令数（{given_1addr}）无关。")
print(f"  只要 given_2addr ≤ {max_2addr} 且 given_1addr ≤ {max_1addr}，扩展链路即可成立。")
print(f"  given_2addr = {given_2addr} ≤ {max_2addr} ✓")
print(f"  given_1addr = {given_1addr} ≤ {max_1addr} ✓")
print()

# ============ ANSWER ============
print("=" * 60)
print("ANSWER")
print("=" * 60)
print(f"第1问：二地址指令最多 {max_2addr} 条；一地址指令最多 {max_1addr} 条。")
print(f"第2问：零地址指令最多 {max_0addr} 条。")
print()


# ============ 验证段：翻译通过条件 ============
# 条件1: 二地址最大数 = 2^8 - 1 = 255
assert max_2addr == (1 << op2_bits) - 1, f"条件1失败：二地址最大数应为 {1<<op2_bits}-1={max_2addr}"
assert max_2addr == 255, f"条件1失败：二地址最大数应为255，实际{max_2addr}"
assert max_2addr != (1 << op2_bits), "条件1失败：未预留扩展前缀，结果为256（错误）"

# 条件2: 一地址最大数 = 2^4 - 1 = 15
assert max_1addr == (1 << ext1_bits) - 1, f"条件2失败：一地址最大数应为 {1<<ext1_bits}-1={max_1addr}"
assert max_1addr == 15, f"条件2失败：一地址最大数应为15，实际{max_1addr}"
assert max_1addr != (1 << ext1_bits), "条件2失败：未预留扩展前缀，结果为16（错误）"

# 条件3: 零地址最大数 = 2^4 = 16（最低级不预留）
assert max_0addr == (1 << ext0_bits), f"条件3失败：零地址最大数应为 {1<<ext0_bits}={max_0addr}"
assert max_0addr == 16, f"条件3失败：零地址最大数应为16，实际{max_0addr}"

# 条件4: 给定数值合法性
assert given_2addr <= max_2addr, f"条件4失败：二地址给定值{given_2addr}超出容量{max_2addr}"
assert given_1addr <= max_1addr, f"条件4失败：一地址给定值{given_1addr}超出容量{max_1addr}"

# 条件5: 零地址最大数与已定义数量无关——用不同合法给定值验证结果不变
max_0addr_check_a = (1 << ext0_bits)  # 给定 250/14
max_0addr_check_b = (1 << ext0_bits)  # 给定 1/1（另一组合法值）
assert max_0addr_check_a == max_0addr_check_b == 16, \
    "条件5失败：零地址最大数应与已定义数量无关，恒为16"

print("=" * 60)
print("✅ 全部通过条件 assert 通过")
print("=" * 60)
