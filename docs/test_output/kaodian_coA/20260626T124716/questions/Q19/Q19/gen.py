# -*- coding: utf-8 -*-
"""
多种寻址方式有效地址计算 —— 建模+求解
将题干描述的五种寻址规则翻译成代码，注入参数求解，
并将 question.md 声明的通过条件翻译为 assert。
"""

# ============================================================
# PARAMS：题干参数（逐字从 question.md 提取）
# ============================================================
# 寄存器当前值
PC_BEFORE = 0x000E   # 指令起始地址（取指前）
IX = 0x0200          # 变址寄存器
BR = 0x0600          # 基址寄存器

# 指令内容
WORD1 = 0x2008       # 第一字
WORD2 = 0x0200       # 第二字 = 形式地址 A

# 双字长指令：取指读 2 个字，PC 自动 +2
INSTRUCTION_LEN_WORDS = 2

# 主存单元内容表
MEMORY = {
    0x0100: 0x0F00,
    0x0200: 0x0500,
    0x0210: 0x0BBB,
    0x0300: 0x0E00,
    0x0400: 0x0CCC,
    0x0500: 0x0AAA,
    0x0600: 0x0D00,
    0x0800: 0x0DDD,
}

def M(addr):
    """从主存表读取；若地址不在表中返回 None。"""
    return MEMORY.get(addr, None)


# ============================================================
# solve：五种寻址方式有效地址计算（逐句翻译题干规则）
# ============================================================
def solve():
    results = {}

    # --- 形式地址 A：从第二字提取（第二字整字就是 A） ---
    A = WORD2  # 0x0200

    # --- (1a) 直接寻址：EA = A ---
    ea_direct = A
    operand_direct = M(ea_direct)
    results['direct'] = {'EA': ea_direct, 'operand': operand_direct}

    # --- (1b) 间接寻址：EA = M[A]，operand = M[M[A]] ---
    # 翻译题干：间接寻址中 A 指向的主存单元内容即为 EA
    ea_indirect = M(A)           # M[0x0200] = 0x0500
    operand_indirect = M(ea_indirect)  # M[0x0500] = 0x0AAA
    results['indirect'] = {'EA': ea_indirect, 'operand': operand_indirect,
                           'pointer': ea_indirect}

    # --- (2a) 变址寻址：EA = (IX) + A ---
    ea_index = (IX + A)          # 0x0200 + 0x0200 = 0x0400
    operand_index = M(ea_index)
    results['index'] = {'EA': ea_index, 'operand': operand_index}

    # --- (2b) 基址寻址：EA = (BR) + A ---
    ea_base = (BR + A)           # 0x0600 + 0x0200 = 0x0800
    operand_base = M(ea_base)
    results['base'] = {'EA': ea_base, 'operand': operand_base}

    # --- (3) 相对寻址：EA = (PC_取指后) + A ---
    # 翻译题干：PC 为取指后的值 = 0x000E + 2 = 0x0010
    PC_AFTER = PC_BEFORE + INSTRUCTION_LEN_WORDS
    ea_relative = (PC_AFTER + A)  # 0x0010 + 0x0200 = 0x0210
    operand_relative = M(ea_relative)
    results['relative'] = {'EA': ea_relative, 'operand': operand_relative,
                           'PC_after': PC_AFTER}

    return A, PC_AFTER, results


# ============================================================
# REASONING + ANSWER：执行并打印
# ============================================================
A, PC_AFTER, res = solve()

print("=" * 60)
print("PARAMS")
print("=" * 60)
print(f"  形式地址 A (第二字) = 0x{A:04X}")
print(f"  PC (取指前) = 0x{PC_BEFORE:04X}")
print(f"  双字指令长度 = {INSTRUCTION_LEN_WORDS} 字")
print(f"  PC (取指后) = 0x{PC_AFTER:04X}")
print(f"  IX = 0x{IX:04X}")
print(f"  BR = 0x{BR:04X}")
print()

print("=" * 60)
print("REASONING")
print("=" * 60)

# (1) 直接 + 间接
print("【(1) 直接寻址】")
print(f"  EA = A = 0x{res['direct']['EA']:04X}")
print(f"  操作数 = M[0x{res['direct']['EA']:04X}] = 0x{res['direct']['operand']:04X}")
print()
print("【(1) 间接寻址】")
print(f"  指针 = M[A] = M[0x{A:04X}] = 0x{res['indirect']['pointer']:04X}")
print(f"  EA = M[A] = 0x{res['indirect']['EA']:04X}")
print(f"  操作数 = M[M[A]] = M[0x{res['indirect']['EA']:04X}] = 0x{res['indirect']['operand']:04X}")
print()

# (2) 变址 + 基址
print("【(2) 变址寻址】")
print(f"  EA = (IX) + A = 0x{IX:04X} + 0x{A:04X} = 0x{res['index']['EA']:04X}")
print(f"  操作数 = M[0x{res['index']['EA']:04X}] = 0x{res['index']['operand']:04X}")
print()
print("【(2) 基址寻址】")
print(f"  EA = (BR) + A = 0x{BR:04X} + 0x{A:04X} = 0x{res['base']['EA']:04X}")
print(f"  操作数 = M[0x{res['base']['EA']:04X}] = 0x{res['base']['operand']:04X}")
print()

# (3) 相对
print("【(3) 相对寻址】")
print(f"  PC_取指后 = 0x{PC_BEFORE:04X} + 2 = 0x{res['relative']['PC_after']:04X}")
print(f"  EA = (PC_取指后) + A = 0x{res['relative']['PC_after']:04X} + 0x{A:04X} = 0x{res['relative']['EA']:04X}")
print(f"  操作数 = M[0x{res['relative']['EA']:04X}] = 0x{res['relative']['operand']:04X}")
print()

# (4) 访存次数
print("【(4) 取得操作数阶段的访存次数】")
print("  直接寻址：1 次（读 M[A]）")
print("  间接寻址：2 次（读 M[A] 得指针 → 读 M[M[A]] 得操作数）")
print("  变址寻址：1 次（计算 EA 后读 M[(IX)+A]）")
print("  基址寻址：1 次（计算 EA 后读 M[(BR)+A]）")
print("  相对寻址：1 次（计算 EA 后读 M[(PC)+A]）")
print()

print("=" * 60)
print("ANSWER")
print("=" * 60)
print(f"  (1) 直接: EA=0x{res['direct']['EA']:04X}, 操作数=0x{res['direct']['operand']:04X}")
print(f"  (1) 间接: EA=0x{res['indirect']['EA']:04X}, 操作数=0x{res['indirect']['operand']:04X}")
print(f"  (2) 变址: EA=0x{res['index']['EA']:04X}, 操作数=0x{res['index']['operand']:04X}")
print(f"  (2) 基址: EA=0x{res['base']['EA']:04X}, 操作数=0x{res['base']['operand']:04X}")
print(f"  (3) 相对: EA=0x{res['relative']['EA']:04X}, 操作数=0x{res['relative']['operand']:04X}")
print()

operands = [
    res['direct']['operand'],
    res['indirect']['operand'],
    res['index']['operand'],
    res['base']['operand'],
    res['relative']['operand'],
]
print(f"  五种操作数 = {[f'0x{o:04X}' for o in operands]}")
print(f"  len(set) = {len(set(operands))}")

# ============================================================
# ASSERT：通过条件翻译（打到题干声明的特征，禁弱化/禁恒真）
# ============================================================
print()
print("=" * 60)
print("ASSERT CHECKS")
print("=" * 60)

# 条件1：形式地址可提取 —— A = 0x0200
assert A == 0x0200, f"形式地址应为0x0200，实际0x{A:04X}"
print("  [PASS] 条件1: 形式地址 A = 0x0200")

# 条件2：五种操作数互不相同
assert len(set(operands)) == 5, f"五种操作数应互不相同，实际set大小={len(set(operands))}"
print("  [PASS] 条件2: 五种寻址方式操作数互不相同 (len(set)==5)")

# 条件3：间接寻址访存链 ≥ 2 级
ptr = M(A)          # M[0x0200] = 0x0500
assert ptr != A, "间接寻址：M[A] 不应等于 A"
assert M(ptr) is not None, "间接寻址：M[M[A]] 应存在于主存表中"
print(f"  [PASS] 条件3: 间接访存链≥2级 (M[A]=0x{ptr:04X} ≠ A=0x{A:04X}, M[M[A]]在表中)")

# 条件4：相对寻址 PC 取值时机正确
assert PC_AFTER == 0x0010, "取指后 PC 应为 0x0010"
ea_rel_correct = PC_AFTER + A   # 0x0210
ea_rel_wrong = PC_BEFORE + A    # 0x020E
assert M(ea_rel_correct) is not None, "正确 PC 计算的 EA 应在表中"
assert M(ea_rel_wrong) is None, "错误 PC（取指前）计算的 EA 应不在表中"
print(f"  [PASS] 条件4: PC取指后=0x{PC_AFTER:04X}, EA=0x{ea_rel_correct:04X}在表中; "
      f"错误EA=0x{ea_rel_wrong:04X}不在表中")

# 条件5：变址目标 ≠ 基址目标
assert res['index']['EA'] != res['base']['EA'], "变址EA不应等于基址EA"
assert res['index']['operand'] != res['base']['operand'], "变址操作数不应等于基址操作数"
print(f"  [PASS] 条件5: 变址EA=0x{res['index']['EA']:04X} ≠ 基址EA=0x{res['base']['EA']:04X}")

# 条件6：所有寻址方式的 EA 对应单元均在主存表内
all_eas = [
    res['direct']['EA'],
    res['indirect']['EA'],
    res['index']['EA'],
    res['base']['EA'],
    res['relative']['EA'],
]
for name, ea in zip(['直接', '间接', '变址', '基址', '相对'], all_eas):
    assert M(ea) is not None, f"{name}寻址EA=0x{ea:04X}不在主存表中"
print("  [PASS] 条件6: 五种寻址方式的 EA 均命中主存表")

print()
print("ALL ASSERTS PASSED ✓")
