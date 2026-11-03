"""
Cache 全相联映射分析 —— 建模 + 数据流打印
题干规则逐句翻译成代码，底部 print 完整数据流。
"""
import math

# ============ 参数 ============
C = 2048       # Cache 数据区容量 (2KB)
L = 64         # 行长/块大小
A = 16         # 主存地址位数
N = C // L     # Cache 行数
b = int(math.log2(L))   # 块内地址位数
m = A - b              # 主存块号位数（全相联 Tag 位数）

addresses = [0x0280, 0x0A00, 0x0500, 0x0C00, 0x0140, 0x1000]

# ============ 地址分解 ============
def decompose(addr):
    """翻译题干：全相联映射地址 = Tag(块号) + 块内地址"""
    block_number = addr >> b          # 块号 = Tag
    block_offset = addr & ((1 << b) - 1)
    return block_number, block_offset

# ============ 初始 Cache 状态 ============
# cache_lines[i] = 行 i 当前存放的块号；初始行 i 存放块 i
cache_lines = list(range(N))  # [0,1,...,31]
# fifo_queue: 按装入顺序排列的块号列表，队首(最早装入)最先被替换
fifo_queue = list(range(N))   # [0,1,...,31]

# ============ 逐地址分析 ============
process_log = []
hit_count = 0
changes = {}  # row_index -> (old_block, new_block) 记录变化

for idx, addr in enumerate(addresses):
    blk, off = decompose(addr)
    # 命中判定：块号在 cache_lines 中
    hit = blk in cache_lines
    entry = {"序号": idx + 1, "地址(hex)": hex(addr), "块号(Tag)": blk,
             "块内偏移": off, "命中": hit}

    if hit:
        hit_count += 1
        entry["结果"] = "命中"
        entry["装入行号"] = None
        entry["替换"] = False
        entry["被替换块号"] = None
    else:
        # 未命中：Cache 已满 → FIFO 替换队首
        replaced_block = fifo_queue[0]
        # 找到 replaced_block 所在的物理行号
        target_row = cache_lines.index(replaced_block)
        old_block = cache_lines[target_row]
        cache_lines[target_row] = blk
        # 更新 FIFO 队列
        fifo_queue.pop(0)
        fifo_queue.append(blk)
        # 记录变化
        changes[target_row] = (old_block, blk)
        entry["结果"] = "未命中"
        entry["装入行号"] = target_row
        entry["替换"] = True
        entry["被替换块号"] = old_block
        entry["FIFO替换后队列"] = list(fifo_queue)

    entry["Cache状态"] = list(cache_lines)
    process_log.append(entry)

# ============ 最终状态 ============
hit_rate = hit_count / len(addresses)

# ============ 场景规则断言（参数间约束，非 answer-recipe）============
# 1. 参数一致性
assert N == C // L, "行数 != 容量/行长"
assert b == int(math.log2(L)), "块内地址位数 != log2(行长)"
assert m == A - b, "块号位数 != 地址位数 - 块内位数"
assert m + b == A, "全相联: Tag位数(m)+块内地址位数(b) != 地址总线位数(A)"  # 地址位守恒

# 2. 地址分解 + 范围
for addr in addresses:
    blk, off = decompose(addr)
    assert addr < (1 << A), f"地址 {hex(addr)} 超出地址空间"
    assert blk == addr >> b
    assert off == addr & ((1 << b) - 1)

# 3. 命中判定（全相联比较块号）
# 4. FIFO 不变量：替换仅当 Cache 满且未命中 —— 初始已满，每次未命中必替换
# 5. 序列设计约束
block_numbers = [decompose(addr)[0] for addr in addresses]
assert len(block_numbers) != len(set(block_numbers)) or any(bn in range(N) for bn in block_numbers), \
    "至少一对地址块号相同或某块号在初始Cache中（保证命中）"
assert any(bn >= N for bn in block_numbers), "至少一个块号不在初始Cache中（保证装入）"

# 6. 最终状态一致性
assert len(cache_lines) <= N, "Cache 占用行数 <= N"
assert all(0 <= blk < (1 << m) for blk in cache_lines), "块号在合法范围"

# ============ 底部数据流 ============
print("=" * 70)
print("PARAMS:")
print(f"  C(容量)={C}B, L(行长)={L}B, A(地址位数)={A}")
print(f"  N(行数)={N}, b(块内地址位数)={b}, m(块号位数/Tag位数)={m}")
print()

print("问题1:")
print(f"  Cache行数 N = C/L = {C}/{L} = {N}")
print(f"  全相联映射地址结构: Tag({m}位) + 块内地址({b}位)")
print(f"  Tag位数 = m = {m}位")
print()

print("问题2 (逐地址分析):")
for e in process_log:
    print(f"  {e['序号']}: 地址{e['地址(hex)']} → 块号={e['块号(Tag)']}, 偏移={e['块内偏移']}")
    if e['命中']:
        print(f"      → 命中（块号{e['块号(Tag)']}已在Cache中）")
    else:
        print(f"      → 未命中 → 装入行{e['装入行号']}, 替换块{e['被替换块号']}")
print()

print("问题3:")
print(f"  发生变化的行: {dict(changes)}")
print(f"  最终Cache各行块号: {cache_lines}")
print(f"  命中次数: {hit_count}, 命中率: {hit_count}/{len(addresses)} = {hit_rate:.4f}")
print()

# 地址块号汇总
print("地址块号汇总:")
for i, addr in enumerate(addresses):
    blk, off = decompose(addr)
    print(f"  {i+1}: {hex(addr)} = {addr:#06b}[{addr}] >> 块号={blk} (0b{blk:b}), 偏移={off}")
print("=" * 70)
print(f"RESULT: 命中次数={hit_count}, 命中率={hit_rate:.4f}, 变化行={list(changes.keys())}")
print(f"RESULT: 最终各变化行Tag: " + ", ".join(f"行{r}→块{changes[r][1]}" for r in sorted(changes)))
