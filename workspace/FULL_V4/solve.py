#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cache映射问题求解
题目：某计算机按字节编址，主存地址长度为32位。
Cache总容量为4KB，数据块大小为64B，采用2路组相联映射方式。
Cache初始为空，替换算法采用LRU。
"""

# ============================================
# 第(1)问：计算地址结构划分
# ============================================

print("=" * 60)
print("第(1)问：计算主存地址结构划分")
print("=" * 60)

# 基本参数
address_length = 32  # 主存地址长度（位）
cache_size = 4 * 1024  # Cache总容量 4KB = 4096字节
block_size = 64  # 数据块大小 64B
ways = 2  # 2路组相联

print(f"基本参数：")
print(f"  主存地址长度: {address_length}位")
print(f"  Cache总容量: {cache_size}B ({cache_size // 1024}KB)")
print(f"  数据块大小: {block_size}B")
print(f"  组相联路数: {ways}路")
print()

# 计算Offset位数：块大小 = 2^offset_bits
import math
offset_bits = int(math.log2(block_size))
print(f"块内地址(Offset)位数计算：")
print(f"  块大小 = {block_size}B = 2^{offset_bits}B")
print(f"  因此 Offset位数 = {offset_bits}位")
print(f"  对应地址位范围: [{offset_bits - 1}:0] = [{offset_bits - 1}:0]")
print()

# 计算Cache总块数
total_blocks = cache_size // block_size
print(f"Cache总块数计算：")
print(f"  总块数 = Cache总容量 / 块大小 = {cache_size}B / {block_size}B = {total_blocks}块")
print()

# 计算组数
num_sets = total_blocks // ways
print(f"组数计算：")
print(f"  组数 = 总块数 / 路数 = {total_blocks} / {ways} = {num_sets}组")
print(f"  {num_sets}组 = 2^{int(math.log2(num_sets))}")
print()

# 计算Set Index位数
set_bits = int(math.log2(num_sets))
print(f"组号(Set Index)位数：")
print(f"  {set_bits}位")
set_start_bit = offset_bits
set_end_bit = offset_bits + set_bits - 1
print(f"  对应地址位范围: [{set_end_bit}:{set_start_bit}]")
print()

# 计算Tag位数
tag_bits = address_length - set_bits - offset_bits
print(f"主存标记(Tag)位数：")
print(f"  Tag位数 = 总地址位数 - Set位数 - Offset位数")
print(f"  Tag位数 = {address_length} - {set_bits} - {offset_bits} = {tag_bits}位")
tag_start_bit = set_end_bit + 1
tag_end_bit = address_length - 1
print(f"  对应地址位范围: [{tag_end_bit}:{tag_start_bit}]")
print()

# 输出地址结构图
print(f"主存地址结构图：")
print(f"  {'┌' + '─' * 50 + '┐'}")
print(f"  │{'主存标记(Tag)':^14}│{'组号(Set Index)':^14}│{'块内地址(Offset)':^14}│")
print(f"  │{'{0}位 [{1}:{2}]'.format(tag_bits, tag_end_bit, tag_start_bit):^14}│{'{0}位 [{1}:{2}]'.format(set_bits, set_end_bit, set_start_bit):^14}│{'{0}位 [{1}:0]'.format(offset_bits):^14}│")
print(f"  {'└' + '─' * 50 + '┘'}")
print(f"  总位数: {tag_bits} + {set_bits} + {offset_bits} = {tag_bits + set_bits + offset_bits}位")
print()

# 定义掩码和移位常量
OFFSET_MASK = (1 << offset_bits) - 1  # 0x3F
SET_MASK = (1 << set_bits) - 1        # 0x1F
TAG_SHIFT = offset_bits + set_bits     # 11
SET_SHIFT = offset_bits                # 6

print(f"位运算常数：")
print(f"  OFFSET_MASK = 0x{OFFSET_MASK:X}")
print(f"  SET_MASK    = 0x{SET_MASK:X}")
print(f"  TAG_SHIFT   = {TAG_SHIFT}")
print(f"  SET_SHIFT   = {SET_SHIFT}")
print()

# ============================================
# 第(2)问：地址映射与命中判断
# ============================================

print("=" * 60)
print("第(2)问：地址映射与命中判断")
print("=" * 60)

# 访问序列（十六进制）
access_sequence = [
    0x00000000,
    0x00001000,
    0x00000100,
    0x00002000,
    0x00000000,
    0x00000100,
    0x00003000,
    0x00001000
]

# 打印表头
print(f"{'次序':^4} | {'主存地址(十六进制)':^18} | {'Tag(十六进制)':^12} | {'Set(十进制)':^10} | {'Offset(十六进制)':^14} | {'命中/未命中':^10}")
print("-" * 80)

# Cache数据结构：每个组有2个slot，每个slot包含(tag, valid, lru_time)
# lru_time越小表示越久未使用
cache = []
for s in range(num_sets):
    cache.append([])  # 每个组初始为空

lru_counter = 0  # LRU计数器

results = []

for i, addr in enumerate(access_sequence):
    # 计算Tag, Set, Offset
    offset = addr & OFFSET_MASK
    set_index = (addr >> SET_SHIFT) & SET_MASK
    tag = addr >> TAG_SHIFT
    
    # 查找该组中是否有匹配的Tag
    hit = False
    cache_set = cache[set_index]
    
    matched_slot = None
    for j, slot in enumerate(cache_set):
        if slot['valid'] and slot['tag'] == tag:
            hit = True
            matched_slot = j
            break
    
    if hit:
        # 命中：更新LRU
        cache_set[matched_slot]['lru_time'] = lru_counter
        hit_miss = "H"
        hit_miss_str = "命中(H)"
    else:
        # 未命中
        hit_miss = "M"
        hit_miss_str = "未命中(M)"
        
        if len(cache_set) < ways:
            # 该组还有空闲slot，直接插入
            cache_set.append({
                'tag': tag,
                'valid': True,
                'lru_time': lru_counter
            })
            action_desc = "插入空slot"
        else:
            # 组已满，使用LRU替换
            # 找到lru_time最小的slot进行替换
            lru_slot = min(range(len(cache_set)), key=lambda x: cache_set[x]['lru_time'])
            cache_set[lru_slot] = {
                'tag': tag,
                'valid': True,
                'lru_time': lru_counter
            }
            old_tag = results[-1] if results else None
            action_desc = f"LRU替换(Tag=0x{cache_set[lru_slot]['tag']-1:X}→0x{tag:X})" if lru_slot == 0 else f"LRU替换(Tag=0x{tag:X})"
    
    lru_counter += 1
    
    # 存储结果
    result = {
        'order': i + 1,
        'addr': addr,
        'tag': tag,
        'set': set_index,
        'offset': offset,
        'hit_miss': hit_miss
    }
    results.append(result)
    
    # 打印当前访问
    print(f"{i+1:^4} | {addr:08X}H{'':^9} | {tag:03X}H{'':^6} | {set_index:^10} | {offset:02X}H{'':^8} | {hit_miss:^10}")
    
    # 打印当前Cache组状态
    print(f"    → Set {set_index} 状态: ", end="")
    set_status = []
    for slot in cache[set_index]:
        set_status.append(f"[Tag=0x{slot['tag']:03X}, valid={slot['valid']}, lru={slot['lru_time']}]")
    print(", ".join(set_status) if set_status else "空")

print()

# 统计命中次数
hit_count = sum(1 for r in results if r['hit_miss'] == 'H')
total_count = len(results)
print(f"命中统计：")
print(f"  总访问次数: {total_count}")
print(f"  命中次数: {hit_count}")
print(f"  未命中次数: {total_count - hit_count}")
print(f"  命中率: {hit_count}/{total_count} = {hit_count/total_count:.2%}")
print()

# ============================================
# 第(3)问：直接映射分析
# ============================================

print("=" * 60)
print("第(3)问：直接映射方式分析")
print("=" * 60)

# 直接映射下，Cache行数 = 总块数
direct_mapped_lines = total_blocks
print(f"直接映射方式：")
print(f"  Cache行数 = Cache总块数 = {direct_mapped_lines}行")
print(f"  块索引(Block Index)位数 = log2({direct_mapped_lines}) = {int(math.log2(direct_mapped_lines))}位")
print(f"  对应地址位范围: [{int(math.log2(direct_mapped_lines)) + offset_bits - 1}:{offset_bits}]")
print(f"  此时Tag位数 = {address_length} - {int(math.log2(direct_mapped_lines))} - {offset_bits} = {address_length - int(math.log2(direct_mapped_lines)) - offset_bits}位")
print()

# 分析直接映射下的冲突
print(f"直接映射下的冲突失效分析：")
print(f"  在直接映射中，主存块号与Cache行号的映射关系为：")
print(f"  Cache行号 = 主存块号 mod Cache行数 = 主存块号 mod {direct_mapped_lines}")
print()

# 计算每个访问地址的主存块号和Cache行号
print(f"  {'次序':^4} | {'主存地址':^18} | {'主存块号':^10} | {'Cache行号':^10} | {'分析'}")
print("  " + "-" * 70)

direct_cache = {}  # 记录直接映射下的cache状态

for i, addr in enumerate(access_sequence):
    block_number = addr // block_size  # 主存块号
    cache_line = block_number % direct_mapped_lines  # Cache行号
    
    analysis = ""
    if cache_line in direct_cache:
        if direct_cache[cache_line] == addr // block_size:
            analysis = f"命中（Cache行{cache_line}中已有块{block_number}）"
        else:
            old_block = direct_cache[cache_line]
            analysis = f"冲突！替换块{old_block}→块{block_number}"
            direct_cache[cache_line] = block_number
    else:
        analysis = f"未命中，存入Cache行{cache_line}"
        direct_cache[cache_line] = block_number
    
    print(f"  {i+1:^4} | {addr:08X}H{'':^9} | {block_number:^10} | {cache_line:^10} | {analysis}")

print()

# 识别冲突失效的模式
conflict_blocks = {}
for i, addr in enumerate(access_sequence):
    block_number = addr // block_size
    cache_line = block_number % direct_mapped_lines
    if cache_line not in conflict_blocks:
        conflict_blocks[cache_line] = []
    conflict_blocks[cache_line].append((i+1, block_number, addr))

print(f"冲突模式分析：")
for line, blocks in conflict_blocks.items():
    if len(blocks) > 1:
        block_nums = [b[1] for b in blocks]
        unique_blocks = list(dict.fromkeys(block_nums))  # 保留顺序去重
        print(f"  Cache行 {line} 映射了 {len(unique_blocks)} 个不同主存块: {unique_blocks}")
        for order, bn, addr in blocks:
            print(f"    次序{order}: 地址{addr:08X}H → 主存块{bn} → Cache行{line}")
print()

print(f"失效类型结论：")
print(f"  直接映射方式下将频繁出现【冲突失效(Conflict Miss)】")
print()
print(f"原因分析：")
print(f"  1. 在直接映射中，主存块与Cache行是一对一映射关系")
print(f"  2. 地址 00000000H、00001000H、00002000H、00003000H 的主存块号分别为 0、64、128、192")
print(f"     这些块号对 {direct_mapped_lines} 取模后都映射到 Cache 行 0")
print(f"  3. 当程序循环访问这些地址时，后访问的块会强制覆盖先前的块")
print(f"  4. 即使Cache整体并未存满，也会不断发生置换，这就是冲突失效")
print()
print(f"  对比：2路组相联映射允许同一个组内存放2个不同主存块，")
print(f"  能有效缓解（但无法完全消除）此类因地址映射重叠引发的冲突失效。")
