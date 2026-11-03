"""
Cache 命中率与平均访问时间（综合题）
直接映射一级 Cache，逐次访存模拟。
"""

# ==================== 参数 ====================
ADDR_BITS = 12          # 主存地址位数
BLOCK_SIZE = 32         # 块大小 (B)
NUM_BLOCKS = 8          # Cache 数据块数（直接映射 → 行数 = 块数）
T_C = 2                 # Cache 访问时间 (ns)
T_M = 18                # 主存访问时间 (ns)（缺失时取块）

ACCESS_SEQ = [0x040, 0x080, 0x040, 0x0C0, 0x080, 0x140, 0x040, 0x0C0]

# ==================== 地址划分 ====================
offset_bits = (BLOCK_SIZE - 1).bit_length()       # 块内偏移位数
index_bits   = (NUM_BLOCKS - 1).bit_length()      # Cache 行号位数
tag_bits     = ADDR_BITS - index_bits - offset_bits  # 标记位数

block_mask = BLOCK_SIZE - 1
index_mask = NUM_BLOCKS - 1

def parse_addr(addr):
    """返回 (tag, index, offset)"""
    offset = addr & block_mask
    index  = (addr >> offset_bits) & index_mask
    tag    = addr >> (offset_bits + index_bits)
    return tag, index, offset

# ==================== 逐次访存模拟（直接映射） ====================
# Cache 行状态: valid, tag
cache = [{"valid": False, "tag": -1} for _ in range(NUM_BLOCKS)]

trace = []          # 每次访问记录
hits = 0
misses = 0
conflict_misses = 0  # 冲突缺失（行有效但 tag 不同）

for i, addr in enumerate(ACCESS_SEQ):
    tag, index, offset = parse_addr(addr)
    line = cache[index]
    if line["valid"] and line["tag"] == tag:
        result = "H"   # 命中
        hits += 1
    else:
        result = "M"   # 缺失
        misses += 1
        if line["valid"] and line["tag"] != tag:
            conflict_misses += 1  # 冲突缺失：行有效但 tag 不匹配
        line["valid"] = True
        line["tag"]   = tag
    trace.append({
        "seq": i + 1,
        "addr": "0x%03X" % addr,
        "addr_bin": format(addr, "012b"),
        "tag": tag,
        "index": index,
        "offset": offset,
        "result": result,
    })

total = len(ACCESS_SEQ)
h = hits / total

# ==================== 平均访问时间 ====================
# 缺失代价 = t_c (先访问Cache确认未命中) + t_m (再访问主存取块)
miss_penalty = T_C + T_M
t_a = h * T_C + (1 - h) * miss_penalty

# ==================== 加速比 ====================
# 无 Cache: 每次访存直接访问主存, 时间 = t_c + t_m'
no_cache_time = T_C + T_M
S = no_cache_time / t_a

# ==================== 场景规则验证（assert 打到特征） ====================
# 规则1: Cache 容量一致性
assert BLOCK_SIZE * NUM_BLOCKS == 256, "Cache总容量应=256B"

# 规则2: 地址位数守恒
assert tag_bits + index_bits + offset_bits == ADDR_BITS

# 规则3: 命中率定义 & 非平凡
assert h == hits / total
assert 0 < h < 1, "命中率必须非平凡(0<h<1)"

# 规则4: 平均访问时间公式
assert t_a == h * T_C + (1 - h) * miss_penalty

# 规则5: 加速比定义 & S>1
assert S == no_cache_time / t_a
assert S > 1, "加速比应>1(Cache才有意义)"

# 规则6: 冲突缺失存在性
assert conflict_misses >= 1, "序列中应存在至少1次冲突缺失"

# 规则7: 时间参数约束
assert (T_C + T_M) >= 5 * T_C

# ==================== 数据流打印 ====================
print("=" * 60)
print("PARAMS:")
print("  ADDR_BITS=%d, BLOCK_SIZE=%d B, NUM_BLOCKS=%d" % (ADDR_BITS, BLOCK_SIZE, NUM_BLOCKS))
print("  T_C=%d ns, T_M=%d ns" % (T_C, T_M))
print("  ACCESS_SEQ =", ["0x%03X" % a for a in ACCESS_SEQ])
print()

print("=" * 60)
print("PROCESS [地址划分]:")
print("  Offset位数 = %d  (块大小 %d B → 2^%d)" % (offset_bits, BLOCK_SIZE, offset_bits))
print("  Index位数  = %d  (块数 %d → 2^%d)" % (index_bits, NUM_BLOCKS, index_bits))
print("  Tag位数    = %d  (%d - %d - %d)" % (tag_bits, ADDR_BITS, index_bits, offset_bits))
print("  地址格式:  Tag(%d) | Index(%d) | Offset(%d)" % (tag_bits, index_bits, offset_bits))
print()

print("=" * 60)
print("PROCESS [逐次访存分析]:")
print("  %-4s %-8s %-16s %-6s %-6s %-6s %-10s" %
      ("序号", "地址", "12位二进制", "Tag", "Index", "Offset", "命中/缺失"))
for r in trace:
    print("  %-4d %-8s %-16s %-6d %-6d %-6d %-10s" %
          (r["seq"], r["addr"], r["addr_bin"], r["tag"], r["index"], r["offset"], r["result"]))
print()
print("  命中次数 = %d, 缺失次数 = %d, 总访问 = %d" % (hits, misses, total))
print("  冲突缺失次数 = %d" % conflict_misses)
print()

print("=" * 60)
print("RESULT [第1问(3) 命中率]:")
print("  h = %d/%d = %s" % (hits, total, "%d/%d" % (hits, total)))
print("  h (小数) = %.4f" % h)
print()

print("RESULT [第2问 平均访问时间]:")
print("  缺失代价 = t_c + t_m' = %d + %d = %d ns" % (T_C, T_M, miss_penalty))
print("  t_a = h*t_c + (1-h)*(t_c+t_m')")
print("     = (%d/%d)*%d + (%d/%d)*%d" % (hits, total, T_C, misses, total, miss_penalty))
print("     = %.4f ns" % t_a)
from fractions import Fraction
t_a_frac = Fraction(hits, total) * T_C + Fraction(misses, total) * miss_penalty
print("     = %s ns  (精确分数 = %s)" % (str(t_a_frac), str(float(t_a_frac))))
print()

print("RESULT [第3问 加速比]:")
print("  无Cache单次访存时间 = t_c + t_m' = %d ns" % no_cache_time)
print("  S = %d / %s" % (no_cache_time, str(t_a_frac)))
S_frac = Fraction(no_cache_time) / t_a_frac
print("  S = %s ≈ %.2f" % (str(S_frac), float(S_frac)))
print()

print("=" * 60)
print("RULE_CHECK:")
print("  Cache总容量 = %d B (= %d×%d)" % (BLOCK_SIZE * NUM_BLOCKS, BLOCK_SIZE, NUM_BLOCKS))
print("  地址位数守恒: %d + %d + %d = %d (==%d)" % (tag_bits, index_bits, offset_bits, tag_bits + index_bits + offset_bits, ADDR_BITS))
print("  命中率 h = %d/%d, 0<h<1 ✓" % (hits, total))
print("  冲突缺失 = %d ≥ 1 ✓" % conflict_misses)
print("  加速比 S = %.2f > 1 ✓" % float(S_frac))
print("  t_c+t_m' = %d ≥ 5*t_c = %d ✓" % (T_C + T_M, 5 * T_C))
