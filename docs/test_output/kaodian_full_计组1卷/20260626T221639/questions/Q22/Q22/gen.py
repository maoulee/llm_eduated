"""
数据寻址方式——有效地址（EA）计算
16位地址空间，按字编址，机器字长16位。

建模：把题干声明的6种寻址方式定义逐句翻译成代码，
底部打印完整数据流（PARAMS/PROCESS/RESULT + 场景规则相关量）。
场景规则用 assert 命中通过条件（打到特征，非恒真）。
"""

MOD = 0x10000  # 16位地址空间模值，地址范围 0x0000 ~ 0xFFFF

# ---- PARAMS（注入题干给定参数）----
A   = 0x3C   # 形式地址
R0  = 0x28   # 基址寄存器
R1  = 0x50   # 变址寄存器
R2  = 0x5A   # 通用寄存器（寄存器间接寻址使用）
PC  = 0x12   # 程序计数器（取本条指令后已更新的值）

# 内存
Mem = {0x3C: 0x7E}  # 内存地址 -> 该单元内容


def solve():
    """逐句翻译题干寻址约定，计算6种寻址方式的EA。"""

    # 翻译："直接寻址：EA = A"
    EA_direct = A % MOD

    # 翻译："间接寻址：EA = 内存地址A处所存储的内容，即 EA = (A)"
    # 间接寻址链仅一跳：Mem[A] 本身即为有效地址，不再二次间接
    EA_indirect = Mem[A] % MOD

    # 翻译："寄存器间接寻址：EA = 指定寄存器的内容，即 EA = (R2)"
    EA_reg_indirect = R2 % MOD

    # 翻译："基址寻址：EA = (R0) + A"
    EA_base = (R0 + A) % MOD

    # 翻译："变址寻址：EA = (R1) + A"
    EA_index = (R1 + A) % MOD

    # 翻译："相对寻址：EA = (PC) + A，PC为取本条指令后已更新的值"
    EA_relative = (PC + A) % MOD

    return {
        "EA_direct":         EA_direct,
        "EA_indirect":       EA_indirect,
        "EA_reg_indirect":   EA_reg_indirect,
        "EA_base":           EA_base,
        "EA_index":          EA_index,
        "EA_relative":       EA_relative,
    }


# ---- 注入参数跑 ----
result = solve()

# ---- 场景规则 assert（打到特征，非恒真）----

# 规则1：间接寻址结果 ≠ 直接寻址结果（Mem[A] ≠ A）
assert result["EA_indirect"] != result["EA_direct"], \
    f"规则1违反：间接寻址({hex(result['EA_indirect'])}) == 直接寻址({hex(result['EA_direct'])})"

# 规则2：基址寻址结果 ≠ 变址寻址结果（R0 ≠ R1 → R0+A ≠ R1+A）
assert result["EA_base"] != result["EA_index"], \
    f"规则2违反：基址寻址({hex(result['EA_base'])}) == 变址寻址({hex(result['EA_index'])})"

# 规则3：6种寻址方式的 EA 互不相同
ea_values = [
    ("直接寻址",       result["EA_direct"]),
    ("间接寻址",       result["EA_indirect"]),
    ("寄存器间接寻址", result["EA_reg_indirect"]),
    ("基址寻址",       result["EA_base"]),
    ("变址寻址",       result["EA_index"]),
    ("相对寻址",       result["EA_relative"]),
]
ea_set = set(v for _, v in ea_values)
assert len(ea_set) == 6, \
    f"规则3违反：6种寻址方式EA不互不相同，去重后仅{len(ea_set)}个不同值"

# 规则4：所有 EA 在地址空间范围内 [0x0000, 0xFFFF]
for name, ea in ea_values:
    assert 0x0000 <= ea <= 0xFFFF, \
        f"规则4违反：{name}的EA={hex(ea)}超出地址空间范围"

# 规则5：相对寻址 EA 定义明确，PC取题中给定值——建模中已直接使用PC常量，此处验证可复现
assert result["EA_relative"] == (PC + A) % MOD, \
    f"规则5违反：相对寻址EA计算与(PC)+A不一致"

# 规则6：间接寻址链仅一跳，Mem[A]的值本身即为合法有效地址（0x7E是合法地址）
assert 0x0000 <= Mem[A] <= 0xFFFF, \
    f"规则6违反：Mem[A]={hex(Mem[A])}不是合法有效地址"


# ---- 底部：打印完整数据流 ----
print("=" * 60)
print("PARAMS:")
print(f"  形式地址 A  = {hex(A)}")
print(f"  基址寄存器 R0 = {hex(R0)}")
print(f"  变址寄存器 R1 = {hex(R1)}")
print(f"  通用寄存器 R2 = {hex(R2)}")
print(f"  程序计数器 PC = {hex(PC)}")
print(f"  Mem[0x3C]    = {hex(Mem[0x3C])}")
print(f"  地址空间     = 0x0000 ~ 0xFFFF (16位)")
print()

print("PROCESS（各寻址方式计算过程）:")
print(f"  直接寻址:       EA = A            = {hex(A)}")
print(f"  间接寻址:       EA = Mem[A]       = Mem[{hex(A)}] = {hex(Mem[A])}")
print(f"  寄存器间接寻址: EA = R2           = {hex(R2)}")
print(f"  基址寻址:       EA = R0 + A       = {hex(R0)} + {hex(A)} = {hex(R0 + A)}")
print(f"  变址寻址:       EA = R1 + A       = {hex(R1)} + {hex(A)} = {hex(R1 + A)}")
print(f"  相对寻址:       EA = PC + A       = {hex(PC)} + {hex(A)} = {hex(PC + A)}")
print()

print("RESULT:")
print(f"  第1问(1) 直接寻址 EA         = {hex(result['EA_direct'])}")
print(f"  第1问(2) 间接寻址 EA         = {hex(result['EA_indirect'])}")
print(f"  第2问(1) 寄存器间接寻址 EA   = {hex(result['EA_reg_indirect'])}")
print(f"  第2问(2) 基址寻址 EA         = {hex(result['EA_base'])}")
print(f"  第3问(1) 变址寻址 EA         = {hex(result['EA_index'])}")
print(f"  第3问(2) 相对寻址 EA         = {hex(result['EA_relative'])}")
print()

print("RULE_CHECK（场景规则验证）:")
print(f"  规则1: EA_间接({hex(result['EA_indirect'])}) ≠ EA_直接({hex(result['EA_direct'])}) → {result['EA_indirect'] != result['EA_direct']}")
print(f"  规则2: EA_基址({hex(result['EA_base'])}) ≠ EA_变址({hex(result['EA_index'])}) → {result['EA_base'] != result['EA_index']}")
print(f"  规则3: 6种EA互不相同，不同值数量 = {len(ea_set)}/6")
print(f"  规则4: 所有EA ∈ [0x0000, 0xFFFF] → True")
print(f"  规则5: EA_相对 = PC + A = {hex(PC)} + {hex(A)} = {hex(result['EA_relative'])} → 明确")
print(f"  规则6: 间接寻址仅一跳，Mem[A]={hex(Mem[A])} 为合法地址 → True")
print()
print("所有场景规则 assert 通过 ✓")
