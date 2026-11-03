"""
页式虚拟存储器地址转换 — gen.py
把题干的地址转换规则翻译成代码，参数注入，exec 验证通过条件。
"""

# ============================================================
# PARAMS（题干系统参数）
# ============================================================
VA_BITS = 32          # 虚拟地址位数
PA_BITS = 20          # 物理地址位数
PAGE_OFFSET_BITS = 12 # 页内偏移位数（4KB = 2^12）

# 页表：虚页号(十六进制) -> (实页号(十六进制), 装入位)
PAGE_TABLE = {
    "0000A": ("2F", 1),
    "0001B": ("4C", 1),
    "0003F": ("1A", 1),
    "00052": ("00", 1),
    "00078": ("9D", 0),
    "0009C": ("B3", 1),
    "000B5": ("71", 1),
    "000C0": ("3E", 0),
}

# 待转换的虚拟地址（十六进制，8 位 = 32 位）
ADDRESSES = ["0001B3F4", "0009C6E8", "00078ABC"]


# ============================================================
# 第 1 问：地址结构计算
# ============================================================
def addr_structure():
    vpn_bits = VA_BITS - PAGE_OFFSET_BITS        # 虚页号位数
    v_offset = PAGE_OFFSET_BITS                   # 虚拟地址页内偏移位数
    pfn_bits = PA_BITS - PAGE_OFFSET_BITS         # 实页号位数
    p_offset = PAGE_OFFSET_BITS                   # 物理地址页内偏移位数
    va_space_gb = (2 ** VA_BITS) / (1024 ** 3)    # 虚拟地址空间 (GB)

    print("[PARAMS] === 地址结构 ===")
    print(f"[PARAMS] 虚页号位数 = {VA_BITS} - {PAGE_OFFSET_BITS} = {vpn_bits} 位")
    print(f"[PARAMS] 虚拟地址页内偏移 = {v_offset} 位")
    print(f"[PARAMS] 实页号位数 = {PA_BITS} - {PAGE_OFFSET_BITS} = {pfn_bits} 位")
    print(f"[PARAMS] 物理地址页内偏移 = {p_offset} 位")
    print(f"[PARAMS] 虚拟地址空间 = 2^{VA_BITS} B = {2**VA_BITS} B = {va_space_gb} GB")

    return {
        "vpn_bits": vpn_bits,
        "v_offset": v_offset,
        "pfn_bits": pfn_bits,
        "p_offset": p_offset,
        "va_space_gb": va_space_gb,
    }


# ============================================================
# 第 2 问：虚拟地址 -> 物理地址转换
# ============================================================
def translate(va_hex):
    """
    翻译题干规则：
    1. 拆分：高 VPN_BITS 位 = 虚页号，低 PAGE_OFFSET_BITS 位 = 页内偏移
    2. 查页表：取虚页号对应的实页号和装入位
    3. 装入位=1 -> 拼物理地址 = 实页号 << offset | 页内偏移
       装入位=0 -> 缺页中断，不给物理地址
    """
    va = int(va_hex, 16)
    offset_mask = (1 << PAGE_OFFSET_BITS) - 1       # 页内偏移掩码
    offset = va & offset_mask                        # 取低12位 = 页内偏移
    vpn = va >> PAGE_OFFSET_BITS                     # 取高20位 = 虚页号

    vpn_hex = format(vpn, "05X")                    # 虚页号（5位十六进制 = 20位）
    offset_hex = format(offset, "03X")              # 页内偏移（3位十六进制 = 12位）

    entry = PAGE_TABLE.get(vpn_hex)
    if entry is None:
        result = ("NOT_IN_TABLE", vpn_hex, offset_hex, None, None)
        return result

    pfn_hex, valid = entry
    pfn = int(pfn_hex, 16)                           # 实页号（整数值）

    if valid == 1:
        pa = (pfn << PAGE_OFFSET_BITS) | offset     # 拼物理地址
        pa_hex = format(pa, "05X")
        status = "HIT"
    else:
        pa = None
        pa_hex = None
        status = "PAGE_FAULT"

    return (status, vpn_hex, offset_hex, pfn_hex, pa_hex)


# ============================================================
# 主流程：输出 PARAMS / REASONING / ANSWER
# ============================================================
print("=" * 60)
struct = addr_structure()
print("=" * 60)

# ---- 第 2 问：逐地址转换 ----
print()
print("[REASONING] === 地址转换 ===")
results = []
for i, addr in enumerate(ADDRESSES, 1):
    status, vpn_h, off_h, pfn_h, pa_h = translate(addr)
    print(f"[REASONING] 地址{['①','②','③'][i-1]}: VA = 0x{addr}")
    print(f"[REASONING]   虚页号 = {addr[:5]} (= 0x{vpn_h})")
    print(f"[REASONING]   页内偏移 = {addr[5:]} (= 0x{off_h})")
    if status == "HIT":
        print(f"[REASONING]   查页表：虚页号 {vpn_h} -> 实页号 {pfn_h}, 装入位=1")
        print(f"[REASONING]   物理地址 = 实页号 {pfn_h} << 12 | 偏移 {off_h} = 0x{pa_h}")
    elif status == "PAGE_FAULT":
        print(f"[REASONING]   查页表：虚页号 {vpn_h} -> 装入位=0")
        print(f"[REASONING]   缺页中断！无法转换，不给出物理地址")
    results.append((status, vpn_h, off_h, pfn_h, pa_h))

# ---- ANSWER 汇总 ----
print()
print("[ANSWER] === 最终答案 ===")
print(f"[ANSWER] 第1问：")
print(f"[ANSWER]   虚页号 {struct['vpn_bits']} 位，页内偏移 {struct['v_offset']} 位")
print(f"[ANSWER]   实页号 {struct['pfn_bits']} 位，页内偏移 {struct['p_offset']} 位")
print(f"[ANSWER]   虚拟地址空间 = 2^{VA_BITS} B = {struct['va_space_gb']} GB")
print(f"[ANSWER] 第2问：")
for i, (status, vpn_h, off_h, pfn_h, pa_h) in enumerate(results, 1):
    label = ['①', '②', '③'][i-1]
    if status == "HIT":
        print(f"[ANSWER]   {label} 0x{ADDRESSES[i-1]} -> 物理地址 0x{pa_h}")
    else:
        print(f"[ANSWER]   {label} 0x{ADDRESSES[i-1]} -> 缺页中断（装入位=0）")

# ============================================================
# 通过条件 ASSERT（逐条翻译 question.md 的通过条件）
# ============================================================
print()
print("=" * 60)
print("=== 通过条件验证 ===")

# 条件1：地址结构正确
assert struct["vpn_bits"] == 20, f"虚页号应为20位，实际{struct['vpn_bits']}"
assert struct["v_offset"] == 12, f"虚拟地址页内偏移应为12位，实际{struct['v_offset']}"
assert struct["pfn_bits"] == 8, f"实页号应为8位，实际{struct['pfn_bits']}"
assert struct["p_offset"] == 12, f"物理地址页内偏移应为12位，实际{struct['p_offset']}"
assert struct["va_space_gb"] == 4.0, f"虚拟地址空间应为4GB，实际{struct['va_space_gb']}"
print("✓ 条件1: 地址结构正确（虚页号20位/偏移12位/实页号8位/偏移12位/4GB）")

# 条件2：地址① 0x0001B3F4 -> 虚页号 0x0001B, 偏移 0x3F4, 装入位=1, 物理地址=0x4C3F4
r1 = results[0]
assert r1[0] == "HIT", f"地址①应命中，实际{r1[0]}"
assert r1[1] == "0001B", f"地址①虚页号应为0001B，实际{r1[1]}"
assert r1[2] == "3F4", f"地址①偏移应为3F4，实际{r1[2]}"
assert r1[3] == "4C", f"地址①实页号应为4C，实际{r1[3]}"
assert r1[4] == "4C3F4", f"地址①物理地址应为4C3F4，实际{r1[4]}"
print("✓ 条件2: 地址① 转换成立 -> 0x4C3F4")

# 条件3：地址② 0x0009C6E8 -> 虚页号 0x0009C, 偏移 0x6E8, 装入位=1, 物理地址=0xB36E8
r2 = results[1]
assert r2[0] == "HIT", f"地址②应命中，实际{r2[0]}"
assert r2[1] == "0009C", f"地址②虚页号应为0009C，实际{r2[1]}"
assert r2[2] == "6E8", f"地址②偏移应为6E8，实际{r2[2]}"
assert r2[3] == "B3", f"地址②实页号应为B3，实际{r2[3]}"
assert r2[4] == "B36E8", f"地址②物理地址应为B36E8，实际{r2[4]}"
print("✓ 条件3: 地址② 转换成立 -> 0xB36E8")

# 条件4：地址③ 0x00078ABC -> 虚页号 0x00078, 装入位=0, 缺页中断，不给物理地址
r3 = results[2]
assert r3[0] == "PAGE_FAULT", f"地址③应缺页，实际{r3[0]}"
assert r3[1] == "00078", f"地址③虚页号应为00078，实际{r3[1]}"
assert r3[4] is None, f"地址③缺页不应给出物理地址，实际给了{r3[4]}"
print("✓ 条件4: 地址③ 命中缺页陷阱（装入位=0，无物理地址）")

# 条件5：实页号位数 < 虚页号位数（8 < 20）
assert struct["pfn_bits"] < struct["vpn_bits"], "实页号位数应小于虚页号位数"
print(f"✓ 条件5: 实页号位数({struct['pfn_bits']}) < 虚页号位数({struct['vpn_bits']})")

# 防呆：直接复制虚页号作为实页号会得到错误结果
# 地址①虚页号=0x0001B(27)，若直接复制，物理地址前缀=0001B ≠ 正确实页号4C
wrong_copy_1 = (int("0001B", 16) << 12) | int("3F4", 16)
assert wrong_copy_1 != int("4C3F4", 16), "防呆：直接复制虚页号应与正确结果不同"
print("✓ 防呆: 直接复制虚页号得到的结果 ≠ 正确物理地址")

print()
print("=== 全部通过条件验证通过 ===")
