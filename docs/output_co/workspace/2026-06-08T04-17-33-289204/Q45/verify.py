# ===== 题目参数 =====
virtual_addr_bits = 32
physical_addr_bits = 24
page_size = 4 * 1024  # 4KB
tlb_assoc = 4  # 4路组相联
tlb_entries = 16
cache_data_size = 32 * 1024  # 32KB
cache_assoc = 4  # 4路组相联
block_size = 64  # 64B

vpn_0x01234 = 0x01234
ppn_0x01234 = 0x0A5B
va_0x01234567 = 0x01234567

# ===== 校验1：页内偏移位数 =====
import math
page_offset_bits = int(math.log2(page_size))
print(f"页内偏移位数: {page_offset_bits} (log2(4KB)={page_offset_bits})")
assert page_size == (1 << page_offset_bits), "页大小不是2的幂"

# ===== 校验2：VPN位数 =====
vpn_bits = virtual_addr_bits - page_offset_bits
print(f"VPN位数: {vpn_bits} (32-{page_offset_bits}={vpn_bits})")

# ===== 校验3：PPN位数 =====
ppn_bits = physical_addr_bits - page_offset_bits
print(f"PPN位数: {ppn_bits} (24-{page_offset_bits}={ppn_bits})")

# ===== 校验4：TLB参数 =====
tlb_sets = tlb_entries // tlb_assoc
print(f"TLB组数: {tlb_sets} (16/{tlb_assoc}={tlb_sets})")
assert tlb_sets == (1 << int(math.log2(tlb_sets))), "TLB组数不是2的幂"
tlb_index_bits = int(math.log2(tlb_sets))
print(f"TLB Index位数: {tlb_index_bits}")
tlb_tag_bits = vpn_bits - tlb_index_bits
print(f"TLB Tag位数: {tlb_tag_bits} ({vpn_bits}-{tlb_index_bits}={tlb_tag_bits})")

# ===== 校验5：Cache参数 =====
cache_lines = cache_data_size // block_size
print(f"Cache行数: {cache_lines} (32KB/64B={cache_lines})")
cache_sets = cache_lines // cache_assoc
print(f"Cache组数: {cache_sets} ({cache_lines}/{cache_assoc}={cache_sets})")
assert cache_sets == (1 << int(math.log2(cache_sets))), "Cache组数不是2的幂"
cache_index_bits = int(math.log2(cache_sets))
print(f"Cache Index位数: {cache_index_bits}")
block_offset_bits = int(math.log2(block_size))
print(f"块内偏移位数: {block_offset_bits}")
cache_tag_bits = physical_addr_bits - cache_index_bits - block_offset_bits
print(f"Cache Tag位数: {cache_tag_bits} ({physical_addr_bits}-{cache_index_bits}-{block_offset_bits}={cache_tag_bits})")

# ===== 校验6：虚拟地址0x01234567的字段拆分 =====
vpn_from_va = va_0x01234567 >> page_offset_bits
page_offset_from_va = va_0x01234567 & ((1 << page_offset_bits) - 1)
print(f"\n虚拟地址0x{va_0x01234567:X}拆分:")
print(f"  VPN: 0x{vpn_from_va:X} ({vpn_bits}位)")
print(f"  页内偏移: 0x{page_offset_from_va:X} ({page_offset_bits}位)")
assert vpn_from_va == vpn_0x01234, f"VPN不匹配: 0x{vpn_from_va:X} != 0x{vpn_0x01234:X}"

# ===== 校验7：物理地址计算 =====
physical_addr = (ppn_0x01234 << page_offset_bits) | page_offset_from_va
print(f"\n物理地址计算:")
print(f"  PPN: 0x{ppn_0x01234:X}")
print(f"  物理地址: 0x{physical_addr:X}")
assert physical_addr < (1 << physical_addr_bits), f"物理地址超出{physical_addr_bits}位范围"

# ===== 校验8：Cache字段提取 =====
cache_block_offset = physical_addr & ((1 << block_offset_bits) - 1)
cache_index = (physical_addr >> block_offset_bits) & ((1 << cache_index_bits) - 1)
cache_tag = physical_addr >> (block_offset_bits + cache_index_bits)
print(f"\nCache字段提取:")
print(f"  块内偏移: 0x{cache_block_offset:X} ({block_offset_bits}位)")
print(f"  Index: 0x{cache_index:X} ({cache_index_bits}位)")
print(f"  Tag: 0x{cache_tag:X} ({cache_tag_bits}位)")

# ===== 校验9：PPN位数是否足够 =====
assert ppn_0x01234 < (1 << ppn_bits), f"PPN 0x{ppn_0x01234:X} 超出{ppn_bits}位范围"
print(f"\nPPN 0x{ppn_0x01234:X} 在{ppn_bits}位范围内: OK")

# ===== 校验10：TLB Tag位数是否足够 =====
assert vpn_from_va < (1 << vpn_bits), f"VPN 0x{vpn_from_va:X} 超出{vpn_bits}位范围"
tlb_tag_from_vpn = vpn_from_va >> tlb_index_bits
tlb_index_from_vpn = vpn_from_va & ((1 << tlb_index_bits) - 1)
print(f"TLB字段提取:")
print(f"  TLB Tag: 0x{tlb_tag_from_vpn:X} ({tlb_tag_bits}位)")
print(f"  TLB Index: 0x{tlb_index_from_vpn:X} ({tlb_index_bits}位)")

print("\n✅ 参数校验全部通过")
