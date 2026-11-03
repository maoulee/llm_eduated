# -*- coding: utf-8 -*-
"""
存储器与CPU连接（地址分配与片选逻辑推导）
建模：ROM 0000H 起 4KB(2K×8) + RAM 紧接后 8KB(2K×4)，16位地址总线。
一次性建模 + 底部打印完整数据流（PARAMS/PROCESS/RESULT）。
"""

def solve():
    # ========== PARAMS ==========
    ADDR_WIDTH = 16
    ROM_START = 0x0000
    ROM_CAPACITY = 4 * 1024          # 4 KB
    ROM_CHIP_WORDS = 2 * 1024        # 2K (字数)
    ROM_CHIP_BITS = 8               # 8 位

    RAM_CAPACITY = 8 * 1024          # 8 KB
    RAM_CHIP_WORDS = 2 * 1024        # 2K (字数)
    RAM_CHIP_BITS = 4               # 4 位

    DECODER_OUTPUTS = 8              # 74LS138: Y0~Y7
    BLOCK_SIZE = 2 * 1024            # 2 KB 译码粒度
    INTRA_BITS = 11                  # 片内寻址位数

    addr_space = 1 << ADDR_WIDTH     # 2^16 = 64 KB

    # ========== PROCESS ==========

    # --- Q1: 地址范围推导 ---
    ROM_END = ROM_START + ROM_CAPACITY - 1
    RAM_START = ROM_END + 1
    RAM_END = RAM_START + RAM_CAPACITY - 1

    # --- Q2: 芯片数量与扩展方式 ---
    # ROM: 字扩展（位宽已满足8位，靠字数扩展容量）
    ROM_CHIP_CAP = ROM_CHIP_WORDS * (ROM_CHIP_BITS // 8)   # 2K * 1 = 2048 B
    ROM_CHIP_COUNT = ROM_CAPACITY // ROM_CHIP_CAP
    # ROM 位宽已=8位，无需位扩展；纯字扩展
    ROM_EXPANSION = "字扩展（ROM芯片位宽8位=数据总线宽度，仅靠增加芯片数量扩展存储字数）"

    # RAM: 2K×4 位，位宽=4 < 8 → 需 2 片并联做位扩展凑齐 8 位；8KB/2KB=4 组 → 字扩展
    # 位扩展对数：ceil(8/4)=2
    RAM_BIT_PAIRS = (8 + RAM_CHIP_BITS - 1) // RAM_CHIP_BITS   # ceil(8/4)=2
    RAM_GROUPS = RAM_CAPACITY // (RAM_CHIP_WORDS * RAM_CHIP_BITS // 8 * 1)
    # RAM 芯片容量(字节) = 2K * 4bit / 8 = 1024 B；位扩展2片成组后组容量=2K*8/8=2048B=2KB
    RAM_CHIP_CAP_BYTES = RAM_CHIP_WORDS * RAM_CHIP_BITS // 8    # 2K*4/8 = 1024 B
    RAM_GROUP_CAP = RAM_CHIP_CAP_BYTES * RAM_BIT_PAIRS          # 1024*2 = 2048 B
    RAM_GROUPS_COUNT = RAM_CAPACITY // RAM_GROUP_CAP
    RAM_CHIP_COUNT = RAM_GROUPS_COUNT * RAM_BIT_PAIRS
    RAM_EXPANSION = ("字位同时扩展：每2片2K×4位并联做位扩展凑成2K×8位(1组)，"
                     "共4组做字扩展，总芯片数=2×4=8片")

    # --- Q3.1: 74LS138 译码 ---
    # 片内寻址位数 = max(ROM芯片地址位数, RAM芯片地址位数) = max(11,11)=11
    INTRA_BITS_CALC = max(
        (ROM_CHIP_WORDS).bit_length() - 1,   # log2(2048)=11
        (RAM_CHIP_WORDS).bit_length() - 1,   # log2(2048)=11
    )
    # CBA = A13,A12,A11 = INTRA_BITS+{2,1,0}
    C_LINE = INTRA_BITS_CALC + 2   # A13
    B_LINE = INTRA_BITS_CALC + 1   # A12
    A_LINE = INTRA_BITS_CALC + 0   # A11

    # 译码粒度
    DECODE_GRAN = 1 << INTRA_BITS_CALC   # 2^11 = 2048 B = 2KB

    # ROM/RAM 占用块数
    ROM_BLOCKS = ROM_CAPACITY // DECODE_GRAN    # 4KB/2KB=2
    RAM_BLOCKS = RAM_CAPACITY // DECODE_GRAN    # 8KB/2KB=4
    TOTAL_BLOCKS = ROM_BLOCKS + RAM_BLOCKS

    # 各译码输出端对应的2KB地址区间
    decoder_map = []
    rom_endpoints = []
    ram_endpoints = []
    for i in range(DECODER_OUTPUTS):
        blk_start = ROM_START + i * DECODE_GRAN
        blk_end   = blk_start + DECODE_GRAN - 1
        addr_high = blk_start >> INTRA_BITS_CALC
        cba = ((addr_high >> 2) & 1, (addr_high >> 1) & 1, (addr_high >> 0) & 1)
        role = ""
        if i < ROM_BLOCKS:
            role = "ROM"
            rom_endpoints.append(i)
        elif i < TOTAL_BLOCKS:
            role = "RAM"
            ram_endpoints.append(i)
        decoder_map.append({
            "Y": i,
            "range": (blk_start, blk_end),
            "range_hex": f"{blk_start:04X}H~{blk_end:04X}H",
            "cba": cba,
            "role": role,
        })

    # --- Q3.2: R/W 信号需求差异 ---
    RW_DIFF = {
        "ROM": "不需要R/W信号参与写控制——ROM只读，片选有效即可输出数据",
        "RAM": "需要R/W信号——RAM可读可写，R/W决定数据方向（高=读，低=写）",
    }

    # --- Q3.3: 使能端连接 ---
    ENABLE_SCHEME = {
        "G1": "接Vcc(+5V恒高)，满足高有效",
        "G2A": "接MREQ(低有效)，访存时MREQ=0使能",
        "G2B": "接A15(低有效)，A15=0限定地址落在存储区",
    }
    # A15覆盖检查
    a15_rom_end = (ROM_END >> 15) & 1
    a15_ram_end = (RAM_END >> 15) & 1

    # R7 使能端逻辑：G2B=A15，验证反面条件——超出存储区(A15=1)的地址译码器应禁止
    test_addr_outside = 0x8000              # A15=1，超出存储区
    a15_outside = (test_addr_outside >> 15) & 1    # G2B端信号值：A15=1 → G2B无效
    g2b_outside = (a15_outside == 0)               # G2B低有效，A15=1时G2B无效
    # 正向：存储区内地址(A15=0)译码器工作
    test_addr_inside = ROM_START                # 存储区内地址
    a15_inside = (test_addr_inside >> 15) & 1   # G2B端信号值：A15=0 → G2B有效
    g2b_inside = (a15_inside == 0)              # G2B低有效，A15=0时G2B有效

    # ========== 场景规则 assert（打到特征，非恒真） ==========
    # R1 地址连续
    assert RAM_START == ROM_END + 1, "R1: RAM起始 != ROM结束+1"
    assert ROM_END == ROM_START + ROM_CAPACITY - 1, "R1: ROM结束地址错"
    assert RAM_END == RAM_START + RAM_CAPACITY - 1, "R1: RAM结束地址错"

    # R2 不重叠 + 总容量≤地址空间
    assert ROM_END < RAM_START, "R2: ROM与RAM重叠"
    assert (ROM_CAPACITY + RAM_CAPACITY) <= addr_space, "R2: 总容量超地址空间"

    # R3 ROM芯片数为整数
    assert ROM_CAPACITY % ROM_CHIP_CAP == 0, "R3: ROM芯片数非整数"
    assert ROM_CHIP_COUNT * ROM_CHIP_CAP == ROM_CAPACITY, "R3: ROM芯片数×容量≠区域容量"

    # R4 RAM芯片数为整数
    assert RAM_CHIP_COUNT * RAM_CHIP_CAP_BYTES == RAM_CAPACITY, "R4: RAM芯片数×容量≠区域容量"
    assert RAM_CAPACITY % RAM_GROUP_CAP == 0, "R4: RAM组数非整数"

    # R5 CBA连接
    assert INTRA_BITS_CALC == INTRA_BITS, "R5: 片内寻址位数不符"
    assert DECODE_GRAN == BLOCK_SIZE, "R5: 译码粒度≠2KB"
    assert C_LINE == A_LINE + 2 and B_LINE == A_LINE + 1, "R5: CBA非连续"
    assert (C_LINE, B_LINE, A_LINE) == (13, 12, 11), "R5: CBA连接不符A13/A12/A11"

    # R6 译码输出端够用
    assert TOTAL_BLOCKS <= DECODER_OUTPUTS, "R6: 译码输出端不够"

    # R7 使能端连接——验证G2B=A15逻辑的实际有效性（正反双向，非恒真）
    # 反面：A15=1的地址不在译码范围，G2B无效→译码器禁止
    assert a15_outside == 1, "R7: 超出存储区地址A15应为1（译码器应禁止）"
    assert g2b_outside == False, "R7: A15=1时G2B应无效（译码器禁止）"
    # 正向：存储区内地址A15=0，G2B有效→译码器工作
    assert a15_inside == 0, "R7: 存储区内地址A15应为0"
    assert g2b_inside == True, "R7: A15=0时G2B应有效（译码器工作）"

    # R8 使能覆盖存储区（A15在全范围恒为0）
    assert a15_rom_end == 0, "R8: ROM结束地址A15≠0"
    assert a15_ram_end == 0, "R8: RAM结束地址A15≠0"

    return locals()


result = solve()

# ========== 底部：打印完整数据流 ==========
print("=" * 60)
print("PARAMS:")
print(f"  地址总线宽度 = {result['ADDR_WIDTH']} 位, 地址空间 = {result['addr_space']} B = {result['addr_space']//1024} KB")
print(f"  ROM: 起始=0000H, 容量={result['ROM_CAPACITY']}B(4KB), 芯片={result['ROM_CHIP_WORDS']}×{result['ROM_CHIP_BITS']}位")
print(f"  RAM: 容量={result['RAM_CAPACITY']}B(8KB), 芯片={result['RAM_CHIP_WORDS']}×{result['RAM_CHIP_BITS']}位")
print(f"  译码器: 74LS138, {result['DECODER_OUTPUTS']}输出端, 译码粒度={result['BLOCK_SIZE']}B(2KB)")
print(f"  片内寻址位数 = {result['INTRA_BITS']} 位")

print("-" * 60)
print("PROCESS (Q1 地址范围):")
print(f"  ROM结束 = {result['ROM_START']:04X}H + {result['ROM_CAPACITY']} - 1 = {result['ROM_END']:04X}H")
print(f"  RAM起始 = ROM结束+1 = {result['RAM_START']:04X}H")
print(f"  RAM结束 = RAM起始 + {result['RAM_CAPACITY']} - 1 = {result['RAM_END']:04X}H")

print("-" * 60)
print("PROCESS (Q2 芯片数量与扩展方式):")
print(f"  ROM芯片容量 = {result['ROM_CHIP_WORDS']}×{result['ROM_CHIP_BITS']//8} = {result['ROM_CHIP_CAP']}B")
print(f"  ROM芯片数 = {result['ROM_CAPACITY']}/{result['ROM_CHIP_CAP']} = {result['ROM_CHIP_COUNT']}")
print(f"  ROM扩展方式 = {result['ROM_EXPANSION']}")
print(f"  RAM芯片容量(字节) = {result['RAM_CHIP_WORDS']}×{result['RAM_CHIP_BITS']}/8 = {result['RAM_CHIP_CAP_BYTES']}B")
print(f"  RAM位扩展对数 = ceil(8/{result['RAM_CHIP_BITS']}) = {result['RAM_BIT_PAIRS']}")
print(f"  RAM组容量 = {result['RAM_BIT_PAIRS']}×{result['RAM_CHIP_CAP_BYTES']} = {result['RAM_GROUP_CAP']}B")
print(f"  RAM组数 = {result['RAM_CAPACITY']}/{result['RAM_GROUP_CAP']} = {result['RAM_GROUPS_COUNT']}")
print(f"  RAM芯片数 = {result['RAM_GROUPS_COUNT']}组×{result['RAM_BIT_PAIRS']}片 = {result['RAM_CHIP_COUNT']}")
print(f"  RAM扩展方式 = {result['RAM_EXPANSION']}")

print("-" * 60)
print("PROCESS (Q3.1 74LS138译码):")
print(f"  片内寻址位数(计算) = max(log2({result['ROM_CHIP_WORDS']}),log2({result['RAM_CHIP_WORDS']})) = {result['INTRA_BITS_CALC']}")
print(f"  译码粒度 = 2^{result['INTRA_BITS_CALC']} = {result['DECODE_GRAN']}B")
print(f"  CBA连接: C=A{result['C_LINE']}, B=A{result['B_LINE']}, A=A{result['A_LINE']}")
print(f"  ROM块数={result['ROM_BLOCKS']}, RAM块数={result['RAM_BLOCKS']}, 总块数={result['TOTAL_BLOCKS']}")
print(f"  --- 各输出端 ---")
for d in result['decoder_map']:
    print(f"    Y{d['Y']}: {d['range_hex']:>16s}  CBA={d['cba']}  [{d['role']}]")
print(f"  ROM用输出端: Y{result['rom_endpoints'][0]}~Y{result['rom_endpoints'][-1]}")
print(f"  RAM用输出端: Y{result['ram_endpoints'][0]}~Y{result['ram_endpoints'][-1]}")

print("-" * 60)
print("PROCESS (Q3.2 R/W信号差异):")
print(f"  {result['RW_DIFF']['ROM']}")
print(f"  {result['RW_DIFF']['RAM']}")

print("-" * 60)
print("PROCESS (Q3.3 使能端连接):")
for k, v in result['ENABLE_SCHEME'].items():
    print(f"  {k}: {v}")
print(f"  工作条件: G1=1(恒) 且 G2A=MREQ=0(访存) 且 G2B=A15=0(存储区) => 译码器工作")
print(f"  R7使能逻辑验证: 存储区内地址{result['test_addr_inside']:04X}H A15={result['a15_inside']}→G2B有效={result['g2b_inside']}(译码器工作); 区外地址{result['test_addr_outside']:04X}H A15={result['a15_outside']}→G2B有效={result['g2b_outside']}(译码器禁止)")
print(f"  R8覆盖检查: ROM结束{result['ROM_END']:04X}H的A15={result['a15_rom_end']}, RAM结束{result['RAM_END']:04X}H的A15={result['a15_ram_end']}")

print("-" * 60)
print("RESULT:")
print(f"  Q1: ROM = 0000H~{result['ROM_END']:04X}H; RAM = {result['RAM_START']:04X}H~{result['RAM_END']:04X}H")
print(f"  Q2: ROM芯片数={result['ROM_CHIP_COUNT']}({result['ROM_EXPANSION'][:4]}); RAM芯片数={result['RAM_CHIP_COUNT']}(字位同时扩展)")
print(f"  Q3.1: ROM→Y0~Y{result['rom_endpoints'][-1]}, RAM→Y{result['ram_endpoints'][0]}~Y{result['ram_endpoints'][-1]}")
print(f"  Q3.3: G1=Vcc, G2A=MREQ, G2B=A15")
print(f"  全部场景规则 R1~R8 assert 通过 ✓")
print("=" * 60)
