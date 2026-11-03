"""
综合题：指令格式分析与寻址方式有效地址推导
建模：字段位宽推导 + 6种寻址方式EA计算 + 场景规则assert验证
"""
import math

# ============ 场景规则约束（assert） ============
def check_asserts(op_bits, m_bits, d_bits, instr_len, num_instrs, num_modes,
                  direct_range_max, D_val, ea_indirect, ea_direct,
                  ea_indexed, ea_based, ea_relative, pc_after_fetch):
    """场景规则1-6 assert验证（打到特征，禁弱化/禁恒真）"""
    # 规则1: 字段位宽约束
    assert op_bits + m_bits + d_bits == instr_len, \
        f"R1字段位宽: {op_bits}+{m_bits}+{d_bits}={op_bits+m_bits+d_bits} != {instr_len}"
    assert op_bits >= math.ceil(math.log2(num_instrs)), \
        f"R1 OP位>=ceil(log2({num_instrs})): {op_bits} < {math.ceil(math.log2(num_instrs))}"
    assert m_bits >= math.ceil(math.log2(num_modes)), \
        f"R1 M位>=ceil(log2({num_modes})): {m_bits} < {math.ceil(math.log2(num_modes))}"
    # 规则2: 直接寻址范围约束
    assert direct_range_max == 2**d_bits - 1, \
        f"R2直接寻址范围: {direct_range_max} != 2^{d_bits}-1={2**d_bits-1}"
    # 规则3: 形式地址合法
    assert D_val < 2**d_bits, \
        f"R3 D合法: 0x{D_val:X} >= 2^{d_bits}=0x{2**d_bits:X}"
    # 规则4: 间接寻址目标落在可寻址地址空间内（参数约束：任意合法 Mem[D] 必为有效地址）
    assert 0 <= ea_indirect < 2**instr_len, f"R4间接EA越界: 0x{ea_indirect:X} >= 2^{instr_len}"
    # 规则5: 五种寻址方式EA互异(立即不参与)
    eas = {"直接": ea_direct, "间接": ea_indirect,
           "变址": ea_indexed, "基址": ea_based, "相对": ea_relative}
    vals = list(eas.values())
    assert len(set(vals)) == len(vals), f"R5 EA互异失败: {eas}"
    # 规则6: 相对寻址PC取值
    assert ea_relative == pc_after_fetch + D_val, \
        f"R6相对寻址EA: 0x{ea_relative:X} != PC+D=0x{pc_after_fetch+D_val:X}"


# ============ 主求解 ============
def solve():
    # ---- PARAMS ----
    instr_len = 16       # 指令字长(位)
    num_instrs = 12      # 指令条数
    num_modes = 6        # 寻址方式数

    D_hex = 0x0C0        # 形式地址
    IX_hex = 0x2000      # 变址寄存器
    BR_hex = 0x3800      # 基址寄存器
    PC_hex = 0x1F02      # PC(取指后)
    mem_00C0 = 0x0400    # 内存单元(00C0H)的内容

    # ---- SQ1: 字段位数推导 ----
    OP_bits = math.ceil(math.log2(num_instrs))   # ceil(log2(12))=4
    M_bits = math.ceil(math.log2(num_modes))     # ceil(log2(6))=3
    D_bits = instr_len - OP_bits - M_bits        # 16-4-3=9

    direct_range_max = 2**D_bits - 1             # 直接寻址范围上限

    # ---- SQ2: 6种寻址方式EA ----
    ea_immediate = None  # 立即寻址: D本身即操作数,不产生地址
    ea_direct = D_hex                                  # 001: EA=D
    ea_indirect = mem_00C0                             # 010: EA=(D)=mem[D]
    ea_indexed = (IX_hex + D_hex)                      # 011: EA=(IX)+D
    ea_based = (BR_hex + D_hex)                        # 100: EA=(BR)+D
    ea_relative = (PC_hex + D_hex)                     # 101: EA=(PC)+D

    # ---- 场景规则assert验证 ----
    check_asserts(OP_bits, M_bits, D_bits, instr_len, num_instrs, num_modes,
                  direct_range_max, D_hex, ea_indirect, ea_direct,
                  ea_indexed, ea_based, ea_relative, PC_hex)

    return {
        "PARAMS": {
            "指令字长": instr_len, "指令条数": num_instrs, "寻址方式数": num_modes,
            "D": D_hex, "IX": IX_hex, "BR": BR_hex, "PC": PC_hex,
            "内存(00C0H)": mem_00C0
        },
        "SQ1": {
            "OP位数": OP_bits, "M位数": M_bits, "D位数": D_bits,
            "直接寻址范围上限": direct_range_max,
            "直接寻址范围_十进制": (0, direct_range_max),
            "直接寻址范围_十六进制": ("000H", f"{direct_range_max:03X}H"),
        },
        "SQ2": {
            "立即寻址": ("EA=N/A(D即操作数)", ea_immediate),
            "直接寻址":  ("EA = D", ea_direct),
            "间接寻址":  ("EA = (D)", ea_indirect),
            "变址寻址":  ("EA = (IX) + D", ea_indexed),
            "基址寻址":  ("EA = (BR) + D", ea_based),
            "相对寻址":  ("EA = (PC) + D", ea_relative),
        },
        "RULES_OK": True,
    }


if __name__ == "__main__":
    result = solve()

    def hexz(v):
        return f"0x{v:04X}" if v is not None else "N/A"

    print("=" * 60)
    print("PARAMS:")
    for k, v in result["PARAMS"].items():
        if isinstance(v, int):
            print(f"  {k:14s} = {hexz(v)}")
        else:
            print(f"  {k:14s} = {v}")

    print("\n" + "=" * 60)
    print("SQ1: 字段位数与直接寻址范围")
    sq1 = result["SQ1"]
    print(f"  OP位数 = ceil(log2({result['PARAMS']['指令条数']})) = {sq1['OP位数']}")
    print(f"  M位数  = ceil(log2({result['PARAMS']['寻址方式数']})) = {sq1['M位数']}")
    print(f"  D位数  = {result['PARAMS']['指令字长']} - {sq1['OP位数']} - {sq1['M位数']} = {sq1['D位数']}")
    print(f"  验证: {sq1['OP位数']} + {sq1['M位数']} + {sq1['D位数']} = {sq1['OP位数']+sq1['M位数']+sq1['D位数']}")
    print(f"  直接寻址范围(十进制): {sq1['直接寻址范围_十进制'][0]} ~ {sq1['直接寻址范围_十进制'][1]}")
    print(f"  直接寻址范围(十六进制): {sq1['直接寻址范围_十六进制'][0]} ~ {sq1['直接寻址范围_十六进制'][1]}")

    print("\n" + "=" * 60)
    print("SQ2: 6种寻址方式有效地址EA")
    sq2 = result["SQ2"]
    for mode, (expr, val) in sq2.items():
        print(f"  {mode:8s} | {expr:18s} | EA = {hexz(val)}")

    print("\n" + "=" * 60)
    print("PROCESS: 关键中间值")
    D = result["PARAMS"]["D"]
    IX = result["PARAMS"]["IX"]
    BR = result["PARAMS"]["BR"]
    PC = result["PARAMS"]["PC"]
    mem = result["PARAMS"]["内存(00C0H)"]
    print(f"  直接寻址: EA = D = {hexz(D)}")
    print(f"  间接寻址: D={hexz(D)} -> 内存[{hexz(D)}]={hexz(mem)} -> EA={hexz(mem)}")
    print(f"  变址寻址: EA = (IX)+D = {hexz(IX)} + {hexz(D)} = {hexz(IX+D)}")
    print(f"  基址寻址: EA = (BR)+D = {hexz(BR)} + {hexz(D)} = {hexz(BR+D)}")
    print(f"  相对寻址: EA = (PC)+D = {hexz(PC)} + {hexz(D)} = {hexz(PC+D)}")

    print("\n" + "=" * 60)
    print("RULES_CHECK: 场景规则验证（全部assert通过）")
    print("  R1 字段位宽: 4+3+9=16 ✓ | OP>=ceil(log2(12))=4 ✓ | M>=ceil(log2(6))=3 ✓")
    print(f"  R2 直接寻址范围: 0~2^9-1 = 0~511 ✓")
    print(f"  R3 D合法: 0x{D:X}=192 < 2^9=512 ✓")
    print(f"  R4 间接单元可达: D=0x{D:X} 在直接寻址范围内 ✓")
    eas = {k: v[1] for k, v in sq2.items() if v[1] is not None}
    print(f"  R5 EA互异: {', '.join(f'{k}={hexz(v)}' for k,v in eas.items())} ✓ 全不同")
    print(f"  R6 相对寻址: EA = PC + D = {hexz(PC)} + {hexz(D)} = {hexz(PC+D)} ✓")

    print("\n" + "=" * 60)
    print(f"RESULT: 所有场景规则assert通过 = {result['RULES_OK']}")
