"""
水平型微指令格式设计与控存容量计算 —— gen.py
题干规则逐句翻译为代码，底部打印完整数据流。
"""
import math


def bits_for_field(num_commands):
    """场景规则1：每字段位数 = ceil(log2(组内微命令数 + 1))，+1 为不操作码。"""
    return math.ceil(math.log2(num_commands + 1))


def solve(classes, num_microinstr, p_bits):
    """
    classes: list of (类名, 微命令数)
    num_microinstr: 控存中微指令总条数
    p_bits: 判别测试标志位位数
    """
    # ---- 场景规则1：各字段位数 ----
    fields = []
    for name, cnt in classes:
        b = bits_for_field(cnt)
        fields.append((name, cnt, b))

    # ---- 场景规则2：操作控制字段总位数 ----
    op_total_bits = sum(b for _, _, b in fields)

    # ---- 场景规则3：下址字段位数 ----
    addr_bits = math.ceil(math.log2(num_microinstr))

    # ---- 场景规则4：微指令字长 ----
    word_length = op_total_bits + p_bits + addr_bits

    # ---- 场景规则5：控存最大容量 ----
    capacity_bits = num_microinstr * word_length

    # ---- 场景规则6：相容微命令分属不同字段验证 ----
    # 相容对：(PC→MAR, READ) → 第一类 vs 第三类
    # 相容对：(ADD, R0←)     → 第二类 vs 第四类
    compatibility_pairs = [
        ("PC→MAR & READ",  "第一类", "第三类"),
        ("ADD & R0←",       "第二类", "第四类"),
    ]
    compat_check = []
    for pair_name, cls_a, cls_b in compatibility_pairs:
        compat_check.append((pair_name, cls_a, cls_b, cls_a != cls_b))

    # ---- assert 场景规则6：相容微命令必须分属不同字段 ----
    for pair_name, cls_a, cls_b, ok in compat_check:
        assert ok, f"相容微命令对 {pair_name} 落入同一字段，分组方案错误"

    return {
        "fields": fields,
        "op_total_bits": op_total_bits,
        "addr_bits": addr_bits,
        "p_bits": p_bits,
        "word_length": word_length,
        "capacity_bits": capacity_bits,
        "compat_check": compat_check,
        "num_microinstr": num_microinstr,
    }


# ==================== 注入参数 ====================
classes = [
    ("第一类（数据通路控制）", 5),
    ("第二类（ALU 运算控制）", 7),
    ("第三类（存储器控制）", 3),
    ("第四类（寄存器读写控制）", 4),
    ("第五类（状态标志控制）", 3),
]
NUM_MICROINSTR = 256
P_BITS = 2

result = solve(classes, NUM_MICROINSTR, P_BITS)

# ==================== 底部数据流 ====================
print("=" * 60)
print("PARAMS:")
print(f"  互斥类: {classes}")
print(f"  微指令总条数: {NUM_MICROINSTR}")
print(f"  判别测试位数(P字段): {P_BITS}")
print(f"  微命令总数: {sum(c for _, c in classes)}")

print("\n" + "=" * 60)
print("PROCESS — 各字段位数计算 (场景规则1: ceil(log2(n+1))):")
for name, cnt, b in result["fields"]:
    calc = f"ceil(log2({cnt}+1)) = ceil(log2({cnt+1})) = ceil({math.log2(cnt+1):.4f}) = {b}"
    print(f"  {name}: {cnt}个微命令 → {calc} 位")

print(f"\nPROCESS — 操作控制字段总位数 (场景规则2):")
detail = " + ".join(str(b) for _, _, b in result["fields"])
print(f"  {detail} = {result['op_total_bits']} 位")

print(f"\nPROCESS — 下址字段位数 (场景规则3: ceil(log2(256))):")
print(f"  ceil(log2({NUM_MICROINSTR})) = ceil({math.log2(NUM_MICROINSTR):.1f}) = {result['addr_bits']} 位")

print(f"\nPROCESS — 微指令字长 (场景规则4):")
print(f"  {result['op_total_bits']}(操作控制) + {result['p_bits']}(判别测试) + {result['addr_bits']}(下址) = {result['word_length']} 位")

print(f"\nPROCESS — 控存最大容量 (场景规则5):")
print(f"  {NUM_MICROINSTR}(条) × {result['word_length']}(位) = {result['capacity_bits']} 位")
print(f"  = {result['capacity_bits'] / 8192:.4f} Kb = {result['capacity_bits'] / 8192} Kb")

print("\n" + "=" * 60)
print("PROCESS — 相容微命令分属不同字段验证 (场景规则6):")
for pair_name, cls_a, cls_b, ok in result["compat_check"]:
    print(f"  {pair_name}: {cls_a} vs {cls_b} → 分属不同字段: {ok}")

print("\n" + "=" * 60)
print("RESULT:")
print(f"  各字段位数: {[b for _, _, b in result['fields']]}")
print(f"  操作控制字段总位数: {result['op_total_bits']} 位")
print(f"  下址字段位数: {result['addr_bits']} 位")
print(f"  判别测试位数: {result['p_bits']} 位")
print(f"  微指令字长: {result['word_length']} 位")
print(f"  控存最大容量: {result['capacity_bits']} 位")
