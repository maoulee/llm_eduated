# -*- coding: utf-8 -*-
"""
存储器字位同时扩展 —— 计算题建模码
题干: 用 8K×4位 RAM 芯片扩展构成 64KB、字长16位 的主存储器模块。
"""
import math

# ============ PARAMS ============
PARAMS = {
    "C_target_byte": 64 * 1024,   # 目标总容量 = 64KB = 65536 B
    "W_target": 16,                # 目标存储字长 = 16 位
    "N_chip": 8 * 1024,            # 芯片地址单元数 = 8K = 8192
    "W_chip": 4,                   # 芯片位宽 = 4 位
}

def solve(p):
    # --- 第1问: 地址线 & 数据线 ---
    # 地址线根数: 按字节编址, log2(总字节数)
    addr_bits = math.ceil(math.log2(p["C_target_byte"]))
    # 数据线根数: = 存储字长
    data_bits = p["W_target"]

    # --- 第2问: 字/位扩展 & 总芯片数 ---
    word_expand  = p["C_target_byte"] // p["N_chip"]    # 字扩展倍数 = 64KB/8K = 8
    bit_expand   = p["W_target"] // p["W_chip"]          # 位扩展倍数 = 16/4 = 4
    total_chips  = word_expand * bit_expand               # 总芯片数 = 8×4 = 32

    # 陷阱答案: 字扩展+位扩展（常见错误）
    trap_add = word_expand + bit_expand                   # 8+4 = 12

    return {
        "addr_bits": addr_bits,
        "data_bits": data_bits,
        "word_expand": word_expand,
        "bit_expand": bit_expand,
        "total_chips": total_chips,
        "trap_add": trap_add,
    }

# ============ 运行 ============
r = solve(PARAMS)

print("=" * 55)
print("PARAMS")
print("=" * 55)
print(f"  目标总容量 C_target = {PARAMS['C_target_byte']} B = {PARAMS['C_target_byte']//1024}KB")
print(f"  目标存储字长 W_target = {PARAMS['W_target']} 位")
print(f"  芯片规格 = {PARAMS['N_chip']//1024}K × {PARAMS['W_chip']}位")
print(f"    (N_chip = {PARAMS['N_chip']}, W_chip = {PARAMS['W_chip']})")

print()
print("=" * 55)
print("REASONING")
print("=" * 55)

# --- 第1问 ---
print("\n【第1问】地址线根数 与 数据线根数")
print(f"  按字节编址, 总字节数 = {PARAMS['C_target_byte']} = 2^{int(math.log2(PARAMS['C_target_byte']))}")
print(f"  地址线根数 = ⌈log2({PARAMS['C_target_byte']})⌉ = {int(math.log2(PARAMS['C_target_byte']))} = {r['addr_bits']}")
print(f"  数据线根数 = 存储字长 = {r['data_bits']}")

# --- 第2问 ---
print("\n【第2问】字/位扩展倍数 与 总芯片数")
print(f"  字扩展倍数 = C_target / N_chip = {PARAMS['C_target_byte']} / {PARAMS['N_chip']} = {r['word_expand']}")
print(f"  位扩展倍数 = W_target / W_chip = {PARAMS['W_target']} / {PARAMS['W_chip']} = {r['bit_expand']}")
print(f"  总芯片数 = 字扩展 × 位扩展 = {r['word_expand']} × {r['bit_expand']} = {r['total_chips']}")

print()
print("=" * 55)
print("ANSWER")
print("=" * 55)
print(f"  第1问: 地址线 {r['addr_bits']} 根, 数据线 {r['data_bits']} 根")
print(f"  第2问: 字扩展 {r['word_expand']} 倍, 位扩展 {r['bit_expand']} 倍, 总芯片数 {r['total_chips']} 片")
print(f"  [陷阱] 字扩展+位扩展 = {r['trap_add']}（相加错误, 非正确答案）")

# ============ ASSERT: 通过条件 ============
# 1. 地址线=16, 数据线=16
assert r["addr_bits"] == 16, f"地址线根数应为16, 实际 {r['addr_bits']}"
assert r["data_bits"] == 16, f"数据线根数应为16, 实际 {r['data_bits']}"

# 2. 字扩展倍数 ≥ 2
assert r["word_expand"] >= 2, f"字扩展倍数应≥2, 实际 {r['word_expand']}"

# 3. 位扩展倍数 ≥ 2
assert r["bit_expand"] >= 2, f"位扩展倍数应≥2, 实际 {r['bit_expand']}"

# 4. 总芯片数 = 字扩展 × 位扩展（乘积关系, 非相加）
assert r["total_chips"] == r["word_expand"] * r["bit_expand"], "总芯片数应=字扩展×位扩展"
assert r["total_chips"] == 32, f"总芯片数应为32, 实际 {r['total_chips']}"

# 5. 地址线由总容量决定, 数据线由字长决定（独立）
assert r["addr_bits"] == math.ceil(math.log2(PARAMS["C_target_byte"])), "地址线由总容量决定"
assert r["data_bits"] == PARAMS["W_target"], "数据线由字长决定"
assert r["addr_bits"] != math.ceil(math.log2(PARAMS["N_chip"])), "地址线≠log2(芯片单元数)"

# 6. 陷阱检测: 相加(12) ≠ 正确答案(32)
assert r["trap_add"] != r["total_chips"], "相加陷阱值必须与正确答案不同"
assert r["trap_add"] == 12, f"陷阱答案应为12, 实际 {r['trap_add']}"

print("\n>>> 全部 assert 通过, 通过条件已满足。")
