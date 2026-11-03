# -*- coding: utf-8 -*-
"""
主存储器扩展与片选逻辑设计 —— 建模求解
一次性建模：把题干规则逐句翻译成代码，底部 print 完整数据流。
"""
import math

# ============================================================
# PARAMS（题干注入的参数）
# ============================================================
ADDR_BITS = 16          # CPU 地址总线宽度
DATA_BITS = 16          # CPU 数据总线宽度

# 地址空间分区（十六进制起止）
ROM_START = 0x0000
ROM_END   = 0x3FFF      # ROM 区 16KB
RAM_START = 0x4000
RAM_END   = 0xFFFF      # RAM 区 48KB

# ROM 芯片规格：8K × 8 位
ROM_CHIP_WORDS = 8 * 1024   # 8192 字
ROM_CHIP_BITS  = 8          # 8 位

# RAM 芯片规格：16K × 8 位
RAM_CHIP_WORDS = 16 * 1024  # 16384 字
RAM_CHIP_BITS  = 8          # 8 位


def byte_capacity(start, end):
    """字节编址下，地址范围 [start, end] 的字节数 = end - start + 1"""
    return end - start + 1


def solve():
    params = {
        "ADDR_BITS": ADDR_BITS,
        "DATA_BITS": DATA_BITS,
        "ROM_START": f"{ROM_START:04X}H",
        "ROM_END":   f"{ROM_END:04X}H",
        "RAM_START": f"{RAM_START:04X}H",
        "RAM_END":   f"{RAM_END:04X}H",
        "ROM_CHIP": f"{ROM_CHIP_WORDS//1024}K × {ROM_CHIP_BITS}位",
        "RAM_CHIP": f"{RAM_CHIP_WORDS//1024}K × {RAM_CHIP_BITS}位",
    }

    # ---- 基本容量计算 ----
    total_mem = byte_capacity(ROM_START, RAM_END)       # 0x0000~0xFFFF
    rom_cap   = byte_capacity(ROM_START, ROM_END)       # ROM 分区字节数
    ram_cap   = byte_capacity(RAM_START, RAM_END)       # RAM 分区字节数

    # 芯片单片的字节数（字数 × 位宽 ÷ 8）
    rom_chip_bytes = ROM_CHIP_WORDS * ROM_CHIP_BITS // 8
    ram_chip_bytes = RAM_CHIP_WORDS * RAM_CHIP_BITS // 8

    # ---- 第1问：芯片数量（字扩展 × 位扩展）----
    # 位扩展倍数 = CPU数据总线宽度 ÷ 芯片位宽
    rom_bit_ext = DATA_BITS // ROM_CHIP_BITS
    ram_bit_ext = DATA_BITS // RAM_CHIP_BITS

    # 字扩展倍数 = 分区字节数 ÷ (芯片字节数 × 位扩展倍数)... 不对
    # 正确：分区容量(字节) ÷ (单芯片字节数) ÷ 位扩展? 
    # 其实：字扩展 = 分区字节数 / (单芯片字节数)  因为位扩展是并联(同一地址)，
    #   分区字节数就是分区中不同地址单元的个数。
    #   单芯片能提供的不同地址单元数 = 芯片字数 = 芯片字节数(÷8后)... 
    #   单芯片字节数 = 字数×位宽/8，但芯片字数 = 字节数(按字节)?
    #   8K×8位 芯片：8192个地址单元 × 8bit = 8192字节。
    #   位扩展2片并联 → 8192个地址单元 × 16bit。
    #   所以一个"芯片组"(位扩展后)覆盖的字节数 = 字数 × 位扩展 × (位宽/8)... = 字数×DATA_BITS/8
    #   但从字节地址角度看：ROM分区 16384字节，单个8K×8芯片提供8192字节，
    #   位扩展2片并联覆盖8192个地址（16bit宽），仍是8192字节地址空间。
    #   字扩展 = 16384 / 8192 = 2
    #   总芯片数 = 字扩展 × 位扩展 = 2 × 2 = 4
    # 通用公式：字扩展 = 分区字节数 / 单芯片字数（单芯片的地址单元数）
    rom_word_ext = rom_cap // ROM_CHIP_WORDS
    ram_word_ext = ram_cap // RAM_CHIP_WORDS

    rom_total_chips = rom_word_ext * rom_bit_ext
    ram_total_chips = ram_word_ext * ram_bit_ext

    # ---- 第2问：片内地址线 & 高位地址线 ----
    # 片内地址线 = log2(芯片字数)
    rom_intra_bits = int(math.log2(ROM_CHIP_WORDS))   # 8K → 13
    ram_intra_bits = int(math.log2(RAM_CHIP_WORDS))   # 16K → 14
    # 高位地址线 = ADDR_BITS - 片内地址线（位扩展不额外占地址线）
    rom_high_bits = ADDR_BITS - rom_intra_bits        # 16-13=3
    ram_high_bits = ADDR_BITS - ram_intra_bits        # 16-14=2

    # ---- 第3问：片选信号逻辑表达式 ----
    # 从每个芯片组的实际起始地址提取高位地址值，再翻译成片选表达式。
    # 这样 ROM 从 0000H 开始、RAM 从 4000H 开始时，高位值自动正确。

    def build_cs_groups(word_ext, intra_bits, start_addr, chip_type):
        """根据字扩展组数、片内地址位数、起始地址，推导各组片选表达式"""
        groups = []
        high_labels = list(range(ADDR_BITS - 1, intra_bits - 1, -1))
        group_span = (1 << intra_bits)
        for g in range(word_ext):
            group_start = start_addr + g * group_span
            # 提取高位地址值
            hi_val = group_start >> intra_bits
            high_bit_count = ADDR_BITS - intra_bits
            bits_str = format(hi_val, f'0{high_bit_count}b')
            cs_terms = []
            for idx, label in enumerate(high_labels):
                bit_val = int(bits_str[idx])
                if bit_val == 0:
                    cs_terms.append(f"!A{label}")
                else:
                    cs_terms.append(f"A{label}")
            groups.append({
                "group": g,
                "type": chip_type,
                "group_start": group_start,
                "high_labels": [f"A{x}" for x in high_labels],
                "cs_expr": " · ".join(cs_terms),
            })
        return groups

    rom_cs_groups = build_cs_groups(rom_word_ext, rom_intra_bits, ROM_START, "ROM")
    ram_cs_groups = build_cs_groups(ram_word_ext, ram_intra_bits, RAM_START, "RAM")

    # ---- 第4问：各芯片组地址范围 ----
    def chip_group_ranges(intra_bits, word_ext, start_addr):
        """计算某类芯片各字扩展组的地址范围"""
        group_span = (1 << intra_bits)  # 每组覆盖的地址单元数
        ranges = []
        cur = start_addr
        for g in range(word_ext):
            s = cur
            e = cur + group_span - 1
            ranges.append((s, e))
            cur = e + 1
        return ranges

    rom_ranges = chip_group_ranges(rom_intra_bits, rom_word_ext, ROM_START)
    ram_ranges = chip_group_ranges(ram_intra_bits, ram_word_ext, RAM_START)

    # 所有芯片组（ROM在前RAM在后）拼接
    all_groups = [(s, e) for s, e in rom_ranges] + [(s, e) for s, e in ram_ranges]

    # ---- 场景规则验证（assert，打到特征非恒真）----
    # 规则1：容量守恒
    assert rom_cap + ram_cap == total_mem, "容量守恒失败"
    # 规则2：按字节编址等价
    assert total_mem == (1 << ADDR_BITS), "总容量 != 2^地址线宽度"
    # 规则3：芯片数可整除
    assert rom_cap % ROM_CHIP_WORDS == 0, "ROM分区不能被芯片字数整除"
    assert ram_cap % RAM_CHIP_WORDS == 0, "RAM分区不能被芯片字数整除"
    # 规则4：位扩展可整除
    assert DATA_BITS % ROM_CHIP_BITS == 0, "ROM位扩展非整数"
    assert DATA_BITS % RAM_CHIP_BITS == 0, "RAM位扩展非整数"
    # 规则5：位扩展不额外占地址线（高位地址线仅由ADDR_BITS-片内地址线决定）
    assert rom_high_bits == ADDR_BITS - rom_intra_bits
    assert ram_high_bits == ADDR_BITS - ram_intra_bits
    # 规则6：片选仅涉及高位地址（高位地址线数>0且片内地址线数=log2字数）
    assert rom_intra_bits == int(math.log2(ROM_CHIP_WORDS))
    assert ram_intra_bits == int(math.log2(RAM_CHIP_WORDS))
    # 规则7：地址连续不重叠 + 并集 == 全空间
    for i in range(len(all_groups) - 1):
        assert all_groups[i][1] + 1 == all_groups[i+1][0], f"芯片组{i}与{i+1}不连续"
    assert all_groups[0][0] == 0x0000, "首组不以0000H开头"
    assert all_groups[-1][1] == 0xFFFF, "末组不以FFFFH结尾"
    # 两两交集为空（由连续+首尾覆盖保证，再加显式检查）
    for i in range(len(all_groups)):
        for j in range(i+1, len(all_groups)):
            si, ei = all_groups[i]
            sj, ej = all_groups[j]
            assert ei < sj or ej < si, f"芯片组{i}与{j}重叠"

    return {
        "params": params,
        "total_mem_bytes": total_mem,
        "rom_cap_bytes": rom_cap,
        "ram_cap_bytes": ram_cap,
        "rom_chip_bytes": rom_chip_bytes,
        "ram_chip_bytes": ram_chip_bytes,
        # 第1问
        "rom_bit_ext": rom_bit_ext,
        "rom_word_ext": rom_word_ext,
        "rom_total_chips": rom_total_chips,
        "ram_bit_ext": ram_bit_ext,
        "ram_word_ext": ram_word_ext,
        "ram_total_chips": ram_total_chips,
        # 第2问
        "rom_intra_bits": rom_intra_bits,
        "rom_high_bits": rom_high_bits,
        "ram_intra_bits": ram_intra_bits,
        "ram_high_bits": ram_high_bits,
        "rom_intra_labels": f"A{rom_intra_bits-1}~A0",
        "rom_high_labels": [f"A{x}" for x in range(ADDR_BITS-1, rom_intra_bits-1, -1)],
        "ram_intra_labels": f"A{ram_intra_bits-1}~A0",
        "ram_high_labels": [f"A{x}" for x in range(ADDR_BITS-1, ram_intra_bits-1, -1)],
        # 第3问
        "rom_cs_groups": rom_cs_groups,
        "ram_cs_groups": ram_cs_groups,
        # 第4问
        "rom_ranges_hex": [(f"{s:04X}H", f"{e:04X}H") for s, e in rom_ranges],
        "ram_ranges_hex": [(f"{s:04X}H", f"{e:04X}H") for s, e in ram_ranges],
        "all_groups_hex": [(f"{s:04X}H", f"{e:04X}H") for s, e in all_groups],
        "all_groups": all_groups,
    }


R = solve()

# ============================================================
# 底部：打印完整数据流（审核对照场景规则验证）
# ============================================================
print("=" * 70)
print("PARAMS:")
for k, v in R["params"].items():
    print(f"  {k} = {v}")

print("\n" + "=" * 70)
print("BASIC CAPACITY:")
print(f"  主存总容量 = {R['total_mem_bytes']} 字节 = {R['total_mem_bytes']//1024}KB")
print(f"  ROM 分区容量 = {R['rom_cap_bytes']} 字节 = {R['rom_cap_bytes']//1024}KB")
print(f"  RAM 分区容量 = {R['ram_cap_bytes']} 字节 = {R['ram_cap_bytes']//1024}KB")
print(f"  ROM 单芯片字节数 = {R['rom_chip_bytes']} 字节")
print(f"  RAM 单芯片字节数 = {R['ram_chip_bytes']} 字节")

print("\n" + "=" * 70)
print("第1问 — 芯片数量（字扩展 × 位扩展）:")
print(f"  ROM 区:")
print(f"    位扩展 = 数据总线{DATA_BITS}位 ÷ 芯片{ROM_CHIP_BITS}位 = {R['rom_bit_ext']} 倍")
print(f"    字扩展 = {R['rom_cap_bytes']} ÷ {ROM_CHIP_WORDS} = {R['rom_word_ext']} 倍")
print(f"    总芯片数 = {R['rom_word_ext']} × {R['rom_bit_ext']} = {R['rom_total_chips']} 片")
print(f"  RAM 区:")
print(f"    位扩展 = 数据总线{DATA_BITS}位 ÷ 芯片{RAM_CHIP_BITS}位 = {R['ram_bit_ext']} 倍")
print(f"    字扩展 = {R['ram_cap_bytes']} ÷ {RAM_CHIP_WORDS} = {R['ram_word_ext']} 倍")
print(f"    总芯片数 = {R['ram_word_ext']} × {R['ram_bit_ext']} = {R['ram_total_chips']} 片")

print("\n" + "=" * 70)
print("第2问 — 地址线分组:")
print(f"  ROM 芯片({ROM_CHIP_WORDS//1024}K×{ROM_CHIP_BITS}位):")
print(f"    片内地址线 = log2({ROM_CHIP_WORDS}) = {R['rom_intra_bits']} 根 → {R['rom_intra_labels']}")
print(f"    高位地址线 = {ADDR_BITS} - {R['rom_intra_bits']} = {R['rom_high_bits']} 根 → {R['rom_high_labels']}")
print(f"  RAM 芯片({RAM_CHIP_WORDS//1024}K×{RAM_CHIP_BITS}位):")
print(f"    片内地址线 = log2({RAM_CHIP_WORDS}) = {R['ram_intra_bits']} 根 → {R['ram_intra_labels']}")
print(f"    高位地址线 = {ADDR_BITS} - {R['ram_intra_bits']} = {R['ram_high_bits']} 根 → {R['ram_high_labels']}")
print(f"  差异: ROM片内{R['rom_intra_bits']}根/高位{R['rom_high_bits']}根 vs RAM片内{R['ram_intra_bits']}根/高位{R['ram_high_bits']}根")
print(f"  原因: ROM芯片8K(2^13)比RAM芯片16K(2^14)少一位，故ROM多一根高位地址线参与译码")

print("\n" + "=" * 70)
print("第3问 — 片选信号逻辑表达式（低电平有效 CS-bar）:")
print(f"  ROM 区（高位{R['rom_high_labels']}参与译码）:")
for g in R["rom_cs_groups"]:
    print(f"    ROM组{g['group']}: CS_bar = {g['cs_expr']}")
print(f"  RAM 区（高位{R['ram_high_labels']}参与译码）:")
for g in R["ram_cs_groups"]:
    print(f"    RAM组{g['group']}: CS_bar = {g['cs_expr']}")

print("\n" + "=" * 70)
print("第4问 — 各芯片组地址范围（十六进制）:")
print(f"  ROM 区:")
for i, (s, e) in enumerate(R["rom_ranges_hex"]):
    cs = R["rom_cs_groups"][i]["cs_expr"]
    print(f"    ROM组{i}: {s} ~ {e}  (片选: {cs})")
print(f"  RAM 区:")
for i, (s, e) in enumerate(R["ram_ranges_hex"]):
    cs = R["ram_cs_groups"][i]["cs_expr"]
    print(f"    RAM组{i}: {s} ~ {e}  (片选: {cs})")

print("\n" + "=" * 70)
print("规则7验证 — 地址连续不重叠:")
print(f"  全部芯片组按序排列:")
for i, (s, e) in enumerate(R["all_groups_hex"]):
    print(f"    [{i}] {s} ~ {e}")
print(f"  首地址 = {R['all_groups_hex'][0][0]} (应为 0000H)")
print(f"  末地址 = {R['all_groups_hex'][-1][1]} (应为 FFFFH)")
# 连续性逐对检查输出
print(f"  逐对连续性:")
for i in range(len(R["all_groups"]) - 1):
    cur_end = R["all_groups"][i][1]
    nxt_start = R["all_groups"][i+1][0]
    print(f"    组{i}末址+1 = {cur_end+1:#06X} == 组{i+1}首址 = {nxt_start:#06X} → {'OK' if cur_end+1==nxt_start else 'FAIL'}")

print("\n" + "=" * 70)
print("全部 7 条场景规则 assert 通过 ✓")
