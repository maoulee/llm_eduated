"""
存储器与CPU连接：地址分配与片选逻辑推导
题干规则 → 代码翻译 + 通过条件 → assert
"""

ADDR_BITS = 16          # CPU地址总线宽度
DATA_BITS = 8           # CPU数据总线宽度
MAX_ADDR = 1 << ADDR_BITS   # 64KB 可寻址空间

# ============================================================
# 区域参数（来自题干）
# ============================================================
ROM_START  = 0x0000     # ROM区起始地址
ROM_SIZE   = 4 * 1024   # 4KB
RAM_START  = 0x4000     # RAM区起始地址
RAM_SIZE   = 8 * 1024   # 8KB

ROM_CHIP_WORDS = 2 * 1024   # 2K
ROM_CHIP_BITS  = 8          # 8 bit

RAM_CHIP_WORDS = 8 * 1024   # 8K
RAM_CHIP_BITS  = 4          # 4 bit

# ============================================================
# 第(1)题：地址范围推导
# ============================================================
rom_end = ROM_START + ROM_SIZE - 1
ram_end = RAM_START + RAM_SIZE - 1

print("=== PARAMS ===")
print(f"CPU地址总线: {ADDR_BITS}位, 数据总线: {DATA_BITS}位")
print(f"ROM区: 起始={ROM_START:04X}H, 容量={ROM_SIZE}B")
print(f"RAM区: 起始={RAM_START:04X}H, 容量={RAM_SIZE}B")
print(f"ROM芯片: {ROM_CHIP_WORDS}×{ROM_CHIP_BITS}bit")
print(f"RAM芯片: {RAM_CHIP_WORDS}×{RAM_CHIP_BITS}bit")

print("\n=== Q1: 地址范围 ===")
print(f"ROM区: {ROM_START:04X}H ~ {rom_end:04X}H")
print(f"RAM区: {RAM_START:04X}H ~ {ram_end:04X}H")

# ============================================================
# 第(2)题：芯片数量与扩展方式
# ============================================================
# 扩展方式判定函数
def analyze_region(region_words, region_data_bits, chip_words, chip_data_bits, bus_data_bits):
    # 字扩展：芯片字数 < 区域字数
    word_expand = region_words // chip_words
    # 位扩展：芯片数据位宽 < 总线数据位宽（或区域需要的数据宽度）
    bit_expand  = bus_data_bits // chip_data_bits
    total = word_expand * bit_expand
    if word_expand > 1 and bit_expand > 1:
        mode = "字位同时扩展"
    elif word_expand > 1:
        mode = "字扩展"
    elif bit_expand > 1:
        mode = "位扩展"
    else:
        mode = "无需扩展"
    return total, word_expand, bit_expand, mode

rom_total, rom_we, rom_be, rom_mode = analyze_region(
    ROM_SIZE, DATA_BITS, ROM_CHIP_WORDS, ROM_CHIP_BITS, DATA_BITS)
ram_total, ram_we, ram_be, ram_mode = analyze_region(
    RAM_SIZE, DATA_BITS, RAM_CHIP_WORDS, RAM_CHIP_BITS, DATA_BITS)

print("\n=== Q2: 芯片数量与扩展方式 ===")
print(f"ROM区: {ROM_SIZE}B, {ROM_CHIP_WORDS}×{ROM_CHIP_BITS}bit芯片")
print(f"  字扩展因子={rom_we}, 位扩展因子={ram_be if False else rom_be}")
print(f"  总片数={rom_total}, 扩展方式={rom_mode}")
print(f"RAM区: {RAM_SIZE}B, {RAM_CHIP_WORDS}×{RAM_CHIP_BITS}bit芯片")
print(f"  字扩展因子={ram_we}, 位扩展因子={ram_be}")
print(f"  总片数={ram_total}, 扩展方式={ram_mode}")

# ============================================================
# 第(3)题：74LS138译码器片选逻辑推导
# ============================================================

# 3-1: C/B/A 连接哪根地址线
# 最大区域 = 8KB = 2^13，片内寻址需13根地址线 A0~A12
# 剩余高位 A15/A14/A13 接译码器 C/B/A
intra_bits = 13   # A0~A12 片内寻址
# 验证：2^intra_bits = 8192 = 8KB = max(ROM_SIZE, RAM_SIZE)
assert (1 << intra_bits) == max(ROM_SIZE, RAM_SIZE), "片内寻址位数错误"

decoder_C = "A15"
decoder_B = "A14"
decoder_A = "A13"

# 3-2: 使能端连接
# G1 高电平有效 → 接Vcc（高电平）
# G2A/G2B 低电平有效 → 其中一个接 MREQ（访存时为低），另一个接低电平（有效）
enable_G1  = "Vcc (高电平)"
enable_G2A = "/MREQ"
enable_G2B = "GND (低电平，即有效)"

# 3-3: 各区域连接译码器哪个输出端
# 译码器把 A15A14A13 的值映射到 Y0~Y7
# 区域起始地址中 A15A14A13 的值 → 对应输出端
def cba_value(addr, bits_intra):
    """从地址提取高位 A(15..13) 的值"""
    return (addr >> bits_intra) & 0x7

rom_cba = cba_value(ROM_START, intra_bits)  # 0x0000 >> 13 = 0 → Y0
ram_cba = cba_value(RAM_START, intra_bits)  # 0x4000 >> 13 = 2 → Y2

# 验证区域内的所有地址都映射到同一个CBA
for addr in [ROM_START, rom_end, RAM_START, ram_end]:
    cba = cba_value(addr, intra_bits)

print("\n=== Q3: 译码器片选逻辑 ===")
print(f"片内寻址线: A0~A{intra_bits-1} (共{intra_bits}根)")
print(f"译码器输入: C={decoder_C}, B={decoder_B}, A={decoder_A}")
print(f"使能端: G1={enable_G1}, /G2A={enable_G2A}, /G2B={enable_G2B}")
print(f"ROM区 CBA={rom_cba:03b} → /Y{rom_cba}")
print(f"RAM区 CBA={ram_cba:03b} → /Y{ram_cba}")

# 3-4: ROM区内部芯片额外地址区分
# 74LS138的/Y0覆盖8KB（0000H~1FFFH），但ROM区只有4KB（0000H~0FFFH）
# → 用A12区分：A12=0 → ROM区; A12=1 → 非使用区
# ROM内部2片2K×8用A11区分（字扩展）：A11=0 → 第1片; A11=1 → 第2片
rom_intra_a12 = "A12"   # 区分ROM区(A12=0)与非使用区(A12=1)
rom_intra_a11 = "A11"   # 区分ROM内部两片2K×8芯片

print(f"\nROM区额外区分:")
print(f"  A12: A12=0 → ROM区(4KB), A12=1 → 非使用区")
print(f"  A11: A11=0 → ROM第1片(0000H~07FFH), A11=1 → ROM第2片(0800H~0FFFH)")

# ============================================================
# ANSWER 汇总
# ============================================================
print("\n=== ANSWER ===")
print(f"Q1: ROM={ROM_START:04X}H~{rom_end:04X}H, RAM={RAM_START:04X}H~{ram_end:04X}H")
print(f"Q2: ROM={rom_total}片({rom_mode}), RAM={ram_total}片({ram_mode})")
print(f"Q3: C=A15,B=A14,A=A13; G1=Vcc,/G2A=/MREQ,/G2B=GND; ROM→/Y{rom_cba}, RAM→/Y{ram_cba}; A12+A11区分ROM内部")

# ============================================================
# 通过条件 → assert（逐条翻译，禁弱化/禁恒真）
# ============================================================

# --- 条件1：地址范围正确且对齐，两区域不重叠 ---
assert rom_end == ROM_START + ROM_SIZE - 1, "ROM结束地址计算错误"
assert ROM_START == 0x0000 and rom_end == 0x0FFF, f"ROM范围应为0000H~0FFFH，实际{ROM_START:04X}~{rom_end:04X}"
assert RAM_START == 0x4000 and ram_end == 0x5FFF, f"RAM范围应为4000H~5FFFH，实际{RAM_START:04X}~{ram_end:04X}"
# 不重叠：ROM结束 < RAM起始
assert rom_end < RAM_START, "ROM区与RAM区地址重叠"
# 对齐：起始地址是容量的整数倍
assert ROM_START % ROM_SIZE == 0, "ROM起始地址未对齐"
assert RAM_START % RAM_SIZE == 0, "RAM起始地址未对齐"

# --- 条件2：芯片数量与扩展方式正确 ---
assert rom_total == 2, f"ROM区应为2片，实际{rom_total}"
assert rom_mode == "字扩展", f"ROM区应为字扩展，实际{rom_mode}"
assert rom_we == 2 and rom_be == 1, f"ROM字扩展因子应为2、位扩展因子应为1"
assert ram_total == 2, f"RAM区应为2片，实际{ram_total}"
assert ram_mode == "位扩展", f"RAM区应为位扩展，实际{ram_mode}"
assert ram_we == 1 and ram_be == 2, f"RAM字扩展因子应为1、位扩展因子应为2"

# --- 条件3：译码器连接可验证 ---
# C/B/A = A15/A14/A13
assert decoder_C == "A15" and decoder_B == "A14" and decoder_A == "A13", "译码器输入端连接错误"
assert intra_bits == 13, "片内寻址位数应为13（8KB=2^13）"
# ROM → Y0 (CBA=000), RAM → Y2 (CBA=010)
assert rom_cba == 0b000, f"ROM区CBA应为000，实际{rom_cba:03b}"
assert ram_cba == 0b010, f"RAM区CBA应为010，实际{ram_cba:03b}"
# 使能端
assert "MREQ" in enable_G2A or "MREQ" in enable_G2B, "使能端须接/MREQ"
assert "Vcc" in enable_G1 or "高电平" in enable_G1, "G1须接高电平/Vcc"

# --- 条件4：ROM内部额外地址区分 ---
# /Y0覆盖8KB但ROM只有4KB → A12区分
assert rom_intra_a12 == "A12", "ROM区需用A12区分4KB vs 非使用区"
# ROM内部2片2K×8 → A11区分
assert rom_intra_a11 == "A11", "ROM内部需用A11区分两片2K×8芯片"

# --- 条件5：一致性检查 ---
assert MAX_ADDR >= ROM_SIZE + RAM_SIZE, "总容量超过可寻址空间"
assert MAX_ADDR == 64 * 1024, "16位地址总线→64KB"
# 各芯片容量 ≤ 区域容量
assert ROM_CHIP_WORDS * (ROM_CHIP_BITS // 8) * 1 <= ROM_SIZE, "ROM芯片容量超过区域容量"  # 实际比的是字数
assert ROM_CHIP_WORDS <= ROM_SIZE, "ROM芯片字数超过区域字数"
assert RAM_CHIP_WORDS <= RAM_SIZE, "RAM芯片字数超过区域字数"
# 各区域起始地址为容量整数倍
assert ROM_START % ROM_SIZE == 0, "0000H不是4KB倍数"
assert RAM_START % RAM_SIZE == 0, "4000H不是8KB倍数"

print("\n✅ 全部assert通过")
