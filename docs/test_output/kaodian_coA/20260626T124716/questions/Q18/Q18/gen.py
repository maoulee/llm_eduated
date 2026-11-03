"""
Cache 地址映射格式设计 — 建模求解
题干规则翻译为代码，通过条件翻译为 assert。
"""
import math

# ============================================================
# PARAMS：题干参数
# ============================================================
M = 64 * 2**20      # 主存容量 64 MB = 2^26 B
C = 16 * 2**10      # Cache 容量 16 KB = 2^14 B
B = 64              # 块长 64 B = 2^6 B
WAYS = 4            # 四路组相联路数

ADDR_BITS = int(math.log2(M))          # 主存地址位数 = 26
BLOCK_OFFSET_BITS = int(math.log2(B))  # 块内地址位数 = 6
CACHE_LINES = C // B                    # Cache 行数 = 256
LINE_BITS = int(math.log2(CACHE_LINES))# 行号位数 = 8
NUM_SETS = CACHE_LINES // WAYS          # 组数（四路）= 64
SET_BITS = int(math.log2(NUM_SETS))    # 组号位数 = 6

print("=" * 60)
print("PARAMS")
print("=" * 60)
print(f"主存容量 M          = {M} B = 2^{ADDR_BITS} B")
print(f"Cache容量 C         = {C} B = 2^{int(math.log2(C))} B")
print(f"块长 B              = {B} B = 2^{BLOCK_OFFSET_BITS} B")
print(f"主存地址位数        = {ADDR_BITS}")
print(f"块内地址位数        = {BLOCK_OFFSET_BITS}")
print(f"Cache 行数          = {CACHE_LINES} = 2^{LINE_BITS}")
print(f"行号位数            = {LINE_BITS}")
print(f"路数（四路）        = {WAYS}")
print(f"组数（四路）        = {NUM_SETS} = 2^{SET_BITS}")
print(f"组号位数            = {SET_BITS}")
print()

# ============================================================
# 推导三种映射方式的字段划分
# ============================================================
print("=" * 60)
print("REASONING")
print("=" * 60)

# --- (1) 直接映射：Tag + 行号 + 块内地址 ---
dm_tag = ADDR_BITS - LINE_BITS - BLOCK_OFFSET_BITS
dm_total = dm_tag + LINE_BITS + BLOCK_OFFSET_BITS
print(f"\n--- (1) 直接映射 ---")
print(f"地址 = Tag + 行号(Line) + 块内地址(Block Offset)")
print(f"  行号位数     = log2(Cache行数) = log2({CACHE_LINES}) = {LINE_BITS}")
print(f"  块内地址位数 = log2(块长)      = log2({B}) = {BLOCK_OFFSET_BITS}")
print(f"  Tag位数      = {ADDR_BITS} - {LINE_BITS} - {BLOCK_OFFSET_BITS} = {dm_tag}")
print(f"  总和         = {dm_tag} + {LINE_BITS} + {BLOCK_OFFSET_BITS} = {dm_total}")

# --- (2) 四路组相联：Tag + 组号 + 块内地址 ---
sa_tag = ADDR_BITS - SET_BITS - BLOCK_OFFSET_BITS
sa_total = sa_tag + SET_BITS + BLOCK_OFFSET_BITS
print(f"\n--- (2) 四路组相联 ---")
print(f"地址 = Tag + 组号(Set) + 块内地址(Block Offset)")
print(f"  组数         = Cache行数 / 路数 = {CACHE_LINES} / {WAYS} = {NUM_SETS}")
print(f"  组号位数     = log2({NUM_SETS}) = {SET_BITS}")
print(f"  块内地址位数 = log2(块长)      = log2({B}) = {BLOCK_OFFSET_BITS}")
print(f"  Tag位数      = {ADDR_BITS} - {SET_BITS} - {BLOCK_OFFSET_BITS} = {sa_tag}")
print(f"  总和         = {sa_tag} + {SET_BITS} + {BLOCK_OFFSET_BITS} = {sa_total}")

# --- (3) 全相联：Tag + 块内地址 ---
fa_tag = ADDR_BITS - BLOCK_OFFSET_BITS
fa_total = fa_tag + BLOCK_OFFSET_BITS
print(f"\n--- (3) 全相联 ---")
print(f"地址 = Tag + 块内地址(Block Offset)")
print(f"  块内地址位数 = log2(块长) = log2({B}) = {BLOCK_OFFSET_BITS}")
print(f"  Tag位数      = {ADDR_BITS} - {BLOCK_OFFSET_BITS} = {fa_tag}")
print(f"  总和         = {fa_tag} + {BLOCK_OFFSET_BITS} = {fa_total}")

# ============================================================
# ANSWER
# ============================================================
print()
print("=" * 60)
print("ANSWER")
print("=" * 60)
print(f"(1) 直接映射:   Tag {dm_tag}位 + 行号 {LINE_BITS}位 + 块内地址 {BLOCK_OFFSET_BITS}位 = {dm_total}位")
print(f"(2) 四路组相联: Tag {sa_tag}位 + 组号 {SET_BITS}位 + 块内地址 {BLOCK_OFFSET_BITS}位 = {sa_total}位")
print(f"(3) 全相联:     Tag {fa_tag}位 + 块内地址 {BLOCK_OFFSET_BITS}位 = {fa_total}位")

# ============================================================
# ASSERT：通过条件翻译为断言（打到特征，禁弱化/禁恒真）
# ============================================================
# 条件1: 三种映射方式的 Tag 位数各不相同，严格递增
assert dm_tag < sa_tag < fa_tag, \
    f"Tag位数应严格递增: 直接映射({dm_tag}) < 四路组相联({sa_tag}) < 全相联({fa_tag})"
assert len({dm_tag, sa_tag, fa_tag}) == 3, \
    f"三种映射方式Tag位数应互不相同: {dm_tag}, {sa_tag}, {fa_tag}"

# 条件2: 三种映射方式各字段位数之和均等于 26
assert dm_total == ADDR_BITS, f"直接映射字段和 {dm_total} != {ADDR_BITS}"
assert sa_total == ADDR_BITS, f"四路组相联字段和 {sa_total} != {ADDR_BITS}"
assert fa_total == ADDR_BITS, f"全相联字段和 {fa_total} != {ADDR_BITS}"

# 条件3: 直接映射字段完整 — Tag + 行号 + 块内地址，行号位数 = 8
assert dm_tag > 0 and LINE_BITS > 0 and BLOCK_OFFSET_BITS > 0, "直接映射各字段必须为正"
assert LINE_BITS == 8, f"行号位数应为8，实际 {LINE_BITS}"

# 条件4: 四路组相联字段完整 — Tag + 组号 + 块内地址，组号位数 = 6
assert sa_tag > 0 and SET_BITS > 0 and BLOCK_OFFSET_BITS > 0, "四路组相联各字段必须为正"
assert SET_BITS == 6, f"组号位数应为6，实际 {SET_BITS}"
# 路数4不单独占字段但影响组数计算
assert NUM_SETS == CACHE_LINES // WAYS, "组数 = Cache行数 / 路数"
assert SET_BITS == int(math.log2(CACHE_LINES // WAYS)), "组号位数 = log2(组数)"

# 条件5: 全相联字段完整 — Tag + 块内地址，两段之和 = 26，无行号/组号字段
assert fa_tag > 0 and BLOCK_OFFSET_BITS > 0, "全相联各字段必须为正"
assert fa_total == ADDR_BITS, f"全相联字段和 {fa_total} != {ADDR_BITS}"

print("\n✅ 所有通过条件 assert 均已满足。")
