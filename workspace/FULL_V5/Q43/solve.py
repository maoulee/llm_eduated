#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cache存储器系统参数求解
- 主存地址长度: 32位
- Cache容量: 2KB = 2048B
- 块大小: 64B
"""

import math

# ============ 系统参数 ============
ADDRESS_BITS = 32        # 主存地址长度
CACHE_SIZE = 2 * 1024    # Cache容量 2KB = 2048B
BLOCK_SIZE = 64          # 块大小 64B

# ============ 基础计算 ============
print("=" * 70)
print("Cache存储器系统参数求解")
print("=" * 70)
print(f"\n系统参数:")
print(f"  主存地址长度: {ADDRESS_BITS} 位")
print(f"  Cache容量: {CACHE_SIZE}B ({CACHE_SIZE // 1024}KB)")
print(f"  块大小: {BLOCK_SIZE}B")

# 块内偏移位数
offset_bits = int(math.log2(BLOCK_SIZE))
print(f"\n  块内偏移(Offset)位数: log2({BLOCK_SIZE}) = {offset_bits} 位")

# Cache总行数（块数）
cache_lines = CACHE_SIZE // BLOCK_SIZE
print(f"  Cache总行数（块数）: {CACHE_SIZE} / {BLOCK_SIZE} = {cache_lines} 行")

# ===================================================================
# 第(1)题：直接映射
# ===================================================================
print("\n" + "=" * 70)
print("第(1)题：直接映射方式")
print("=" * 70)

# 直接映射下，Index位数 = log2(Cache行数)
dm_index_bits = int(math.log2(cache_lines))
dm_tag_bits = ADDRESS_BITS - dm_index_bits - offset_bits

print(f"\n位数计算:")
print(f"  Offset（块内偏移）: {offset_bits} 位")
print(f"  Index（组索引）: log2({cache_lines}) = {dm_index_bits} 位")
print(f"  Tag（标记）: {ADDRESS_BITS} - {dm_index_bits} - {offset_bits} = {dm_tag_bits} 位")

# 地址解析
addr_hex = 0x12345678
print(f"\n地址解析: {addr_hex:#010X} ({addr_hex} )")
print(f"  二进制: {addr_hex:032b}")

# 提取各字段
# Offset: 低offset_bits位
offset_mask = (1 << offset_bits) - 1
offset_value = addr_hex & offset_mask

# Index: 接下来dm_index_bits位
index_mask = (1 << dm_index_bits) - 1
index_value = (addr_hex >> offset_bits) & index_mask

# Tag: 高位
tag_value = addr_hex >> (offset_bits + dm_index_bits)

print(f"\n  字段提取:")
print(f"    Offset（低{offset_bits}位）:  二进制 {offset_value:06b}  = {offset_value:#04X}H")
print(f"    Index（中{dm_index_bits}位）:  二进制 {index_value:05b}  = {index_value:#04X}H")
print(f"    Tag（高{dm_tag_bits}位）:    二进制 {tag_value:021b}  = {tag_value:#04X}H")

# 验证拼接
reconstructed = (tag_value << (offset_bits + dm_index_bits)) | (index_value << offset_bits) | offset_value
print(f"\n  验证: Tag|Index|Offset 拼接 = {reconstructed:#010X}  == {addr_hex:#010X}? {reconstructed == addr_hex}")

# ===================================================================
# 第(2)题：2路组相联映射
# ===================================================================
print("\n" + "=" * 70)
print("第(2)题：2路组相联映射")
print("=" * 70)

ways = 2  # 2路
num_sets = cache_lines // ways  # 组数
print(f"\n2路组相联配置:")
print(f"  路数(ways): {ways}")
print(f"  组数: {cache_lines} / {ways} = {num_sets} 组")

# 计算各字段位数
su_index_bits = int(math.log2(num_sets))
su_offset_bits = offset_bits  # Offset不变
su_tag_bits = ADDRESS_BITS - su_index_bits - su_offset_bits

print(f"\n位数计算:")
print(f"  Offset（块内偏移）: {su_offset_bits} 位（不变）")
print(f"  Index（组索引）: log2({num_sets}) = {su_index_bits} 位")
print(f"  Tag（标记）: {ADDRESS_BITS} - {su_index_bits} - {su_offset_bits} = {su_tag_bits} 位")

print(f"\n与直接映射相比的变化:")
print(f"  Offset: {offset_bits} 位 → {su_offset_bits} 位, 变化 {su_offset_bits - offset_bits:+d} 位（不变）")
print(f"  Index:  {dm_index_bits} 位 → {su_index_bits} 位, 变化 {su_index_bits - dm_index_bits:+d} 位（减少1位）")
print(f"  Tag:    {dm_tag_bits} 位 → {su_tag_bits} 位, 变化 {su_tag_bits - dm_tag_bits:+d} 位（增加1位）")

# ===================================================================
# 第(3)题：2路组相联 LRU替换算法模拟
# ===================================================================
print("\n" + "=" * 70)
print("第(3)题：2路组相联 LRU替换算法模拟")
print("=" * 70)

# 2路组相联参数
ways_3 = 2
sets_3 = num_sets  # 16组
index_bits_3 = su_index_bits  # 4位
offset_bits_3 = su_offset_bits  # 6位
tag_bits_3 = su_tag_bits  # 22位

print(f"\n配置参数:")
print(f"  路数: {ways_3} 组内行数: {ways_3}")
print(f"  组数: {sets_3}  Index位数: {index_bits_3}")
print(f"  Offset位数: {offset_bits_3}  Tag位数: {tag_bits_3}")

# 地址块号计算: block_number = address >> offset_bits
# 组号: set_index = block_number & ((1 << index_bits) - 1)
# 标记: tag = block_number >> index_bits

index_mask_3 = (1 << index_bits_3) - 1

# 访问序列
access_sequence = [0x00000080, 0x00000100, 0x00000080, 0x00000180, 0x00000080]

print(f"\n访问序列: {[f'{a:#010X}' for a in access_sequence]}")

# 先分析每个地址的块号、组号、Tag
print(f"\n地址映射分析:")
print(f"  {'地址':>12}  {'块号':>10}  {'组号':>6}  {'Tag':>6}")
print(f"  {'-'*12}  {'-'*10}  {'-'*6}  {'-'*6}")

addr_analysis = []
for addr in access_sequence:
    block_num = addr >> offset_bits_3
    set_idx = block_num & index_mask_3
    tag = block_num >> index_bits_3
    addr_analysis.append((addr, block_num, set_idx, tag))
    print(f"  {addr:#010X}  {block_num:#06X}({block_num:>5})  {set_idx:#04X}({set_idx:>4})  {tag:#04X}({tag:>4})")

# 模拟Cache访问（2路组相联，LRU替换）
print(f"\n{'='*70}")
print("LRU替换算法模拟（2路组相联，命中与缺失均更新LRU状态）")
print(f"{'='*70}")

# Cache状态：每组包含2行，每行有tag和valid标志
# 使用列表维护LRU顺序：索引0是最老的，索引ways_3-1是最近的
# cache_sets[set_idx] = [(tag, valid), (tag, valid), ...]
cache_sets = {}  # set_idx -> [(tag, valid), ...] LRU顺序：末尾是最近使用的

hits = 0
misses = 0

for step, (addr, block_num, set_idx, tag) in enumerate(addr_analysis, 1):
    print(f"\n访问 {step}: 地址 {addr:#010X} -> 块号 {block_num:#06X} -> 组号 {set_idx}, Tag {tag}")
    
    # 初始化该组（如果不存在）
    if set_idx not in cache_sets:
        cache_sets[set_idx] = [(None, False) for _ in range(ways_3)]
    
    current_set = cache_sets[set_idx]
    print(f"  当前组状态: {[(f'Tag{t}' if v else '空') for t, v in current_set]}")
    
    # 检查命中
    hit = False
    hit_pos = -1
    for i in range(len(current_set)):
        if current_set[i][1] and current_set[i][0] == tag:
            hit = True
            hit_pos = i
            break
    
    if hit:
        hits += 1
        print(f"  结果: 【命中】Tag {tag} 在第 {hit_pos} 行")
        # 更新LRU：将命中的行移到末尾（最近使用）
        moved = current_set.pop(hit_pos)
        current_set.append(moved)
        print(f"  LRU更新后: {[(f'Tag{t}' if v else '空') for t, v in current_set]} (末尾=最近)")
    else:
        misses += 1
        print(f"  结果: 【缺失】需要装入 Tag {tag}")
        
        # 检查是否有空行
        empty_pos = None
        for i in range(len(current_set)):
            if not current_set[i][1]:
                empty_pos = i
                break
        
        if empty_pos is not None:
            # 有空行，直接装入
            current_set[empty_pos] = (tag, True)
            print(f"  装入空行 (位置 {empty_pos}): Tag {tag}")
            # 移到末尾（最近使用）
            moved = current_set.pop(empty_pos)
            current_set.append(moved)
        else:
            # 组满，替换最老的（第一个元素）
            evicted_tag = current_set[0][0]
            print(f"  组满，替换最老的 Tag {evicted_tag}")
            current_set.pop(0)
            current_set.append((tag, True))
        
        print(f"  LRU更新后: {[(f'Tag{t}' if v else '空') for t, v in current_set]} (末尾=最近)")

# 命中率统计
total_accesses = len(access_sequence)
hit_rate = hits / total_accesses * 100

print(f"\n{'='*70}")
print("统计结果:")
print(f"{'='*70}")
print(f"  总访问次数: {total_accesses}")
print(f"  命中次数:   {hits}")
print(f"  缺失次数:   {misses}")
print(f"  命中率:     {hits}/{total_accesses} = {hit_rate:.1f}%")

# ===================================================================
# 总结
# ===================================================================
print(f"\n{'='*70}")
print("总结")
print(f"{'='*70}")

print(f"\n(1) 直接映射地址字段位数:")
print(f"    Tag: {dm_tag_bits} 位, Index: {dm_index_bits} 位, Offset: {offset_bits} 位")
print(f"    地址 12345678H 解析: Tag={tag_value:#X}H, Index={index_value:#X}H, Offset={offset_value:#X}H")

print(f"\n(2) 2路组相联地址字段位数:")
print(f"    Tag: {su_tag_bits} 位, Index: {su_index_bits} 位, Offset: {su_offset_bits} 位")
print(f"    与直接映射相比: Index减少1位({dm_index_bits}->{su_index_bits}), Tag增加1位({dm_tag_bits}->{su_tag_bits}), Offset不变")

print(f"\n(3) 2路组相联LRU模拟:")
print(f"    5次访问: 命中{hits}次, 缺失{misses}次, 命中率={hit_rate:.1f}%")
print(f"    所有地址均映射到第0组，产生真冲突")
