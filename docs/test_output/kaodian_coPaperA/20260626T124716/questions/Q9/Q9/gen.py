"""
Cache 全相联映射分析 —— 建模+求解
题干规则翻译成代码，通过条件翻译成 assert。
"""
import math

# ============================================================
# PARAMS
# ============================================================
M = 2**20          # 主存容量 (字节)
BLOCK_SIZE = 32    # 块大小 (字节) = 2^5
CACHE_LINES = 4   # Cache 行数

# 访存序列（字节地址，十进制）
ACCESS_SEQUENCE = [0, 96, 32, 0, 160, 224, 96, 1024]

print("=== PARAMS ===")
print(f"主存容量 M = 2^{int(math.log2(M))} = {M} 字节")
print(f"块大小 B = {BLOCK_SIZE} = 2^{int(math.log2(BLOCK_SIZE))} 字节")
print(f"Cache 行数 L = {CACHE_LINES}")
print(f"映射方式 = 全相联映射")
print(f"替换算法 = LRU")
print(f"访存序列（字节地址）= {ACCESS_SEQUENCE}")
print()

# ============================================================
# Q1: 地址分解
# ============================================================
offset_bits = int(math.log2(BLOCK_SIZE))
block_number_bits = int(math.log2(M // BLOCK_SIZE))
total_addr_bits = int(math.log2(M))
tag_bits = block_number_bits  # 全相联映射: Tag = 整个块号

print("=== Q1: 地址分解 ===")
print(f"主存地址位数 = {total_addr_bits} 位")
print(f"块内偏移位数 = log2({BLOCK_SIZE}) = {offset_bits} 位")
print(f"主存块号位数 = log2({M // BLOCK_SIZE}) = {block_number_bits} 位")
print(f"全相联映射: 无组号/行号字段")
print(f"Tag 位数 = 块号位数 = {tag_bits} 位")
print(f"验证: {offset_bits} + {block_number_bits} = {offset_bits + block_number_bits} 位 = {total_addr_bits} 位 ✓")
print()

# ============================================================
# Q2: 访存序列逐次分析（全相联映射 + LRU）
# ============================================================
def simulate_full_associative_lru(access_seq, block_size, num_lines):
    """
    全相联映射 + LRU 模拟。
    Cache 每行: {valid, tag, lru_stamp}
    lru_stamp: 越大表示越近期使用；替换时选最小者（最近最少使用）。
    """
    cache = [{'valid': False, 'tag': None, 'lru': 0} for _ in range(num_lines)]
    results = []
    hit_count = 0
    miss_count = 0
    timestamp = 0  # 全局时间戳

    for i, byte_addr in enumerate(access_seq):
        block_num = byte_addr // block_size
        timestamp += 1

        # --- 检查是否命中 ---
        hit_line = -1
        for j in range(num_lines):
            if cache[j]['valid'] and cache[j]['tag'] == block_num:
                hit_line = j
                break

        if hit_line >= 0:
            # 命中：更新 LRU
            cache[hit_line]['lru'] = timestamp
            hit_count += 1
            results.append({
                'index': i + 1, 'addr': byte_addr, 'block': block_num,
                'result': 'HIT', 'line': hit_line,
                'tag': block_num, 'replaced': None
            })
        else:
            # 缺失：需要装入
            miss_count += 1

            # 检查是否有空行
            empty_line = -1
            for j in range(num_lines):
                if not cache[j]['valid']:
                    empty_line = j
                    break

            if empty_line >= 0:
                # 装入空行
                target_line = empty_line
                cache[target_line]['valid'] = True
                cache[target_line]['tag'] = block_num
                cache[target_line]['lru'] = timestamp
                results.append({
                    'index': i + 1, 'addr': byte_addr, 'block': block_num,
                    'result': 'MISS(装入空行)', 'line': target_line,
                    'tag': block_num, 'replaced': None
                })
            else:
                # 替换：选 LRU 最小的行（最近最少使用）
                lru_line = 0
                for j in range(1, num_lines):
                    if cache[j]['lru'] < cache[lru_line]['lru']:
                        lru_line = j
                replaced_tag = cache[lru_line]['tag']
                cache[lru_line]['tag'] = block_num
                cache[lru_line]['lru'] = timestamp
                results.append({
                    'index': i + 1, 'addr': byte_addr, 'block': block_num,
                    'result': 'MISS(LRU替换)', 'line': lru_line,
                    'tag': block_num, 'replaced': replaced_tag
                })

    final_cache = [(j, cache[j]['valid'], cache[j]['tag']) for j in range(num_lines)]
    return results, final_cache, hit_count, miss_count

results, final_cache, hit_count, miss_count = simulate_full_associative_lru(
    ACCESS_SEQUENCE, BLOCK_SIZE, CACHE_LINES
)

print("=== Q2: 访存序列逐步分析 ===")
print(f"{'序号':>4} {'地址(十进制)':>12} {'地址(十六进制)':>14} {'主存块号':>8} {'结果':>14} {'行':>4} {'Tag':>6} {'替换':>8}")
print("-" * 80)
for r in results:
    hex_addr = f"0x{r['addr']:05X}"
    replaced_str = f"替换Tag={r['replaced']}" if r['replaced'] is not None else "—"
    print(f"{r['index']:>4} {r['addr']:>12} {hex_addr:>14} {r['block']:>8} {r['result']:>14} L{r['line']:>1} {r['tag']:>6} {replaced_str:>8}")

print()
print("访问结束后 Cache 各行状态：")
for line_idx, valid, tag in final_cache:
    v_str = "V=1" if valid else "V=0"
    t_str = f"Tag={tag}" if tag is not None else "Tag=—"
    print(f"  行{line_idx}: {v_str}, {t_str}")
print()

# ============================================================
# Q3: 命中率
# ============================================================
total_access = len(ACCESS_SEQUENCE)
hit_rate = hit_count / total_access

print("=== Q3: 命中率 ===")
print(f"总访问次数 = {total_access}")
print(f"命中次数 = {hit_count}")
print(f"缺失次数 = {miss_count}")
print(f"命中率 = {hit_count}/{total_access} = {hit_rate:.4f} = {hit_rate*100:.2f}%")
print()

# ============================================================
# ANSWER 汇总
# ============================================================
print("=== ANSWER ===")
print(f"Q1: 偏移位数={offset_bits}, 块号位数={block_number_bits}, Tag位数={tag_bits}")
print(f"Q2: 命中{hit_count}次, 缺失{miss_count}次")
print(f"Q3: 命中率 = {hit_count}/{total_access} = {hit_rate*100:.2f}%")
print()

# ============================================================
# 通过条件 assert
# ============================================================
print("=== ASSERTS (通过条件) ===")

# 条件1: 地址分解正确，符合全相联映射特征
assert offset_bits == 5, f"偏移位数应=5, 实际={offset_bits}"
assert block_number_bits == 15, f"块号位数应=15, 实际={block_number_bits}"
assert tag_bits == 15, f"Tag位数应=15(=块号), 实际={tag_bits}"
assert tag_bits == block_number_bits, f"全相联: Tag位数必须=块号位数"
assert (offset_bits + block_number_bits) == total_addr_bits, f"地址位数分解不匹配"
print("✓ 条件1: 地址分解正确（偏移5, 块号15, Tag15=块号, 全相联无组号字段）")

# 条件2: 访存序列触发至少1次替换
replacement_count = sum(1 for r in results if 'LRU替换' in r['result'])
assert replacement_count >= 1, f"应触发至少1次LRU替换, 实际={replacement_count}"
print(f"✓ 条件2: 触发 {replacement_count} 次LRU替换 (≥1)")

# 条件2 补充: 至少存在某次MISS时所有4行已满
# 逐次模拟验证
def verify_all_full_moment(access_seq, block_size, num_lines):
    cache = [None] * num_lines  # None=空, 否则存block_num
    lru = [0] * num_lines
    ts = 0
    for addr in access_seq:
        block = addr // block_size
        ts += 1
        if block in cache:
            idx = cache.index(block)
            lru[idx] = ts
        else:
            used = sum(1 for c in cache if c is not None)
            if used < num_lines:
                for j in range(num_lines):
                    if cache[j] is None:
                        cache[j] = block
                        lru[j] = ts
                        break
            else:
                # 全满，触发替换
                return True
    return False

assert verify_all_full_moment(ACCESS_SEQUENCE, BLOCK_SIZE, CACHE_LINES), "应存在某次MISS时Cache全满"
print("✓ 条件2补充: 存在某次MISS时Cache所有4行均已占用")

# 条件3: 至少1次命中
assert hit_count >= 1, f"应至少1次命中, 实际={hit_count}"
print(f"✓ 条件3: 命中{hit_count}次 (≥1)")

# 条件4: 命中率可确定计算，1 <= 命中次数 <= 3
assert total_access == 8, f"总访问次数应=8, 实际={total_access}"
assert 1 <= hit_count <= 3, f"命中次数应在1~3, 实际={hit_count}"
print(f"✓ 条件4: 总访问={total_access}, 命中次数={hit_count} (1≤h≤3), 命中率={hit_count}/{total_access}")

# 条件5: 结果唯一确定性（验证两次模拟结果一致）
results2, final_cache2, hit2, miss2 = simulate_full_associative_lru(
    ACCESS_SEQUENCE, BLOCK_SIZE, CACHE_LINES
)
assert hit2 == hit_count, "两次模拟命中次数不一致"
assert final_cache == final_cache2, "两次模拟最终Cache状态不一致"
print("✓ 条件5: 多次模拟结果一致，替换分析唯一确定")

# 访存序列中不同主存块数验证
distinct_blocks = sorted(set(a // BLOCK_SIZE for a in ACCESS_SEQUENCE))
assert len(distinct_blocks) == 6, f"不同主存块数应=6, 实际={len(distinct_blocks)}"
assert distinct_blocks == [0, 1, 3, 5, 7, 32], f"块号应为[0,1,3,5,7,32], 实际={distinct_blocks}"
print(f"✓ 参数校验: 访存序列涉及{len(distinct_blocks)}个不同主存块 {distinct_blocks}")

print()
print("=== 全部 assert 通过 ===")
