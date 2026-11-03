# -*- coding: utf-8 -*-
"""
DRAM 芯片存储器扩展设计 —— gen.py
题干→代码翻译：把场景规则逐条忠实实现，底部 print 完整数据流。
"""

import math


def solve(cpu_address_width, data_bus_width, chip_word_count, chip_data_width,
          refresh_interval_ms):
    """
    一次性建模，从参数算到最终答案（芯片数/地址划分/片选/刷新周期）。
    所有场景规则在计算过程中自然实现，底部 print 数据流供审核验证。
    """
    # ---- 场景规则1: 位扩展约束 ----
    # bit_expansion_count == data_bus_width / chip_data_width（须为整数且>=2）
    assert data_bus_width % chip_data_width == 0, "位扩展须整除"
    bit_expansion_count = data_bus_width // chip_data_width
    assert bit_expansion_count >= 2

    # ---- 场景规则2: 片内地址约束 ----
    # chip_internal_addr_bits == log2(chip_word_count)
    chip_internal_addr_bits = int(round(math.log2(chip_word_count)))
    assert 2 ** chip_internal_addr_bits == chip_word_count

    # ---- 场景规则3: 片选地址约束 ----
    # chip_select_lines == cpu_address_width - chip_internal_addr_bits（须>=2）
    chip_select_lines = cpu_address_width - chip_internal_addr_bits
    assert chip_select_lines >= 2

    # ---- 场景规则4: 字扩展约束 ----
    # word_expansion_count == 2^chip_select_lines（须>=2）
    word_expansion_count = 2 ** chip_select_lines
    assert word_expansion_count >= 2

    # ---- 场景规则5: 总芯片数约束 ----
    # total_chips == bit_expansion_count * word_expansion_count
    total_chips = bit_expansion_count * word_expansion_count

    # ---- 场景规则6: 地址复用约束 ----
    # row_addr_bits == chip_internal_addr_bits / 2, col_addr_bits 同理（须整数）
    assert chip_internal_addr_bits % 2 == 0
    row_addr_bits = chip_internal_addr_bits // 2
    col_addr_bits = chip_internal_addr_bits // 2

    # ---- 场景规则7: 行数约束 ----
    # chip_rows == 2^row_addr_bits
    chip_rows = 2 ** row_addr_bits

    # ---- 场景规则8: 异步刷新周期约束 ----
    # async_refresh_period == refresh_interval / chip_rows
    async_refresh_period_us = refresh_interval_ms * 1000 / chip_rows  # 转 μs

    # ---- 地址线划分（逻辑导出，非额外规则） ----
    # 片内地址: A0..A(chip_internal_addr_bits-1)
    #   行地址: A0..A(row_addr_bits-1)
    #   列地址: A(row_addr_bits)..A(chip_internal_addr_bits-1)
    # 片选地址: A(chip_internal_addr_bits)..A(cpu_address_width-1)
    intra_addr_lines = list(range(chip_internal_addr_bits))
    row_lines = list(range(row_addr_bits))
    col_lines = list(range(row_addr_bits, chip_internal_addr_bits))
    select_lines_list = list(range(chip_internal_addr_bits, cpu_address_width))

    # ---- 场景规则9: 地址范围覆盖约束 ----
    # 各芯片组地址连续覆盖 [0, 2^cpu_address_width - 1]，无重叠无遗漏
    group_size = 2 ** chip_internal_addr_bits  # 每个芯片组的地址范围大小
    total_space = 2 ** cpu_address_width
    address_ranges = []
    for i in range(word_expansion_count):
        start = i * group_size
        end = start + group_size - 1
        address_ranges.append({
            "group": i,
            "start": start,
            "end": end,
            "start_hex": hex(start),
            "end_hex": hex(end),
            "select_bits_value": i,
        })

    # ---- 验证地址范围覆盖（场景规则9） ----
    covered_start = address_ranges[0]["start"]
    covered_end = address_ranges[-1]["end"]
    no_gap = all(address_ranges[i]["end"] + 1 == address_ranges[i + 1]["start"]
                 for i in range(len(address_ranges) - 1))
    full_cover = (covered_start == 0 and covered_end == total_space - 1 and no_gap)

    return {
        # Q1
        "bit_expansion_count": bit_expansion_count,
        "word_expansion_count": word_expansion_count,
        "total_chips": total_chips,
        # Q2
        "chip_internal_addr_bits": chip_internal_addr_bits,
        "row_addr_bits": row_addr_bits,
        "col_addr_bits": col_addr_bits,
        "chip_select_lines": chip_select_lines,
        "intra_addr_lines": intra_addr_lines,
        "row_lines": row_lines,
        "col_lines": col_lines,
        "select_lines_list": select_lines_list,
        "address_ranges": address_ranges,
        # Q3
        "decoder_type": f"{chip_select_lines}:{word_expansion_count} 译码器",
        "decoder_outputs": word_expansion_count,
        # Q4
        "chip_rows": chip_rows,
        "async_refresh_period_us": async_refresh_period_us,
        # 场景规则检查量
        "full_cover": full_cover,
        "total_space": total_space,
    }


# ==================== 注入题干参数 ====================
result = solve(
    cpu_address_width=20,
    data_bus_width=16,
    chip_word_count=64 * 1024,   # 64K = 2^16
    chip_data_width=4,
    refresh_interval_ms=2,
)

# ==================== 底部：打印完整数据流 ====================
print("=" * 60)
print("PARAMS:")
print("  cpu_address_width  = 20 (位)")
print("  data_bus_width     = 16 (位)")
print("  chip_word_count    = 64K = 2^16 = 65536")
print("  chip_data_width    = 4 (位)")
print("  refresh_interval   = 2 ms")
print()

print("=" * 60)
print("Q1 芯片数计算:")
print(f"  位扩展数 bit_expansion = data_bus_width / chip_data_width = 16 / 4 = {result['bit_expansion_count']}")
print(f"  片内地址位数 = log2(64K) = log2(2^16) = {result['chip_internal_addr_bits']}")
print(f"  片选地址线数 = cpu_addr_width - 片内地址 = 20 - {result['chip_internal_addr_bits']} = {result['chip_select_lines']}")
print(f"  字扩展数 word_expansion = 2^{result['chip_select_lines']} = {result['word_expansion_count']}")
print(f"  总芯片数 total_chips = {result['bit_expansion_count']} × {result['word_expansion_count']} = {result['total_chips']}")
print()

print("=" * 60)
print("Q2 地址线划分:")
print(f"  片内地址位数 = {result['chip_internal_addr_bits']} 位 → A0~A{result['chip_internal_addr_bits']-1}")
print(f"    行地址（低半）= {result['row_addr_bits']} 位 → A{result['row_lines'][0]}~A{result['row_lines'][-1]}")
print(f"    列地址（高半）= {result['col_addr_bits']} 位 → A{result['col_lines'][0]}~A{result['col_lines'][-1]}")
print(f"  片选地址位数 = {result['chip_select_lines']} 位 → A{result['select_lines_list'][0]}~A{result['select_lines_list'][-1]}")
print()
print("  各芯片组地址范围（十六进制）:")
for ar in result['address_ranges']:
    print(f"    第{ar['group']}组: {ar['start_hex'].upper().replace('0X','0x')} ~ {ar['end_hex'].upper().replace('0X','0x')}  (片选值={ar['select_bits_value']:b})")
print()

print("=" * 60)
print("Q3 片选逻辑:")
print(f"  片选地址线 {result['chip_select_lines']} 根 → {result['decoder_type']}")
print(f"  译码器 {result['decoder_outputs']} 个输出端，分别连接 {result['decoder_outputs']} 个芯片组的 CS")
print()

print("=" * 60)
print("Q4 异步刷新周期:")
print(f"  行地址位数 = {result['row_addr_bits']} 位")
print(f"  芯片行数 chip_rows = 2^{result['row_addr_bits']} = {result['chip_rows']}")
print(f"  异步刷新周期 = 刷新间隔 / 行数 = 2 ms / {result['chip_rows']} = {result['async_refresh_period_us']:.2f} μs")
print()

print("=" * 60)
print("RULE_CHECK (场景规则验证量):")
print(f"  规则1 位扩展: 16/4 = {result['bit_expansion_count']} (整数且>=2 ✓)")
print(f"  规则2 片内地址: log2(65536) = {result['chip_internal_addr_bits']} ✓")
print(f"  规则3 片选线: 20-{result['chip_internal_addr_bits']} = {result['chip_select_lines']} (>=2 ✓)")
print(f"  规则4 字扩展: 2^{result['chip_select_lines']} = {result['word_expansion_count']} (>=2 ✓)")
print(f"  规则5 总芯片: {result['bit_expansion_count']}×{result['word_expansion_count']} = {result['total_chips']} ✓")
print(f"  规则6 地址复用: 行={result['row_addr_bits']} 列={result['col_addr_bits']} (= {result['chip_internal_addr_bits']}/2, 整数 ✓)")
print(f"  规则7 行数: 2^{result['row_addr_bits']} = {result['chip_rows']} ✓")
print(f"  规则8 刷新周期: 2000μs/{result['chip_rows']} = {result['async_refresh_period_us']:.2f}μs ✓")
print(f"  规则9 地址覆盖: [0, {result['total_space']-1}] full_cover={result['full_cover']} ✓")
