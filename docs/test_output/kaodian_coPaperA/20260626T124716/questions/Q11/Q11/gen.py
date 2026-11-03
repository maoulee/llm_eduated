"""
主存储器扩展与片选逻辑设计 —— 建模求解
题干规则翻译为代码，通过条件翻译为 assert。

题目参数：
- CPU: 16位地址总线(A15~A0), 8位数据总线(D7~D0)
- ROM区: 0000H起始, 16KB; RAM区: 紧接ROM区, 16KB
- ROM芯片: 4K×4位; RAM芯片: 8K×4位
- 全译码方式
"""
import itertools

# ============================================================
# PARAMS：题干参数
# ============================================================
ADDR_BITS = 16              # CPU 地址总线宽度
DATA_BITS = 8               # CPU 数据总线宽度
ADDR_SPACE = 1 << ADDR_BITS # 65536 = 64KB

ROM_REGION_CAP = 16 * 1024  # 16KB = 16384
RAM_REGION_CAP = 16 * 1024  # 16KB = 16384

ROM_CHIP_WORDS = 4 * 1024   # 4K 字
ROM_CHIP_BITS  = 4          # 4 位
RAM_CHIP_WORDS = 8 * 1024   # 8K 字
RAM_CHIP_BITS  = 4          # 4 位

ROM_START = 0x0000
RAM_START = ROM_START + ROM_REGION_CAP  # 紧接 ROM 区 = 0x4000

print("=== PARAMS ===")
print(f"ADDR_BITS={ADDR_BITS}, DATA_BITS={DATA_BITS}, ADDR_SPACE={ADDR_SPACE} ({ADDR_SPACE//1024}KB)")
print(f"ROM_REGION_CAP={ROM_REGION_CAP} ({ROM_REGION_CAP//1024}KB), RAM_REGION_CAP={RAM_REGION_CAP} ({RAM_REGION_CAP//1024}KB)")
print(f"ROM芯片: {ROM_CHIP_WORDS}×{ROM_CHIP_BITS}位, RAM芯片: {RAM_CHIP_WORDS}×{RAM_CHIP_BITS}位")
print(f"ROM_START={ROM_START:04X}H, RAM_START={RAM_START:04X}H")

# ============================================================
# Q1: 芯片数量计算（字位同时扩展）
# ============================================================

def calc_chips(region_cap, chip_words, chip_bits):
    """
    位扩展倍数 = 数据总线宽度 / 芯片位宽
    一组(位扩展后)的容量(字节) = chip_words × DATA_BITS / 8
      （位扩展后每字占DATA_BITS位=1字节，故组容量=chip_words字节）
    字扩展倍数 = 区域容量 / 组容量(字节)
    总芯片数 = 位扩展 × 字扩展
    """
    bit_expand = DATA_BITS // chip_bits
    group_bytes = chip_words * DATA_BITS // 8
    word_expand = region_cap // group_bytes
    total = bit_expand * word_expand
    return bit_expand, word_expand, total, group_bytes

rom_bit_ext, rom_word_ext, rom_total, rom_group_bytes = calc_chips(ROM_REGION_CAP, ROM_CHIP_WORDS, ROM_CHIP_BITS)
ram_bit_ext, ram_word_ext, ram_total, ram_group_bytes = calc_chips(RAM_REGION_CAP, RAM_CHIP_WORDS, RAM_CHIP_BITS)

print("\n=== Q1: 芯片数量 ===")
print(f"ROM: 位扩展={rom_bit_ext}倍, 字扩展={rom_word_ext}倍, 总芯片数={rom_total}")
print(f"  组容量(字节) = {ROM_CHIP_WORDS}字×{DATA_BITS}位/8 = {rom_group_bytes}字节")
print(f"  ROM芯片={rom_total}片 = 位扩展{rom_bit_ext}×字扩展{rom_word_ext}")
print(f"RAM: 位扩展={ram_bit_ext}倍, 字扩展={ram_word_ext}倍, 总芯片数={ram_total}")
print(f"  组容量(字节) = {RAM_CHIP_WORDS}字×{DATA_BITS}位/8 = {ram_group_bytes}字节")
print(f"  RAM芯片={ram_total}片 = 位扩展{ram_bit_ext}×字扩展{ram_word_ext}")

# ============================================================
# Q2: 地址范围（每个芯片组）
# ============================================================

# ROM芯片4K字 → 片内地址线=log2(4096)=12位 (A11~A0)
# RAM芯片8K字 → 片内地址线=log2(8192)=13位 (A12~A0)
ROM_CHIP_ADDR_BITS = 12   # 4K = 2^12
RAM_CHIP_ADDR_BITS = 13   # 8K = 2^13
ROM_HIGH_BITS = ADDR_BITS - ROM_CHIP_ADDR_BITS   # 16-12=4 (A15~A12)
RAM_HIGH_BITS = ADDR_BITS - RAM_CHIP_ADDR_BITS   # 16-13=3 (A15~A13)

rom_group_size = 1 << ROM_CHIP_ADDR_BITS   # 4K = 4096 字节（位扩展后每字1字节）
ram_group_size = 1 << RAM_CHIP_ADDR_BITS   # 8K = 8192 字节

print("\n=== Q2: 地址范围 ===")
print(f"ROM: 片内地址线={ROM_CHIP_ADDR_BITS}位(A{ROM_CHIP_ADDR_BITS-1}~A0), 高位地址线={ROM_HIGH_BITS}位(A{ADDR_BITS-1}~A{ROM_CHIP_ADDR_BITS})")
print(f"RAM: 片内地址线={RAM_CHIP_ADDR_BITS}位(A{RAM_CHIP_ADDR_BITS-1}~A0), 高位地址线={RAM_HIGH_BITS}位(A{ADDR_BITS-1}~A{RAM_CHIP_ADDR_BITS})")

rom_groups = []
for i in range(rom_word_ext):
    start = ROM_START + i * rom_group_size
    end   = start + rom_group_size - 1
    rom_groups.append((start, end))
    print(f"  ROM组{i}: {start:04X}H ~ {end:04X}H")

ram_groups = []
for i in range(ram_word_ext):
    start = RAM_START + i * ram_group_size
    end   = start + ram_group_size - 1
    ram_groups.append((start, end))
    print(f"  RAM组{i}: {start:04X}H ~ {end:04X}H")

# ============================================================
# Q3: 片选逻辑表达式
# ============================================================

def bits_to_cs_expr(top_bit_idx, value, num_high_bits):
    """
    将高位地址线的取值翻译成片选逻辑表达式字符串。
    top_bit_idx = 最高位地址线索引（如 ROM 的 A15）。
    value 为高位地址线的取值（num_high_bits 位二进制），
    从最高位到最低位依次对应 top_bit_idx, top_bit_idx-1, ..., top_bit_idx-num_high_bits+1。
    """
    terms = []
    for j in range(num_high_bits):
        bit_idx = top_bit_idx - j
        bit_val = (value >> (num_high_bits - 1 - j)) & 1
        if bit_val == 0:
            terms.append(f"~A{bit_idx}")
        else:
            terms.append(f"A{bit_idx}")
    return " · ".join(terms)

rom_top_bit = ADDR_BITS - 1   # A15
ram_top_bit = ADDR_BITS - 1   # A15

print("\n=== Q3: 片选逻辑表达式 ===")
rom_cs_exprs = []
for i, (start, end) in enumerate(rom_groups):
    high_val = start >> ROM_CHIP_ADDR_BITS   # 取高4位
    expr = bits_to_cs_expr(rom_top_bit, high_val, ROM_HIGH_BITS)
    rom_cs_exprs.append((i, high_val, expr))
    print(f"  ROM组{i} (CS_ROM{i}): 高位A15~A12={high_val:0{ROM_HIGH_BITS}b} → {expr}")

ram_cs_exprs = []
for i, (start, end) in enumerate(ram_groups):
    high_val = start >> RAM_CHIP_ADDR_BITS   # 取高3位
    expr = bits_to_cs_expr(ram_top_bit, high_val, RAM_HIGH_BITS)
    ram_cs_exprs.append((i, high_val, expr))
    print(f"  RAM组{i} (CS_RAM{i}): 高位A15~A13={high_val:0{RAM_HIGH_BITS}b} → {expr}")

# ============================================================
# 互斥性验证：枚举所有可能地址，检查至多一个片选有效
# ============================================================
print("\n=== 互斥性验证 ===")

# 对所有65536个地址，检查至多一个组被选中
# ROM组按A15~A12判别（4位），RAM组按A15~A13判别（3位）
# 但两者比较的实际地址范围应该互斥
mutual_exclusive = True
collision = None

def addr_in_rom(addr):
    for i, (gs, ge) in enumerate(rom_groups):
        if gs <= addr <= ge:
            return i
    return None

def addr_in_ram(addr):
    for i, (gs, ge) in enumerate(ram_groups):
        if gs <= addr <= ge:
            return i
    return None

# 检查ROM区与RAM区地址范围不重叠（ROM区=0x0000~0x3FFF, RAM区=0x4000~0x7FFF）
rom_region = (ROM_START, ROM_START + ROM_REGION_CAP - 1)
ram_region = (RAM_START, RAM_START + RAM_REGION_CAP - 1)

# 逐地址验证（抽样+边界），这里检查每组边界
# 实际上：任何地址要么在ROM组、要么在RAM组、要么在未使用区
for addr in range(ADDR_SPACE):
    rom_i = addr_in_rom(addr)
    ram_i = addr_in_ram(addr)
    if rom_i is not None and ram_i is not None:
        mutual_exclusive = False
        collision = (addr, ("ROM", rom_i), ("RAM", ram_i))
        break

print(f"互斥性检查(遍历全部{ADDR_SPACE}地址): {'通过（至多一个片选有效）' if mutual_exclusive else f'失败！碰撞={collision}'}")

# ============================================================
# ASSERT: 通过条件翻译
# ============================================================

print("\n=== ASSERT (通过条件验证) ===")

# --- 全局一致性 ---
assert ROM_REGION_CAP + RAM_REGION_CAP <= ADDR_SPACE, "ROM+RAM 总容量超出地址空间"
assert ROM_START == 0x0000, "ROM区起始地址必须为0000H"
assert RAM_START == ROM_START + ROM_REGION_CAP, "RAM区必须紧接ROM区"
assert ROM_HIGH_BITS >= 2, "ROM高位地址线<2根"
assert RAM_HIGH_BITS >= 2, "RAM高位地址线<2根"
print("[PASS] 全局一致性: 总容量<=地址空间, ROM/RAM地址连续")

# --- Q1 通过条件 ---
assert rom_bit_ext * ROM_CHIP_BITS == DATA_BITS, "ROM位扩展×4位≠8位"
assert rom_bit_ext > 1, "ROM必须涉及位扩展"
assert rom_word_ext > 1, "ROM必须涉及字扩展"
assert rom_total == rom_bit_ext * rom_word_ext, "ROM芯片数≠位扩展×字扩展"
assert rom_bit_ext == DATA_BITS // ROM_CHIP_BITS, "ROM位扩展≠数据总线宽度/芯片位宽"
assert rom_word_ext == ROM_REGION_CAP // (ROM_CHIP_WORDS * DATA_BITS // 8), "ROM字扩展计算不符"

assert ram_bit_ext * RAM_CHIP_BITS == DATA_BITS, "RAM位扩展×4位≠8位"
assert ram_bit_ext > 1, "RAM必须涉及位扩展"
assert ram_word_ext > 1, "RAM必须涉及字扩展"
assert ram_total == ram_bit_ext * ram_word_ext, "RAM芯片数≠位扩展×字扩展"
assert ram_bit_ext == DATA_BITS // RAM_CHIP_BITS, "RAM位扩展≠数据总线宽度/芯片位宽"
assert ram_word_ext == RAM_REGION_CAP // (RAM_CHIP_WORDS * DATA_BITS // 8), "RAM字扩展计算不符"
print(f"[PASS] Q1: ROM芯片={rom_total}(位扩{rom_bit_ext}×字扩{rom_word_ext}), RAM芯片={ram_total}(位扩{ram_bit_ext}×字扩{ram_word_ext})")

# --- Q2 通过条件 ---
# 每个ROM组容量=4K且起始整除4K
for i, (s, e) in enumerate(rom_groups):
    assert (e - s + 1) == ROM_CHIP_WORDS, f"ROM组{i}容量≠4K"
    assert s % ROM_CHIP_WORDS == 0, f"ROM组{i}起始地址不整除4K边界"
# 每个RAM组容量=8K且起始整除8K
for i, (s, e) in enumerate(ram_groups):
    assert (e - s + 1) == RAM_CHIP_WORDS, f"RAM组{i}容量≠8K"
    assert s % RAM_CHIP_WORDS == 0, f"RAM组{i}起始地址不整除8K边界"

# ROM组内部连续不重叠
for i in range(len(rom_groups) - 1):
    assert rom_groups[i][1] + 1 == rom_groups[i+1][0], f"ROM组{i}与组{i+1}地址不连续"
# RAM组内部连续不重叠
for i in range(len(ram_groups) - 1):
    assert ram_groups[i][1] + 1 == ram_groups[i+1][0], f"RAM组{i}与组{i+1}地址不连续"
# ROM区与RAM区衔接：最后一个ROM组结束+1 = 第一个RAM组起始
assert rom_groups[-1][1] + 1 == ram_groups[0][0], "ROM区与RAM区地址不连续"

assert ROM_CHIP_ADDR_BITS == 12, "ROM片内地址线位数≠12"
assert RAM_CHIP_ADDR_BITS == 13, "RAM片内地址线位数≠13"
assert ROM_CHIP_ADDR_BITS != RAM_CHIP_ADDR_BITS, "ROM与RAM片内地址线位数应不同"
print("[PASS] Q2: ROM组4K/RAM组8K边界整除, 各组内部及区际连续不重叠, 片内地址线12/13位")

# --- Q3 通过条件 ---
# ROM组使用全部4根高位地址线A15~A12
assert ROM_HIGH_BITS == 4, "ROM高位地址线≠4根"
assert RAM_HIGH_BITS == 3, "RAM高位地址线≠3根"

# 每个ROM组高位取值唯一且不同
rom_vals = [v for (_, v, _) in rom_cs_exprs]
assert len(set(rom_vals)) == len(rom_vals), "ROM组高位取值有重复"

# 每个RAM组高位取值唯一且不同
ram_vals = [v for (_, v, _) in ram_cs_exprs]
assert len(set(ram_vals)) == len(ram_vals), "RAM组高位取值有重复"

# 验证ROM组表达式使用了全部高位地址线（每个表达式含A出现次数=高位线数）
for (_, _, expr) in rom_cs_exprs:
    assert expr.count("A") == ROM_HIGH_BITS, f"ROM表达式未使用全部4根高位线: {expr}"

# 验证RAM组表达式使用了全部高位地址线
for (_, _, expr) in ram_cs_exprs:
    assert expr.count("A") == RAM_HIGH_BITS, f"RAM表达式未使用全部3根高位线: {expr}"

# 互斥性：ROM组与RAM组片选条件互斥（遍历全部地址验证）
assert mutual_exclusive, "ROM组与RAM组片选条件不互斥（存在地址同时选中ROM和RAM）"

# ROM组与RAM组的高位取值不交叉导致地址重叠
# ROM组高位(A15~A12)取值 vs RAM组高位(A15~A13)取值——验证地址范围不重叠
rom_addr_set = set()
for (s, e) in rom_groups:
    rom_addr_set.update(range(s, e+1))
ram_addr_set = set()
for (s, e) in ram_groups:
    ram_addr_set.update(range(s, e+1))
assert len(rom_addr_set & ram_addr_set) == 0, "ROM区与RAM区地址范围有重叠"

# 不存在线选法（每个表达式使用≥2根地址线）
for (_, _, expr) in rom_cs_exprs + ram_cs_exprs:
    assert expr.count("A") >= 2, f"存在线选法特征(仅1根地址线): {expr}"

print("[PASS] Q3: ROM组用A15~A12(4根), RAM组用A15~A13(3根), 取值唯一, 互斥, 无线选法")

print("\n=== 全部 ASSERT 通过 ===")

# ============================================================
# ANSWER 汇总
# ============================================================
print("\n=== ANSWER ===")
print(f"Q1: ROM芯片={rom_total}片(位扩展{rom_bit_ext}倍×字扩展{rom_word_ext}倍), RAM芯片={ram_total}片(位扩展{ram_bit_ext}倍×字扩展{ram_word_ext}倍)")
print(f"Q2: ROM组{len(rom_groups)}组(每组{ROM_CHIP_WORDS}字节), RAM组{len(ram_groups)}组(每组{RAM_CHIP_WORDS}字节)")
for i, (s, e) in enumerate(rom_groups):
    print(f"    ROM组{i}: {s:04X}H ~ {e:04X}H")
for i, (s, e) in enumerate(ram_groups):
    print(f"    RAM组{i}: {s:04X}H ~ {e:04X}H")
print(f"Q3: 全译码, ROM组片选用A15~A12(4根), RAM组片选用A15~A13(3根)")
for i, (_, val, expr) in enumerate(rom_cs_exprs):
    print(f"    CS_ROM{i} = {expr}")
for i, (_, val, expr) in enumerate(ram_cs_exprs):
    print(f"    CS_RAM{i} = {expr}")
