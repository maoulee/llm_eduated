# -*- coding: utf-8 -*-
"""
Cache 映射地址字段位数推导
建模：把 question.md 声明的场景规则（按字节编址→地址总位数=log2(M)，
各字段位数公式，字段求和守恒，区分度，Tag差异方向）翻译成代码。
"""

import math

def solve(M, C, B, W):
    """M=主存容量(字节), C=Cache容量(字节), B=块大小(字节), W=组相联路数"""
    # ---- 场景规则1：按字节编址 → 地址总位数 = log2(M) ----
    addr_bits = int(round(math.log2(M)))

    # ---- 场景规则2：块内偏移 = log2(B)（两种映射相同） ----
    offset_bits = int(round(math.log2(B)))

    # ---- 直接相联 ----
    # 场景规则3：行号位数 = log2(C/B)
    num_lines = C // B
    line_bits = int(round(math.log2(num_lines)))
    # 场景规则4：直接相联 Tag = 地址总位数 − 行号位数 − 块内偏移位数
    tag_direct = addr_bits - line_bits - offset_bits
    # 场景规则9（直接相联）：Tag + 行号 + 块内偏移 = 地址总位数
    sum_direct = tag_direct + line_bits + offset_bits

    # ---- 组相联 ----
    # 场景规则5：组号位数 = log2(C/(B*W))，要求 C/(B*W) >= 2
    num_sets = C // (B * W)
    set_bits = int(round(math.log2(num_sets)))
    # 场景规则6：组相联 Tag = 地址总位数 − 组号位数 − 块内偏移位数
    tag_set_assoc = addr_bits - set_bits - offset_bits
    # 场景规则9（组相联）：Tag + 组号 + 块内偏移 = 地址总位数
    sum_set_assoc = tag_set_assoc + set_bits + offset_bits

    # ---- 场景规则7：组号位数 < 行号位数（区分度） ----
    distinct_ok = set_bits < line_bits
    # ---- 场景规则8：组相联 Tag 位数 >= 直接相联 Tag 位数 ----
    tag_order_ok = tag_set_assoc >= tag_direct
    # ---- 场景规则5要求：组数 >= 2 ----
    sets_ge2 = num_sets >= 2

    return {
        "addr_bits": addr_bits,
        "offset_bits": offset_bits,
        # 直接相联
        "num_lines": num_lines,
        "line_bits": line_bits,
        "tag_direct": tag_direct,
        "sum_direct": sum_direct,
        # 组相联
        "num_sets": num_sets,
        "set_bits": set_bits,
        "tag_set_assoc": tag_set_assoc,
        "sum_set_assoc": sum_set_assoc,
        # 规则验证量
        "distinct_ok": distinct_ok,
        "tag_order_ok": tag_order_ok,
        "sets_ge2": sets_ge2,
        "tag_diff": tag_set_assoc - tag_direct,
    }


# ====== 注入题干参数 ======
M = 1 * 1024 * 1024   # 1 MB = 2^20 B
C = 32 * 1024          # 32 KB = 2^15 B
B = 64                 # 64 B = 2^6 B
W = 4                  # 4 路组相联

R = solve(M, C, B, W)

# ====== 通过条件断言（场景规则→assert，打到特征非恒真）======
# 规则1
assert R["addr_bits"] == 20, f"地址总位数应为log2(1MB)=20, got {R['addr_bits']}"
# 规则2
assert R["offset_bits"] == 6, f"块内偏移应为log2(64)=6, got {R['offset_bits']}"
# 规则5要求
assert R["sets_ge2"], "组数应>=2"
# 规则9 守恒（两种映射各自）
assert R["sum_direct"] == R["addr_bits"], "直接相联字段和!=地址总位数"
assert R["sum_set_assoc"] == R["addr_bits"], "组相联字段和!=地址总位数"
# 规则7 区分度
assert R["distinct_ok"], "组号位数应<行号位数"
# 规则8 Tag差异方向
assert R["tag_order_ok"], "组相联Tag应>=直接相联Tag"

# ====== 底部完整数据流 print ======
print("=" * 60)
print("PARAMS:")
print(f"  M (主存容量) = {M} B = 2^{int(math.log2(M))} B")
print(f"  C (Cache容量) = {C} B = 2^{int(math.log2(C))} B")
print(f"  B (块大小) = {B} B = 2^{int(math.log2(B))} B")
print(f"  W (组相联路数) = {W}")
print()
print("PROCESS:")
print(f"  地址总位数 = log2(M) = log2(2^{int(math.log2(M))}) = {R['addr_bits']}")
print()
print("  [第1问 直接相联]")
print(f"    块内偏移位数 = log2(B) = log2(2^{int(math.log2(B))}) = {R['offset_bits']}")
print(f"    Cache总行数 = C/B = {C}/{B} = {R['num_lines']}")
print(f"    行号位数 = log2({R['num_lines']}) = {R['line_bits']}")
print(f"    Tag位数 = {R['addr_bits']} - {R['line_bits']} - {R['offset_bits']} = {R['tag_direct']}")
print(f"    字段守恒: Tag({R['tag_direct']}) + 行号({R['line_bits']}) + 偏移({R['offset_bits']}) = {R['sum_direct']} == 地址总位数({R['addr_bits']})")
print()
print("  [第2问 4路组相联]")
print(f"    块内偏移位数 = log2(B) = {R['offset_bits']} （与第1问相同，块大小决定）")
print(f"    Cache总行数 = C/B = {R['num_lines']}")
print(f"    组数 = C/(B*W) = {C}/({B}*{W}) = {C}/{B*W} = {R['num_sets']}")
print(f"    组号位数 = log2({R['num_sets']}) = {R['set_bits']}")
print(f"    Tag位数 = {R['addr_bits']} - {R['set_bits']} - {R['offset_bits']} = {R['tag_set_assoc']}")
print(f"    字段守恒: Tag({R['tag_set_assoc']}) + 组号({R['set_bits']}) + 偏移({R['offset_bits']}) = {R['sum_set_assoc']} == 地址总位数({R['addr_bits']})")
print()
print("  [第3问 Tag位数比较]")
print(f"    直接相联 Tag = {R['tag_direct']} 位")
print(f"    组相联   Tag = {R['tag_set_assoc']} 位")
print(f"    差值 = {R['tag_set_assoc']} - {R['tag_direct']} = {R['tag_diff']} 位")
print(f"    行号位数({R['line_bits']}) - 组号位数({R['set_bits']}) = {R['line_bits'] - R['set_bits']} 位  （等于Tag差值）")
print()
print("RULE_CHECK (场景规则):")
print(f"  规则5 组数>=2: {R['num_sets']}>=2 => {R['sets_ge2']}")
print(f"  规则7 组号<行号: {R['set_bits']}<{R['line_bits']} => {R['distinct_ok']}")
tsa = R['tag_set_assoc']
tdr = R['tag_direct']
print(f"  规则8 组相联Tag({tsa})>=直接Tag({tdr}): => {R['tag_order_ok']}")
print(f"  规则9 守恒(直接): {R['sum_direct']}=={R['addr_bits']} => {R['sum_direct']==R['addr_bits']}")
print(f"  规则9 守恒(组相联): {R['sum_set_assoc']}=={R['addr_bits']} => {R['sum_set_assoc']==R['addr_bits']}")
print()
print("RESULT:")
print(f"  第1问: 块内偏移={R['offset_bits']}位, 行号={R['line_bits']}位, Tag={R['tag_direct']}位")
print(f"  第2问: 块内偏移={R['offset_bits']}位, 组号={R['set_bits']}位, Tag={R['tag_set_assoc']}位")
print(f"  第3问: Tag差值={R['tag_diff']}位（组相联Tag比直接相联Tag多{R['tag_diff']}位）")
print("=" * 60)
print("ALL ASSERTS PASSED ✓")
