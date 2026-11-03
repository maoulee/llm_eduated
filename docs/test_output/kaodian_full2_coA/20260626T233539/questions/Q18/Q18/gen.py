"""
Cache 地址映射格式设计 — gen.py
把题干规则翻译成代码，底部 print 完整数据流，
用 assert 逐一验证场景规则（通过条件）的 6 条约束。
"""
import math


def solve(M_exp, C_exp, B_exp, ways=4):
    """M=主存容量, C=Cache容量, B=块长（均以 2 的指数给出）。"""
    M = 2 ** M_exp
    C = 2 ** C_exp
    B = 2 ** B_exp

    addr_bits = M_exp                          # 主存地址位数 = log2(M)，按字节编址
    block_offset = B_exp                       # 块内地址位数 = log2(B)
    num_lines = C // B                         # Cache 行数
    num_sets = C // (B * ways)                 # 组数 = 行数 / 路数

    # --- 直接映射 ---
    dm_line_bits = int(math.log2(num_lines))
    dm_tag_bits = addr_bits - dm_line_bits - block_offset
    dm_total = dm_tag_bits + dm_line_bits + block_offset

    # --- 四路组相联 ---
    sa_set_bits = int(math.log2(num_sets))
    sa_tag_bits = addr_bits - sa_set_bits - block_offset
    sa_total = sa_tag_bits + sa_set_bits + block_offset

    # --- 全相联 ---
    fa_tag_bits = addr_bits - block_offset
    fa_set_bits = 0
    fa_total = fa_tag_bits + block_offset

    return {
        "M": M, "C": C, "B": B, "ways": ways,
        "M_exp": M_exp, "C_exp": C_exp, "B_exp": B_exp,
        "addr_bits": addr_bits,
        "block_offset": block_offset,
        "num_lines": num_lines,
        "num_sets": num_sets,
        "direct": {"tag": dm_tag_bits, "line": dm_line_bits,
                   "offset": block_offset, "total": dm_total},
        "set_assoc": {"tag": sa_tag_bits, "set": sa_set_bits,
                      "offset": block_offset, "total": sa_total,
                      "num_sets": num_sets},
        "full_assoc": {"tag": fa_tag_bits, "set": fa_set_bits,
                       "offset": block_offset, "total": fa_total},
    }


# ============ 注入参数 ============
r = solve(M_exp=28, C_exp=15, B_exp=5, ways=4)

# ============ 底部：打印完整数据流 ============
print("=" * 60)
print("PARAMS:")
print(f"  主存容量 M  = 2^{r['M_exp']} = {r['M']} B")
print(f"  Cache容量 C = 2^{r['C_exp']} = {r['C']} B")
print(f"  块长 B      = 2^{r['B_exp']} = {r['B']} B")
print(f"  组相联路数  = {r['ways']}")
print()
print("PROCESS（推导中间值）:")
print(f"  主存地址位数  addr_bits = {r['addr_bits']}")
print(f"  块内地址位数  block_offset = log2(B) = {r['block_offset']}")
print(f"  Cache 行数    num_lines = C/B = {r['num_lines']}")
print(f"  组数          num_sets  = C/(B*ways) = {r['num_sets']}")
print()

print("--- 直接映射 ---")
d = r["direct"]
print(f"  行号位 = log2({r['num_lines']}) = {d['line']}")
print(f"  标记位 = {r['addr_bits']} - {d['line']} - {d['offset']} = {d['tag']}")
print(f"  总位数 = {d['tag']} + {d['line']} + {d['offset']} = {d['total']}")
print()

print("--- 四路组相联映射 ---")
s = r["set_assoc"]
print(f"  组数   = {r['num_sets']}")
print(f"  组号位 = log2({r['num_sets']}) = {s['set']}")
print(f"  标记位 = {r['addr_bits']} - {s['set']} - {s['offset']} = {s['tag']}")
print(f"  总位数 = {s['tag']} + {s['set']} + {s['offset']} = {s['total']}")
print()

print("--- 全相联映射 ---")
f = r["full_assoc"]
print(f"  无索引位（组号位 = {f['set']}）")
print(f"  标记位 = {r['addr_bits']} - {f['offset']} = {f['tag']}")
print(f"  总位数 = {f['tag']} + {f['offset']} = {f['total']}")
print()

print("RESULT（答案汇总）:")
print("  直接映射:   标记={}, 行号={}, 块内={}, 总位数={}".format(
    d['tag'], d['line'], d['offset'], d['total']))
print("  四路组相联: 标记={}, 组号={}, 块内={}, 总位数={}".format(
    s['tag'], s['set'], s['offset'], s['total']))
print("  全相联:     标记={}, 组号={}, 块内={}, 总位数={}".format(
    f['tag'], f['set'], f['offset'], f['total']))
print()

print("RULE_CHECK（场景规则验证）:")

# 规则1: 参数为 2 的幂
r1 = (r['M'] & (r['M']-1) == 0) and (r['C'] & (r['C']-1) == 0) and (r['B'] & (r['B']-1) == 0)
print(f"  [规则1] 参数为2的幂: {r1}")

# 规则2: 容量层级约束 M > C > B, 且 C/B >= 4
r2 = (r['M'] > r['C'] > r['B']) and (r['C'] // r['B'] >= 4)
print(f"  [规则2] M>C>B 且 C/B>=4: {r2}  (C/B = {r['C']//r['B']})")

# 规则3: 地址位数守恒
r3a = (d['tag'] + d['line'] + d['offset'] == r['addr_bits'])
r3b = (s['tag'] + s['set'] + s['offset'] == r['addr_bits'])
r3c = (f['tag'] + f['offset'] == r['addr_bits'])
print(f"  [规则3a] 直接映射 守恒 {d['tag']}+{d['line']}+{d['offset']}={d['tag']+d['line']+d['offset']}=={r['addr_bits']}: {r3a}")
print(f"  [规则3b] 组相联   守恒 {s['tag']}+{s['set']}+{s['offset']}={s['tag']+s['set']+s['offset']}=={r['addr_bits']}: {r3b}")
print(f"  [规则3c] 全相联   守恒 {f['tag']}+{f['offset']}={f['tag']+f['offset']}=={r['addr_bits']}: {r3c}")

# 规则4: 字段位数非负且 >=1（全相联索引除外）
r4 = all(x >= 1 for x in [d['tag'], d['line'], d['offset'],
                           s['tag'], s['set'], s['offset'],
                           f['tag'], f['offset']])
print(f"  [规则4] 各字段位数>=1: {r4}")

# 规则5: 块内地址位数范围 [4,8]
r5 = 4 <= r['block_offset'] <= 8
print(f"  [规则5] 块内地址位数 log2(B)={r['block_offset']} ∈[4,8]: {r5}")

# 规则6: 标记位 >= 4
r6 = all(x >= 4 for x in [d['tag'], s['tag'], f['tag']])
print(f"  [规则6] 标记位>=4: {r6}  (dm={d['tag']}, sa={s['tag']}, fa={f['tag']})")

all_pass = all([r1, r2, r3a, r3b, r3c, r4, r5, r6])
print(f"\n  全部规则通过: {all_pass}")

# ============ assert 场景规则 ============
assert r1, "规则1失败: 参数非2的幂"
assert r2, "规则2失败: 容量层级约束不满足"
assert r3a, "规则3a失败: 直接映射地址位数不守恒"
assert r3b, "规则3b失败: 四路组相联地址位数不守恒"
assert r3c, "规则3c失败: 全相联地址位数不守恒"
assert r4, "规则4失败: 字段位数应>=1"
assert r5, "规则5失败: 块内地址位数不在[4,8]"
assert r6, "规则6失败: 标记位应>=4"
