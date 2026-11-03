"""
Cache 地址映射综合题 —— 建模求解
主存 M=2^24B(16MB), Cache C=2^12B(4KB), 块 B=2^5B(32B), 按字节编址
Q1: 直接映射     Q2: 4路组相联     Q3: 地址 0x123450 定位
"""
import math

# ============ 题干参数 ============
M = 1 << 24          # 主存地址空间 16 MB = 2^24 B
C = 1 << 12          # Cache 容量 4 KB = 2^12 B
B = 1 << 5           # 块(行)大小 32 B = 2^5 B
W = 4                # 组相联路数

addr = 0x123450      # Q3 给定块起始地址


# ============ 通用计算 ============
addr_bits   = int(math.log2(M))    # 主存地址总位数 = 24
offset_bits = int(math.log2(B))    # 块内偏移位数    = 5  (SR-1)
num_lines   = C // B               # Cache 行数      = 128


# ============ Q1: 直接映射 ============
line_bits_dir  = int(math.log2(num_lines))               # 行号位数 = 7
tag_bits_dir   = addr_bits - line_bits_dir - offset_bits # Tag位数 = 12

# 地址范围（从最低位起编号）
offset_range_dir = f"位 {offset_bits - 1} ~ 位 0"
line_range_dir   = f"位 {line_bits_dir + offset_bits - 1} ~ 位 {offset_bits}"
tag_range_dir    = f"位 {addr_bits - 1} ~ 位 {line_bits_dir + offset_bits}"


# ============ Q2: 4路组相联映射 ============
num_sets       = num_lines // W                          # 组数 = 32
set_bits_sa    = int(math.log2(num_sets))               # 组号位数 = 5
tag_bits_sa    = addr_bits - set_bits_sa - offset_bits  # Tag位数 = 14

offset_range_sa = f"位 {offset_bits - 1} ~ 位 0"
set_range_sa    = f"位 {set_bits_sa + offset_bits - 1} ~ 位 {offset_bits}"
tag_range_sa    = f"位 {addr_bits - 1} ~ 位 {set_bits_sa + offset_bits}"


# ============ Q3: 地址 0x123450 定位 ============
# 块内偏移
intra_offset = addr % B                                   # = 0（块对齐）
block_start  = addr - intra_offset                        # 块起始地址

# 直接映射：行号 = 块号 mod 行数；Tag = 块号 // 行数
block_num       = block_start // B
dir_line_idx    = block_num % num_lines
dir_tag_value   = block_num // num_lines

# 组相联：组号 = 块号 mod 组数；Tag = 块号 // 组数
sa_set_idx      = block_num % num_sets
sa_tag_value    = block_num // num_sets


# ============ 数据流输出 ============
print("=" * 60)
print("PARAMS:")
print(f"  主存容量 M   = 2^{int(math.log2(M))} B = {M} B")
print(f"  Cache容量 C  = 2^{int(math.log2(C))} B = {C} B")
print(f"  块大小 B     = 2^{int(math.log2(B))} B = {B} B")
print(f"  组相联路数 w = {W}")
print(f"  按字节编址, 地址总位数 = {addr_bits}")
print(f"  Cache行数   = C/B = {num_lines}")
print(f"  Q3给定地址  = 0x{addr:X} = {addr}")

print("\n" + "=" * 60)
print("PROCESS — Q1 直接映射:")
print(f"  块内偏移位数 = log2(B) = {offset_bits}")
print(f"  行号位数     = log2(行数) = log2({num_lines}) = {line_bits_dir}")
print(f"  Tag位数      = {addr_bits} - {line_bits_dir} - {offset_bits} = {tag_bits_dir}")
print(f"  三字段之和   = {tag_bits_dir} + {line_bits_dir} + {offset_bits} = {tag_bits_dir + line_bits_dir + offset_bits}")
print(f"  [表] Tag:  {tag_bits_dir}位, 范围 {tag_range_dir}")
print(f"  [表] 行号: {line_bits_dir}位, 范围 {line_range_dir}")
print(f"  [表] 偏移: {offset_bits}位, 范围 {offset_range_dir}")

print("\n" + "=" * 60)
print("PROCESS — Q2 4路组相联映射:")
print(f"  组数   = 行数/路数 = {num_lines}/{W} = {num_sets}")
print(f"  块内偏移位数 = {offset_bits}")
print(f"  组号位数     = log2(组数) = log2({num_sets}) = {set_bits_sa}")
print(f"  Tag位数      = {addr_bits} - {set_bits_sa} - {offset_bits} = {tag_bits_sa}")
print(f"  三字段之和   = {tag_bits_sa} + {set_bits_sa} + {offset_bits} = {tag_bits_sa + set_bits_sa + offset_bits}")
print(f"  [表] Tag:  {tag_bits_sa}位, 范围 {tag_range_sa}")
print(f"  [表] 组号: {set_bits_sa}位, 范围 {set_range_sa}")
print(f"  [表] 偏移: {offset_bits}位, 范围 {offset_range_sa}")

print("\n" + "=" * 60)
print("PROCESS — Q3 地址 0x%X 定位:" % addr)
print(f"  块号         = 地址 / B = {addr} / {B} = {block_num}")
print(f"  块内偏移     = 地址 mod B = {intra_offset}  (块对齐)")
print(f"  --- 直接映射 ---")
print(f"  映射行号     = 块号 mod 行数 = {block_num} mod {num_lines} = {dir_line_idx}")
print(f"  Tag值        = 块号 / 行数  = {block_num} / {num_lines} = {dir_tag_value}")
print(f"  --- 4路组相联 ---")
print(f"  映射组号     = 块号 mod 组数 = {block_num} mod {num_sets} = {sa_set_idx}")
print(f"  Tag值        = 块号 / 组数  = {block_num} / {num_sets} = {sa_tag_value}")

print("\n" + "=" * 60)
print("RESULT:")
print(f"  Q1 直接映射:  Tag={tag_bits_dir}位, 行号={line_bits_dir}位, 偏移={offset_bits}位")
print(f"  Q2 组相联映射: Tag={tag_bits_sa}位, 组号={set_bits_sa}位, 偏移={offset_bits}位")
print(f"  Q3 直接映射:  行号={dir_line_idx}, Tag={dir_tag_value}")
print(f"  Q3 组相联:    组号={sa_set_idx}, Tag={sa_tag_value}")


# ============ 场景规则验证（assert 命中通过条件）============
# SR-1: 块内偏移 = log2(B) = 5
assert offset_bits == int(math.log2(B)) == 5, "SR-1"

# SR-2: 直接映射字段一致性
assert num_lines == C // B == (1 << 7), "SR-2 行数=128"
assert line_bits_dir == 7, "SR-2 行号位数=7"
assert tag_bits_dir == 12, "SR-2 Tag位数=12"
assert tag_bits_dir + line_bits_dir + offset_bits == addr_bits, "SR-2 三段之和=地址总位数"

# SR-3: 组相联映射字段一致性
assert num_sets == num_lines // W == 32, "SR-3 组数=32"
assert set_bits_sa == 5, "SR-3 组号位数=5"
assert tag_bits_sa == 14, "SR-3 Tag位数=14"
assert tag_bits_sa + set_bits_sa + offset_bits == addr_bits, "SR-3 三段之和=地址总位数"

# SR-4: 两种映射 Tag 位数至少差 1（区分度）
assert abs(tag_bits_sa - tag_bits_dir) >= 1, "SR-4 区分度"

# SR-5: Q3 地址在地址空间内（定位用块号=addr//B，偏移不影响块号）
assert addr < M, "SR-5 地址在主存空间内"
assert addr // B == (addr & ~(B - 1)) // B, "SR-5 块号计算一致"

print("\n" + "=" * 60)
print("ALL SCENARIO RULES (SR-1 ~ SR-5) PASSED.")
