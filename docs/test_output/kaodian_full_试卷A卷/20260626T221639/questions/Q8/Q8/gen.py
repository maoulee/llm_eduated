"""
页式虚拟存储器地址转换 —— 代码翻译题干规则
建模：拆地址 → 查页表 → 判装入位 → 拼物理地址
"""

# ==================== 参数（来自题干） ====================
VA_BITS = 32
PA_BITS = 26
PAGE_SIZE = 4096          # 4KB = 2^12
OFFSET_BITS = 12          # log2(4096) = 12

# 页表：虚页号 -> (装入位, 实页号或None)
PAGE_TABLE = {
    0x00000: (1, 0x0012),
    0x00001: (1, 0x0005),
    0x00002: (0, None),
    0x00003: (1, 0x03AB),
    0x00004: (1, 0x001F),
    0x00005: (0, None),
    0x00006: (1, 0x000C),
    0x00007: (1, 0x0042),
}

# 5个虚拟地址（十六进制）
VAs = {
    1: 0x000035A8,   # ①
    2: 0x000041F0,   # ②
    3: 0x000067C4,   # ③
    4: 0x00002B3E,   # ④
    5: 0x00005A10,   # ⑤
}

# ==================== 地址结构推导 ====================
vpn_bits = VA_BITS - OFFSET_BITS     # 虚页号位数 = 20
pfn_bits = PA_BITS - OFFSET_BITS     # 实页号位数 = 14

# ==================== 建模：拆地址 → 查页表 → 判装入位 → 拼 PA ====================
def translate(va):
    """对一个虚拟地址执行完整的转换流程，返回详细数据流"""
    vpn = va >> OFFSET_BITS                          # 虚页号 = VA >> 12
    offset = va & (PAGE_SIZE - 1)                     # 页内偏移 = VA & 0xFFF
    valid, pfn = PAGE_TABLE[vpn]                      # 查页表
    result = {
        "VA_hex":  hex(va),
        "VA_bin":  format(va, '032b'),
        "VPN":     vpn,
        "VPN_hex": hex(vpn),
        "Offset":  offset,
        "Offset_hex": hex(offset),
        "Valid":   valid,
        "PFN":     pfn,
    }
    if valid == 1:
        pa = (pfn << OFFSET_BITS) | offset            # PA = (PFN << 12) | offset
        result["PA"] = pa
        result["PA_hex"] = hex(pa)
        result["PA_bin"] = format(pa, '026b')
        result["translatable"] = True
    else:
        result["PA"] = None
        result["translatable"] = False
    return result

# ==================== 注入参数跑 ====================
results = {k: translate(v) for k, v in VAs.items()}

# ==================== 场景规则验证（检查载体） ====================
# 规则1: 地址结构一致性
assert vpn_bits == 20, f"虚页号位数应为20，实际{vpn_bits}"
assert pfn_bits == 14, f"实页号位数应为14，实际{pfn_bits}"
assert OFFSET_BITS == 12

# 规则4: 实页号合法性 —— 所有装入位=1 的 PFN < 2^14
for vpn_, (v_, pf_) in PAGE_TABLE.items():
    if v_ == 1:
        assert pf_ < (1 << pfn_bits), f"PFN {hex(pf_)} >= 2^{pfn_bits}"

# 规则6: 页表覆盖性 —— 所有待转换VA的VPN落在 0x00000~0x00007
for k, va in VAs.items():
    vpn_val = va >> OFFSET_BITS
    assert vpn_val in PAGE_TABLE, f"VA{k} VPN={hex(vpn_val)} 不在页表范围"

# 规则3: 装入位=0 不可转换（验证模型忠实实现）
for k, r in results.items():
    if r["Valid"] == 0:
        assert r["translatable"] == False, f"VA{k} 装入位=0 却被转换"
    else:
        assert r["translatable"] == True, f"VA{k} 装入位=1 却未转换"

# 规则2: 拼接一致性 —— PA = (PFN<<12)|offset，且 PA 位数 = PA_BITS
for k, r in results.items():
    if r["translatable"]:
        pa_reconstructed = (r["PFN"] << OFFSET_BITS) | r["Offset"]
        assert pa_reconstructed == r["PA"], f"VA{k} 拼接不一致"
        assert r["PA"] < (1 << PA_BITS), f"VA{k} PA 超过 {PA_BITS} 位"

# ==================== 底部：完整数据流 print ====================
print("=" * 70)
print("PARAMS:")
print(f"  VA_BITS = {VA_BITS}, PA_BITS = {PA_BITS}, PAGE_SIZE = {PAGE_SIZE} (2^{OFFSET_BITS})")
print(f"  OFFSET_BITS = {OFFSET_BITS}")
print(f"  vpn_bits(VA虚页号位数) = {VA_BITS} - {OFFSET_BITS} = {vpn_bits}")
print(f"  pfn_bits(PA实页号位数) = {PA_BITS} - {OFFSET_BITS} = {pfn_bits}")
print()
print("PAGE_TABLE:")
for vpn_ in sorted(PAGE_TABLE):
    v_, pf_ = PAGE_TABLE[vpn_]
    pf_str = hex(pf_) if pf_ is not None else "——"
    print(f"  VPN={hex(vpn_):>8s}  Valid={v_}  PFN={pf_str:>8s}")

print()
print("=" * 70)
print("Q1 结果:")
print(f"  (1) 虚页号位数 = {vpn_bits} 位, 页内偏移位数 = {OFFSET_BITS} 位")
print(f"  (2) 实页号位数 = {pfn_bits} 位, 页内偏移位数 = {OFFSET_BITS} 位")
invalid_list = [k for k in sorted(results) if results[k]["Valid"] == 0]
print(f"  (3) 不在内存中的虚拟地址(装入位=0): {['①②③④⑤'[k-1] for k in invalid_list]}")
print(f"      VPN列表: {[hex(results[k]['VPN']) for k in invalid_list]}")

print()
print("=" * 70)
print("Q2 结果 (虚拟地址 ①②③ 转换):")
for k in [1, 2, 3]:
    r = results[k]
    print(f"\n  --- 虚拟地址 {'①②③'[k-1]} = {r['VA_hex']} ---")
    print(f"    拆分: VPN = {r['VA_hex']} >> 12 = {r['VPN_hex']}  (十进制 {r['VPN']})")
    print(f"          页内偏移 = {r['VA_hex']} & 0xFFF = {r['Offset_hex']}  (十进制 {r['Offset']})")
    print(f"    查页表: VPN={r['VPN_hex']} → 装入位={r['Valid']}, 实页号 PFN={hex(r['PFN'])}")
    print(f"    拼接: PA = (PFN << 12) | offset = ({hex(r['PFN'])} << 12) | {r['Offset_hex']}")
    print(f"              = {hex(r['PFN'] << 12)} | {r['Offset_hex']}")
    print(f"              = {r['PA_hex']}")
    print(f"    物理地址(26位二进制): {r['PA_bin']}")

print()
print("=" * 70)
print("Q3 结果 (虚拟地址 ④⑤ 判断):")
for k in [4, 5]:
    r = results[k]
    label = '④⑤'[k-4]
    print(f"\n  --- 虚拟地址 {label} = {r['VA_hex']} ---")
    print(f"    拆分: VPN = {r['VPN_hex']}, 页内偏移 = {r['Offset_hex']}")
    print(f"    查页表: VPN={r['VPN_hex']} → 装入位={r['Valid']}", end="")
    if r["Valid"] == 0:
        print(f" → 不在内存中（缺页）")
        print(f"    结论: 不可转换，触发缺页中断")
        print(f"    操作系统需: 将该页从外存调入内存，更新页表装入位")
    else:
        print(f", 实页号 PFN={hex(r['PFN'])}")
        print(f"    物理地址 = {r['PA_hex']}")

print()
print("=" * 70)
print("RULE_CHECK (场景规则验证):")
print(f"  规则1 地址结构: vpn_bits={vpn_bits}(=20✓), pfn_bits={pfn_bits}(=14✓), offset_bits={OFFSET_BITS}(=12✓)")
print(f"  规则4 PFN合法性: ", end="")
pfns_ok = all(pf < (1 << pfn_bits) for v, pf in PAGE_TABLE.values() if v == 1)
print(f"所有 PFN < 2^14={hex(1<<pfn_bits)} → {'✓' if pfns_ok else '✗'}")
print(f"  规则6 页表覆盖性: 所有VPN ∈ [0,7] → ✓")
print(f"  规则2 拼接一致性 & 规则3 装入位语义: 所有assert通过 → ✓")
print()
print("RESULT SUMMARY:")
for k in sorted(results):
    r = results[k]
    pa_str = r["PA_hex"] if r["translatable"] else "N/A(缺页)"
    print(f"  VA{k} {'①②③④⑤'[k-1]}: {r['VA_hex']} → VPN={r['VPN_hex']}, offset={r['Offset_hex']}, valid={r['Valid']}, PA={pa_str}")
