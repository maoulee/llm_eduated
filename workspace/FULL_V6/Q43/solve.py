import math

def solve():
    # ================= 参数定义 =================
    main_mem_size = 64 * 1024 * 1024  # 主存容量 64 MB
    cache_size = 64 * 1024            # Cache容量 64 KB
    block_size = 128                  # 数据块大小 128 B
    
    print("=== (1) 计算主存块数、Cache总行数以及块内地址（Offset）的位数 ===")
    main_mem_blocks = main_mem_size // block_size
    cache_lines = cache_size // block_size
    offset_bits = int(math.log2(block_size))
    
    print(f"主存容量: {main_mem_size} B = 2^{int(math.log2(main_mem_size))} B")
    print(f"Cache容量: {cache_size} B = 2^{int(math.log2(cache_size))} B")
    print(f"数据块大小: {block_size} B = 2^{offset_bits} B")
    print(f"主存块数 = 主存容量 / 块大小 = {main_mem_size} / {block_size} = {main_mem_blocks} 块 (2^{int(math.log2(main_mem_blocks))})")
    print(f"Cache总行数 = Cache容量 / 块大小 = {cache_size} / {block_size} = {cache_lines} 行 (2^{int(math.log2(cache_lines))})")
    print(f"块内偏移(Offset)位数 = log2(块大小) = {offset_bits} 位\n")
    
    addr_bits = int(math.log2(main_mem_size))
    print(f"主存地址总位数 = log2(主存容量) = {addr_bits} 位\n")
    
    # ================= (2) 直接映射分析 =================
    print("=== (2) 直接映射（Direct Mapping）地址结构分析 ===")
    dm_index_bits = int(math.log2(cache_lines))
    dm_tag_bits = addr_bits - dm_index_bits - offset_bits
    print(f"索引(Index)位数 = log2(Cache行数) = log2({cache_lines}) = {dm_index_bits} 位")
    print(f"标记(Tag)位数 = 地址总位数 - 索引位数 - 偏移位数 = {addr_bits} - {dm_index_bits} - {offset_bits} = {dm_tag_bits} 位")
    print(f"主存地址结构图: [ 标记 Tag: {dm_tag_bits}位 ] | [ 索引 Index: {dm_index_bits}位 ] | [ 块内偏移 Offset: {offset_bits}位 ]\n")
    
    # ================= (3) 2路组相联映射分析 =================
    print("=== (3) 2路组相联映射（2-way Set Associative）地址结构分析 ===")
    ways = 2
    num_sets = cache_lines // ways
    sa_index_bits = int(math.log2(num_sets))
    sa_tag_bits = addr_bits - sa_index_bits - offset_bits
    print(f"组数 = Cache总行数 / 路数 = {cache_lines} / {ways} = {num_sets} 组")
    print(f"索引(Index)位数 = log2(组数) = log2({num_sets}) = {sa_index_bits} 位")
    print(f"标记(Tag)位数 = 地址总位数 - 索引位数 - 偏移位数 = {addr_bits} - {sa_index_bits} - {offset_bits} = {sa_tag_bits} 位")
    print(f"主存地址结构图: [ 标记 Tag: {sa_tag_bits}位 ] | [ 索引 Index: {sa_index_bits}位 ] | [ 块内偏移 Offset: {offset_bits}位 ]")
    print(f"对比: 与直接映射相比，2路组相联的索引位减少{dm_index_bits - sa_index_bits}位，标记位增加{sa_tag_bits - dm_tag_bits}位。")
    print(f"组相联将直接映射的1个Cache行扩展为包含{ways}行的组，主存块可映射到组内任意一行，有效降低了冲突缺失率。\n")
    
    # ================= (4) Cache命中率模拟 =================
    print("=== (4) Cache命中率模拟计算 ===")
    access_seq_hex = [
        "0x0000000", "0x0000010", "0x0100000", "0x0000000", "0x0100000",
        "0x0000000", "0x0200000", "0x0200010", "0x0000080", "0x0000090",
        "0x0000100", "0x0000110", "0x0000200", "0x0000210", "0x0000000"
    ]
    access_seq = [int(addr, 16) for addr in access_seq_hex]
    
    # --- 直接映射模拟 ---
    print("--- 直接映射模拟 (直接覆盖) ---")
    dm_cache = [-1] * cache_lines  # 存储每个Cache行的Tag，-1表示空
    dm_hits = 0
    dm_total = len(access_seq)
    
    for i, addr in enumerate(access_seq):
        offset = addr & ((1 << offset_bits) - 1)
        index = (addr >> offset_bits) & ((1 << dm_index_bits) - 1)
        tag = addr >> (offset_bits + dm_index_bits)
        
        hit = dm_cache[index] == tag
        if hit:
            dm_hits += 1
            status = "命中"
        else:
            dm_cache[index] = tag
            status = "缺失"
            
        print(f"访问{i+1:2d}: 地址={addr:07X} | Tag={tag:3d} | Index={index:3d} | Offset={offset:3d} | 状态: {status}")
        
    dm_hit_rate = dm_hits / dm_total
    print(f"直接映射命中率: {dm_hits}/{dm_total} = {dm_hit_rate:.1%}\n")
    
    # --- 2路组相联映射模拟 (LRU) ---
    print("--- 2路组相联映射模拟 (LRU替换) ---")
    sa_cache = [] # 每个元素是一个列表，表示组内的Tags，列表顺序体现LRU状态（末尾为最近使用）
    for _ in range(num_sets):
        sa_cache.append([])
        
    sa_hits = 0
    sa_total = len(access_seq)
    
    for i, addr in enumerate(access_seq):
        offset = addr & ((1 << offset_bits) - 1)
        index = (addr >> offset_bits) & ((1 << sa_index_bits) - 1)
        tag = addr >> (offset_bits + sa_index_bits)
        
        set_cache = sa_cache[index]
        hit = tag in set_cache
        
        if hit:
            sa_hits += 1
            status = "命中"
            # 更新LRU: 命中块移到列表末尾（最近使用）
            set_cache.remove(tag)
            set_cache.append(tag)
        else:
            status = "缺失"
            if len(set_cache) < ways:
                # 组内有空位，直接放入
                set_cache.append(tag)
            else:
                # 组已满，替换最久未使用的（列表头部）
                set_cache.pop(0)
                set_cache.append(tag)
                
        print(f"访问{i+1:2d}: 地址={addr:07X} | Tag={tag:3d} | Index={index:3d} | Offset={offset:3d} | 组状态: {set_cache} | 状态: {status}")
        
    sa_hit_rate = sa_hits / sa_total
    print(f"2路组相联命中率: {sa_hits}/{sa_total} = {sa_hit_rate:.1%}\n")
    
    # ================= 差异原因分析 =================
    print("=== 差异原因分析 ===")
    print(f"直接映射命中率 ({dm_hit_rate:.1%}) 低于 2路组相联 ({sa_hit_rate:.1%})。")
    print("原因: 访问序列中多次交替访问映射到同一Cache行/组（Index=0）的不同主存块（Tag分别为0、1、2）。")
    print("直接映射下，同一行只能容纳1个块，导致严重冲突替换（乒乓效应），命中率被压制。")
    print(f"而2路组相联允许同一组内容纳{ways}个不同标记的块，在LRU策略下可保留频繁访问的块，显著缓解了冲突，从而提高了命中率。")

if __name__ == "__main__":
    solve()