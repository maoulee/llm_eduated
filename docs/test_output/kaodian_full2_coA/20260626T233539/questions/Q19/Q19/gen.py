"""
多种寻址方式有效地址计算 —— 建模码
按字编址，双字长指令（占2个字地址），5种寻址方式。
把题干声明的场景规则逐句翻译成代码，底部 print 完整数据流。
"""

# ==================== 输入参数 ====================
A   = 0x0040   # 形式地址
Rx  = 0x0018   # 变址寄存器
Rb  = 0x0020   # 基址寄存器

# 当前指令首地址（双字指令占 0x000E 和 0x000F 两个字地址）
INSTR_ADDR = 0x000E
INSTRUCTION_WORDS = 2            # 双字长指令占 2 个字地址
PC_updated = INSTR_ADDR + INSTRUCTION_WORDS   # 取指后 PC = 0x0010（下一条指令地址）

# 主存内容表（按字编址，地址 -> 内容）
MEMORY = {
    0x0040: 0x0048,
    0x0048: 0x1234,
    0x004E: 0xABCD,
    0x0050: 0x5678,
    0x0058: 0x9ABC,
    0x0060: 0xDEF0,
    0x0068: 0x1111,
}

def M(addr):
    """访存：返回主存 addr 单元的内容。"""
    return MEMORY[addr]


# ==================== 五种寻址方式（逐句翻译题干公式） ====================

def direct_addressing(A):
    """直接寻址：EA = A；操作数 = M[A]"""
    EA = A
    operand = M(EA)
    mem_accesses = 1
    return EA, operand, mem_accesses

def indirect_addressing(A):
    """间接寻址：EA = M[A]（读指针）；操作数 = M[M[A]]（再取数）；至少 2 次访存"""
    ptr = M(A)           # 第1次访存：读出指针
    EA = ptr             # 有效地址 = 指针
    operand = M(EA)      # 第2次访存：取操作数
    mem_accesses = 2
    return EA, operand, mem_accesses

def relative_addressing(A):
    """相对寻址：EA = PC_updated + A；操作数 = M[EA]"""
    EA = PC_updated + A
    operand = M(EA)
    mem_accesses = 1
    return EA, operand, mem_accesses

def indexed_addressing(A):
    """变址寻址：EA = Rx + A；操作数 = M[EA]"""
    EA = Rx + A
    operand = M(EA)
    mem_accesses = 1
    return EA, operand, mem_accesses

def based_addressing(A):
    """基址寻址：EA = Rb + A；操作数 = M[EA]"""
    EA = Rb + A
    operand = M(EA)
    mem_accesses = 1
    return EA, operand, mem_accesses


# ==================== 求解 ====================

ea1, op1, m1 = direct_addressing(A)
ea2, op2, m2 = indirect_addressing(A)
ea3, op3, m3 = relative_addressing(A)
ea4, op4, m4 = indexed_addressing(A)
ea5, op5, m5 = based_addressing(A)

# 相对寻址陷阱：误用当前指令地址而非 PC_updated
ea3_trap = INSTR_ADDR + A        # 错误 EA = 0x000E + 0x0040
trap_in_memory = ea3_trap in MEMORY


# ==================== 场景规则 assert（题干通过条件翻译） ====================

# 规则1-5: 各寻址公式约束（定义层），已在函数实现中忠实翻译
# 规则6: 所有 EA 及间接寻址中间指针均能在主存表查到
all_EAs = [ea1, ea2, ea3, ea4, ea5]
for ea in all_EAs:
    assert ea in MEMORY, f"EA 0x{ea:04X} 不在主存表中"
assert M(A) in MEMORY, f"间接寻址中间指针 M[A]=0x{M(A):04X} 不在主存表中"

# 规则7: 五种有效地址互不相同
assert len(set(all_EAs)) == 5, f"有效地址不互不相同: {[hex(e) for e in all_EAs]}"

# 规则8: 五种操作数互不相同
all_ops = [op1, op2, op3, op4, op5]
assert len(set(all_ops)) == 5, f"操作数不互不相同: {[hex(o) for o in all_ops]}"

# 规则9: Rx != Rb
assert Rx != Rb, "Rx == Rb"

# 规则10: 相对寻址陷阱可区分 —— 错误 EA 也能在表中查到，但与正确 EA 不同
assert trap_in_memory, f"陷阱 EA 0x{ea3_trap:04X} 不在主存表中（无法产生貌似合理答案）"
assert ea3_trap != ea3, "陷阱 EA 与正确 EA 相同"

# 间接寻址访存次数 >= 2
assert m2 >= 2, "间接寻址访存次数 < 2"


# ==================== 底部打印完整数据流 ====================

def hx(v):
    return f"0x{v:04X}"

print("=" * 60)
print("PARAMS:")
print(f"  形式地址 A      = {hx(A)}")
print(f"  变址寄存器 Rx   = {hx(Rx)}")
print(f"  基址寄存器 Rb   = {hx(Rb)}")
print(f"  当前指令首地址  = {hx(INSTR_ADDR)}")
print(f"  指令占用字地址数= {INSTRUCTION_WORDS}")
print(f"  PC_updated(取指后) = {hx(PC_updated)}")
print(f"  主存表:")
for addr in sorted(MEMORY):
    print(f"    {hx(addr)} -> {hx(MEMORY[addr])}")

print("-" * 60)
print("PROCESS（各寻址方式推导）:")
print(f"  (1) 直接:   EA = A = {hx(A)} = {hx(ea1)};  操作数 = M[{hx(ea1)}] = {hx(op1)};  访存{m1}次")
print(f"  (2) 间接:   指针 = M[{hx(A)}] = {hx(M(A))};  EA = {hx(ea2)};  操作数 = M[{hx(ea2)}] = {hx(op2)};  访存{m2}次")
print(f"  (3) 相对:   EA = PC_updated + A = {hx(PC_updated)} + {hx(A)} = {hx(ea3)};  操作数 = M[{hx(ea3)}] = {hx(op3)};  访存{m3}次")
print(f"       陷阱:  误用PC=当前指令地址: {hx(INSTR_ADDR)} + {hx(A)} = {hx(ea3_trap)} -> {hx(M(ea3_trap)) if trap_in_memory else '不在表中'}")
print(f"  (4) 变址:   EA = Rx + A = {hx(Rx)} + {hx(A)} = {hx(ea4)};  操作数 = M[{hx(ea4)}] = {hx(op4)};  访存{m4}次")
print(f"  (5) 基址:   EA = Rb + A = {hx(Rb)} + {hx(A)} = {hx(ea5)};  操作数 = M[{hx(ea5)}] = {hx(op5)};  访存{m5}次")

print("-" * 60)
print("RESULT:")
print(f"  (1) 直接寻址:  EA = {hx(ea1)},  操作数 = {hx(op1)}")
print(f"  (2) 间接寻址:  EA = {hx(ea2)},  操作数 = {hx(op2)}")
print(f"  (3) 相对寻址:  EA = {hx(ea3)},  操作数 = {hx(op3)}")
print(f"  (4) 变址寻址:  EA = {hx(ea4)},  操作数 = {hx(op4)}")
print(f"  (5) 基址寻址:  EA = {hx(ea5)},  操作数 = {hx(op5)}")

print("-" * 60)
print("RULE_CHECK（场景规则验证）:")
print(f"  规则6 所有EA及间接指针在主存表: True")
print(f"  规则7 五种EA互不相同: {len(set(all_EAs)) == 5}")
print(f"         EA集合: {sorted([hx(e) for e in all_EAs])}")
print(f"  规则8 五种操作数互不相同: {len(set(all_ops)) == 5}")
print(f"         操作数集合: {sorted([hx(o) for o in all_ops])}")
print(f"  规则9 Rx != Rb: {Rx != Rb}  ({hx(Rx)} != {hx(Rb)})")
print(f"  规则10 陷阱EA在表中={trap_in_memory}, 陷阱EA={hx(ea3_trap)}, 正确EA={hx(ea3)}, 不同={ea3_trap != ea3}")
print(f"  间接访存次数={m2} >= 2: {m2 >= 2}")
print("=" * 60)
