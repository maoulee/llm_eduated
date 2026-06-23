# ===== 题目参数 =====
va_bits = 32       # 虚拟地址位数
pa_bits = 24       # 物理地址位数
page_size = 64     # 页大小 64B
cache_size = 32 * 1024  # Cache 32KB
associativity = 4  # 4路组相联
block_size = 64    # 块大小 64B

# ===== 校验1：页大小和块大小是否为2的幂 =====
assert page_size == 2 ** int(page_size.bit_length() - 1), "页大小不是2的幂"
assert block_size == 2 ** int(block_size.bit_length() - 1), "块大小不是2的幂"
assert cache_size == 2 ** int(cache_size.bit_length() - 1), "Cache大小不是2的幂"

# ===== 校验2：页内偏移 = 块内偏移 =====
page_offset_bits = page_size.bit_length() - 1  # log2(64) = 6
block_offset_bits = block_size.bit_length() - 1  # log2(64) = 6
assert page_offset_bits == block_offset_bits, f"页内偏移({page_offset_bits}) != 块内偏移({block_offset_bits})"

# ===== 校验3：Cache参数自洽 =====
num_blocks = cache_size // block_size  # 总块数
num_sets = num_blocks // associativity  # 组数
assert num_sets == 2 ** int(num_sets.bit_length() - 1), "组数不是2的幂"
set_index_bits = num_sets.bit_length() - 1  # log2(组数)

# ===== 校验4：地址字段位数加和 =====
vpn_bits = va_bits - page_offset_bits  # VPN位数
ppn_bits = pa_bits - block_offset_bits  # PPN位数
tag_bits = pa_bits - set_index_bits - block_offset_bits  # Tag位数

print(f"页内偏移/块内偏移: {page_offset_bits}位")
print(f"VPN: {vpn_bits}位")
print(f"PPN: {ppn_bits}位")
print(f"Cache总块数: {num_blocks}")
print(f"Cache组数: {num_sets}")
print(f"Cache组号: {set_index_bits}位")
print(f"Cache Tag: {tag_bits}位")
print(f"物理地址字段加和: {tag_bits} + {set_index_bits} + {block_offset_bits} = {tag_bits + set_index_bits + block_offset_bits} (应为{pa_bits})")
assert tag_bits + set_index_bits + block_offset_bits == pa_bits, "物理地址字段位数加和不等于物理地址总位数"

# ===== 校验5：子问(2)参数自洽 =====
va = 0x00123456
ppn_given = 0x003A5
# PPN应该在范围内
assert ppn_given < (1 << ppn_bits), f"物理页号{hex(ppn_given)}超出范围(需要{ppn_bits}位)"

# 计算物理地址
pa = (ppn_given << block_offset_bits) | (va & ((1 << page_offset_bits) - 1))
assert pa < (1 << pa_bits), f"物理地址{hex(pa)}超出范围"

print(f"\n子问(2)参数:")
print(f"虚拟地址: {hex(va)}")
print(f"物理页号: {hex(ppn_given)}")
print(f"物理地址: {hex(pa)}")

# 提取Cache字段
cache_set = (pa >> block_offset_bits) & ((1 << set_index_bits) - 1)
cache_tag = pa >> (block_offset_bits + set_index_bits)
print(f"Cache组号: {cache_set} ({hex(cache_set)})")
print(f"Cache Tag: {cache_tag} ({hex(cache_tag)})")

print("\n参数校验通过")
