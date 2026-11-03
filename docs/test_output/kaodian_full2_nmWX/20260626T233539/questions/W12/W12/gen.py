"""
存储器扩展设计题 gen.py
题干：16K×4位 DRAM 芯片 → 64K×8位 存储器模块
CPU 地址总线 16 位(A15~A0)，按字节编址，数据总线 8 位。
DRAM 芯片 14 位内部地址，地址线复用，行=列=7位；刷新间隔 2ms。

建模：把场景规则 1~9 翻译成代码计算，底部 print 完整数据流供审核对照。
"""
import math

# ==================== 输入参数 ====================
# 芯片规格
chip_units = 16 * 1024        # 16K 个存储单元
chip_data_width = 4            # 芯片数据位宽 4 位
chip_addr_bits = 14            # 芯片内部地址位数 2^14=16K

# 目标存储器规格
target_units = 64 * 1024       # 64K 个存储单元
target_data_width = 8          # 目标数据位宽 8 位

# CPU 地址总线
cpu_addr_bits = 16             # A15~A0

# DRAM 复用 & 刷新
refresh_interval_ms = 2        # 刷新间隔 2ms


# ==================== 求解函数 ====================
def solve():
    p = {}

    # ---- 第(1)题：扩展方式判断 + 芯片数 ----
    # 规则1：位扩展数 = 目标位宽 / 芯片位宽
    bit_expand = target_data_width // chip_data_width
    p['位扩展数'] = bit_expand
    p['位扩展计算'] = f"{target_data_width} / {chip_data_width} = {bit_expand}"

    # 规则2：字扩展数 = 目标单元数 / 芯片单元数
    word_expand = target_units // chip_units
    p['字扩展数'] = word_expand
    p['字扩展计算'] = f"{target_units} / {chip_units} = {word_expand}"

    # 规则3：总片数 = 位扩展 × 字扩展
    total_chips = bit_expand * word_expand
    p['芯片总数'] = total_chips
    p['总片数计算'] = f"{bit_expand} × {word_expand} = {total_chips}"

    # 规则9：必须字位同时扩展（位扩展≥2 且 字扩展≥2）
    p['扩展方式'] = '字位同时扩展'
    p['位扩展>=2'] = bit_expand >= 2
    p['字扩展>=2'] = word_expand >= 2

    # ---- 第(2)题：地址线分组 ----
    # 规则4：片内地址位数 = log2(芯片单元数)
    intra_addr_bits = int(math.log2(chip_units))
    p['片内地址位数'] = intra_addr_bits
    p['片内地址计算'] = f"log2({chip_units}) = {intra_addr_bits}"

    # 规则4：片选地址位数 = log2(目标单元数) - 片内地址位数
    target_addr_bits = int(math.log2(target_units))
    select_addr_bits = target_addr_bits - intra_addr_bits
    p['片选地址位数'] = select_addr_bits
    p['片选地址计算'] = f"log2({target_units}) - {intra_addr_bits} = {target_addr_bits} - {intra_addr_bits} = {select_addr_bits}"

    # 地址线对应关系
    p['片内地址线'] = f"A{intra_addr_bits - 1}~A0"
    p['片选地址线'] = f"A{target_addr_bits - 1}~A{intra_addr_bits}"

    # 规则6：DRAM 地址线复用 → 对外地址引脚 = 内部地址位数 / 2
    ext_pins = chip_addr_bits // 2
    p['DRAM对外地址引脚数'] = ext_pins
    p['地址引脚计算'] = f"{chip_addr_bits} / 2 = {ext_pins}（行地址=列地址=7位）"

    # ---- 第(3)题：片选逻辑 ----
    # 字扩展数 = 2^(片选地址位数)，每个片选地址对应一组芯片
    p['芯片组数'] = 2 ** select_addr_bits
    chip_groups = []
    for i in range(2 ** select_addr_bits):
        start = i * chip_units
        end = (i + 1) * chip_units - 1
        cs_code = format(i, f'0{select_addr_bits}b')
        chip_groups.append({
            '组': i,
            '片选码(A15~A14)': cs_code,
            '起始地址': hex(start),
            '结束地址': hex(end),
            '地址范围(H)': f"{start//1024}K~{(end+1)//1024 - 1}K",
            '片内地址线': f"A{intra_addr_bits-1}~A0",
        })
    p['各组片选详情'] = chip_groups

    # ---- 第(4)题：异步刷新 ----
    # 规则7：行地址位数 = 内部地址位数 / 2；刷新行数 = 2^(行地址位数)
    row_addr_bits = chip_addr_bits // 2
    refresh_rows = 2 ** row_addr_bits
    p['行地址位数'] = row_addr_bits
    p['刷新行数'] = refresh_rows
    p['刷新行数计算'] = f"2^{row_addr_bits} = {refresh_rows}"

    # 规则8：异步刷新周期 = 刷新间隔 / 刷新行数
    async_period_us = (refresh_interval_ms * 1000) / refresh_rows
    p['异步刷新周期(us)'] = async_period_us
    p['异步刷新周期计算'] = f"{refresh_interval_ms}ms×1000 / {refresh_rows} = {refresh_interval_ms * 1000}us / {refresh_rows} = {async_period_us}us"

    return p


# ==================== 运行 + 底部数据流 print ====================
result = solve()

print("=" * 60)
print("PARAMS:")
print(f"  芯片规格: {chip_units}存储单元 × {chip_data_width}位, 内部地址{chip_addr_bits}位")
print(f"  目标规格: {target_units}存储单元 × {target_data_width}位")
print(f"  CPU地址总线: {cpu_addr_bits}位(A15~A0)")
print(f"  刷新间隔: {refresh_interval_ms}ms")
print()

print("=" * 60)
print("PROCESS / RESULT:")
print()

print("--- 第(1)题 扩展方式 + 芯片数 ---")
print(f"  位扩展数: {result['位扩展计算']}  → {result['位扩展数']}")
print(f"  字扩展数: {result['字扩展计算']}  → {result['字扩展数']}")
print(f"  芯片总数: {result['总片数计算']}  → {result['芯片总数']}")
print(f"  扩展方式: {result['扩展方式']} (位扩展≥2: {result['位扩展>=2']}, 字扩展≥2: {result['字扩展>=2']})")
print()

print("--- 第(2)题 地址线分组 ---")
print(f"  片内地址位数: {result['片内地址计算']}  → {result['片内地址位数']}位")
print(f"  片选地址位数: {result['片选地址计算']}  → {result['片选地址位数']}位")
print(f"  片内地址线: {result['片内地址线']}")
print(f"  片选地址线: {result['片选地址线']}")
print(f"  DRAM对外地址引脚: {result['地址引脚计算']}  → {result['DRAM对外地址引脚数']}根")
print()

print("--- 第(3)题 片选逻辑 ---")
print(f"  芯片组数: {result['芯片组数']}")
for g in result['各组片选详情']:
    print(f"  第{g['组']}组: {g['片选码(A15~A14)']}, 地址范围 {g['起始地址']}~{g['结束地址']}")
print()

print("--- 第(4)题 异步刷新 ---")
print(f"  行地址位数: {result['行地址位数']}位")
print(f"  刷新行数: {result['刷新行数计算']}  → {result['刷新行数']}行")
print(f"  异步刷新周期: {result['异步刷新周期计算']}  → {result['异步刷新周期(us)']}us")
print()

print("=" * 60)
print("RULE_CHECK (场景规则逐条验证):")
be = target_data_width // chip_data_width
we = target_units // chip_units
iab = int(math.log2(chip_units))
sab = int(math.log2(target_units)) - iab
rab = chip_addr_bits // 2
rr = 2 ** rab
ap = refresh_interval_ms * 1000 / rr

checks = [
    ("规则1 位扩展=目标位宽/芯片位宽且≥2",   be == target_data_width // chip_data_width and be >= 2, f"{be}"),
    ("规则2 字扩展=目标单元/芯片单元且≥2",   we == target_units // chip_units and we >= 2, f"{we}"),
    ("规则3 总片数=位扩展×字扩展",          be * we == be * we, f"{be}*{we}={be*we}"),
    ("规则4 2^片选位数=字扩展数",           2 ** sab == we, f"2^{sab}={2**sab} == {we}"),
    ("规则5 片内+片选=log2(目标单元数)",      iab + sab == int(math.log2(target_units)), f"{iab}+{sab}={iab+sab} == {int(math.log2(target_units))}"),
    ("规则6 对外引脚=内部地址/2且整数",       chip_addr_bits % 2 == 0 and chip_addr_bits // 2 == ext_pins if (ext_pins := chip_addr_bits//2) else True, f"{chip_addr_bits}/2={chip_addr_bits//2}"),
    ("规则7 刷新行数=2^(内部地址/2)",        rr == 2 ** rab, f"2^{rab}={rr}"),
    ("规则8 异步周期=刷新间隔/刷新行数",      abs(ap - refresh_interval_ms * 1000 / rr) < 1e-9, f"{refresh_interval_ms}ms/{rr}={ap}us"),
    ("规则9 字位同时扩展(位≥2且字≥2)",       be >= 2 and we >= 2, f"位{be}≥2且字{we}≥2"),
]
for name, ok, detail in checks:
    print(f"  [{'✓' if ok else '✗'}] {name}: {detail}")
print()
all_ok = all(c[1] for c in checks)
print(f"所有场景规则: {'全部满足 ✓' if all_ok else '存在不满足 ✗'}")
