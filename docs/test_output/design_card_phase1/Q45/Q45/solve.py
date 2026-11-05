# ===== 题目参数定义 =====
va_bits = 32       # 虚拟地址位数
pa_bits = 24       # 物理地址位数
page_size = 64     # 页大小 64B
cache_size = 32 * 1024  # Cache 32KB
associativity = 4  # 4路组相联
block_size = 64    # 块大小 64B

# ===== 子问题(1)：计算各字段位数 =====
page_offset_bits = page_size.bit_length() - 1  # log2(64) = 6
block_offset_bits = block_size.bit_length() - 1  # log2(64) = 6

# 虚拟地址字段
A_bits = va_bits - page_offset_bits  # VPN = 32 - 6 = 26
B_bits = page_offset_bits  # 页内偏移 = 6

# Cache参数
num_blocks = cache_size // block_size  # 512
num_sets = num_blocks // associativity  # 128
set_index_bits = num_sets.bit_length() - 1  # log2(128) = 7
tag_bits = pa_bits - set_index_bits - block_offset_bits  # 24 - 7 - 6 = 11

# 物理地址字段
C_bits = tag_bits  # Tag = 11
D_bits = set_index_bits  # Index = 7
E_bits = block_offset_bits  # Block Offset = 6

# Cache地址字段
F_bits = tag_bits  # Tag = 11
G_bits = set_index_bits  # Index = 7

print(f"子问题(1):")
print(f"  A (VPN) = {A_bits}位")
print(f"  B (页内偏移) = {B_bits}位")
print(f"  C (Tag) = {C_bits}位")
print(f"  D (Index) = {D_bits}位")
print(f"  E (Block Offset) = {E_bits}位")
print(f"  F (Tag) = {F_bits}位")
print(f"  G (Index) = {G_bits}位")
print(f"  TLB标记字段存放：虚拟页号(VPN)")

# ===== 子问题(2)：地址转换与Cache映射 =====
va = 0x00123456
ppn_given = 0x003A5

# 提取页内偏移
page_offset = va & ((1 << page_offset_bits) - 1)  # 低6位

# 计算物理地址
pa = (ppn_given << block_offset_bits) | page_offset

# 提取Cache字段
cache_set = (pa >> block_offset_bits) & ((1 << set_index_bits) - 1)
cache_tag = pa >> (block_offset_bits + set_index_bits)

print(f"\n子问题(2):")
print(f"  虚拟地址: {hex(va)}")
print(f"  物理页号: {hex(ppn_given)}")
print(f"  页内偏移: {hex(page_offset)}")
print(f"  物理地址: {hex(pa)}")
print(f"  Cache组号: {cache_set} ({hex(cache_set)})")
print(f"  Cache Tag: {cache_tag} ({hex(cache_tag)})")

# ===== 最终输出 =====
print(f"\nANSWER:")
print(f"  (1) A={A_bits}位, B={B_bits}位, C={C_bits}位, D={D_bits}位, E={E_bits}位, F={F_bits}位, G={G_bits}位; TLB标记存放虚拟页号(VPN)")
print(f"  (2) Cache组号={cache_set}, Cache Tag={hex(cache_tag)}")
print(f"  (3) 可能。TLB缺失只影响地址转换过程，不影响Cache中数据的存在。")
