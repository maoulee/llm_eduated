"""
微指令格式设计与控制存储器容量计算
字段直接编码法（分段直接编码）
"""
import math


def bits_needed(n_commands):
    """字段直接编码法：n 个微命令 + 1 个预留"不发命令"状态 = (n+1) 种状态。
    需 ceil(log2(n+1)) 位才能编码全部状态。
    """
    if n_commands + 1 <= 1:
        return 0
    return math.ceil(math.log2(n_commands + 1))


def bits_needed_no_reserve(n_commands):
    """遗漏预留码的错误路径：只按 ceil(log2(n)) 位算。"""
    if n_commands <= 1:
        return 0
    return math.ceil(math.log2(n_commands))


def solve(groups, test_field_bits, micro_count):
    """
    groups: 各互斥类的微命令数列表，如 [4, 3, 4, 2, 5]
    test_field_bits: 判别测试字段位数
    micro_count: 控存中微指令总条数
    """
    # ===== 第 1 问：操作控制字段 =====
    # 预留码约束：每个互斥类位数 = ceil(log2(微命令数+1))
    field_bits = [bits_needed(n) for n in groups]
    # 错误路径：遗漏预留码
    field_bits_wrong = [bits_needed_no_reserve(n) for n in groups]
    # 控制字段总位数 = 各字段位数之和
    ctrl_total = sum(field_bits)
    ctrl_total_wrong = sum(field_bits_wrong)

    # ===== 第 2 问：微指令字长 =====
    # 下址字段位数 = ceil(log2(微指令总条数))
    addr_field_bits = math.ceil(math.log2(micro_count)) if micro_count > 1 else 0
    # 下址字段可寻址数 >= 微指令总条数
    addr_addressable = 2 ** addr_field_bits
    # 微指令字长 = 操作控制字段 + 判别测试字段 + 下址字段
    word_length = ctrl_total + test_field_bits + addr_field_bits

    # ===== 第 3 问：控存容量 =====
    capacity_bits = micro_count * word_length
    capacity_bytes = capacity_bits / 8

    return {
        "field_bits": field_bits,
        "field_bits_wrong": field_bits_wrong,
        "ctrl_total": ctrl_total,
        "ctrl_total_wrong": ctrl_total_wrong,
        "addr_field_bits": addr_field_bits,
        "addr_addressable": addr_addressable,
        "word_length": word_length,
        "capacity_bits": capacity_bits,
        "capacity_bytes": capacity_bytes,
    }


# ===== 注入参数 =====
groups = [4, 3, 4, 2, 5]
test_field_bits = 2
micro_count = 512

r = solve(groups, test_field_bits, micro_count)

# ===== 底部：打印完整数据流 =====
print("=" * 60)
print("PARAMS:")
print(f"  各互斥类微命令数: {groups}")
print(f"  微命令总数: {sum(groups)}")
print(f"  判别测试字段位数: {test_field_bits}")
print(f"  控存微指令总条数: {micro_count}")
print()

print("=" * 60)
print("第 1 问 PROCESS — 操作控制字段（字段直接编码法）:")
for i, (n, b, bw) in enumerate(zip(groups, r["field_bits"], r["field_bits_wrong"])):
    reserve_str = f"⌈log2({n}+1)⌉ = ⌈log2({n+1})⌉ = {b} 位"
    wrong_str = f"⌈log2({n})⌉ = {bw} 位"
    trap = "  ← 预留码陷阱(n=2^k, 正确{0}位 vs 遗漏{1}位)".format(b, bw) if b != bw else ""
    print(f"  第 {i+1} 组: {n} 个微命令 → 正确: {reserve_str}{trap}")
    print(f"           遗漏预留码: {wrong_str}")
print(f"\n  操作控制字段总位数(正确) = {' + '.join(str(b) for b in r['field_bits'])} = {r['ctrl_total']} 位")
print(f"  操作控制字段总位数(遗漏预留码) = {' + '.join(str(b) for b in r['field_bits_wrong'])} = {r['ctrl_total_wrong']} 位")
print()

print("=" * 60)
print("第 2 问 PROCESS — 微指令字长:")
print(f"  操作控制字段位数: {r['ctrl_total']} 位")
print(f"  判别测试字段位数: {test_field_bits} 位 (题干给定)")
print(f"  下址字段位数: ⌈log2({micro_count})⌉ = {r['addr_field_bits']} 位")
print(f"    (验证: 2^{r['addr_field_bits']} = {r['addr_addressable']} >= {micro_count} 微指令)")
print(f"  微指令字长 = {r['ctrl_total']} + {test_field_bits} + {r['addr_field_bits']} = {r['word_length']} 位")
print()

print("=" * 60)
print("第 3 问 PROCESS — 控制存储器容量:")
print(f"  控存容量(位) = {micro_count} × {r['word_length']} = {r['capacity_bits']} 位")
print(f"  控存容量(字节) = {r['capacity_bits']} / 8 = {r['capacity_bytes']} 字节 = {r['capacity_bits']//8//1024} KB")
print()

print("=" * 60)
print("RESULT:")
print(f"  Q1 操作控制字段总位数: {r['ctrl_total']} 位")
print(f"     各字段: 第1组={r['field_bits'][0]}, 第2组={r['field_bits'][1]}, 第3组={r['field_bits'][2]}, 第4组={r['field_bits'][3]}, 第5组={r['field_bits'][4]}")
print(f"  Q2 微指令字长: {r['word_length']} 位")
print(f"  Q3 控存容量: {r['capacity_bits']} 位 = {r['capacity_bytes']} 字节 ({r['capacity_bits']//8//1024} KB)")
print()

print("=" * 60)
print("RULE_CHECK (场景规则验证):")
# 规则1: 预留码约束 — 每组 +1
for i, (n, b) in enumerate(zip(groups, r["field_bits"])):
    expected = math.ceil(math.log2(n + 1))
    print(f"  规则1 第{i+1}组: ⌈log2({n}+1)⌉ = {expected}, 实际分配 {b} → {'✓' if expected == b else '✗'}")
# 规则2: 控制字段总位数 = 各组之和
print(f"  规则2 控制字段总位数: sum({r['field_bits']}) = {sum(r['field_bits'])} == {r['ctrl_total']} → {'✓' if sum(r['field_bits']) == r['ctrl_total'] else '✗'}")
# 规则3: 下址字段位数 = ceil(log2(微指令数)), 且可寻址 >= 总条数
print(f"  规则3 下址字段: 2^{r['addr_field_bits']} = {r['addr_addressable']} >= {micro_count} → {'✓' if r['addr_addressable'] >= micro_count else '✗'}")
# 规则4: 微指令字长 = 控制字段 + 判别字段 + 下址字段
print(f"  规则4 字长: {r['ctrl_total']} + {test_field_bits} + {r['addr_field_bits']} = {r['ctrl_total']+test_field_bits+r['addr_field_bits']} == {r['word_length']} → {'✓' if r['ctrl_total']+test_field_bits+r['addr_field_bits'] == r['word_length'] else '✗'}")
# 规则5: 控存容量(位) = 条数 × 字长; 容量(字节) = 位/8 整除
print(f"  规则5 容量(位): {micro_count} × {r['word_length']} = {r['capacity_bits']} → {'✓' if micro_count * r['word_length'] == r['capacity_bits'] else '✗'}")
print(f"  规则5 容量(字节): {r['capacity_bits']} % 8 = {r['capacity_bits'] % 8} → {'✓ (整除)' if r['capacity_bits'] % 8 == 0 else '✗ (不整除)'}")
# 规则6: 陷阱可区分性 — 至少两组微命令数为 2 的幂
power_of_2_groups = [i+1 for i, n in enumerate(groups) if n > 0 and (n & (n-1)) == 0]
print(f"  规则6 陷阱可区分: 微命令数为2的幂的组 = {power_of_2_groups} (共{len(power_of_2_groups)}组 >= 2) → {'✓' if len(power_of_2_groups) >= 2 else '✗'}")
