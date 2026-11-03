"""
SRAM 存储芯片容量计算（选择题建模）
- 地址线 18 根，数据线 16 根
- A = 正确结果（2^18 × 16 bit → 单位换算到 KB）
- B = bit/Byte 混淆（差 8 倍）
- C = 忽略数据线位宽（漏乘 m=16）
- D = 幂次算错或单位换算因子错误（差 2 或 4 倍）
"""

# ==================== 参数 ====================
n = 18        # 地址线根数
m = 16        # 数据线位宽

# ==================== 正确推导（翻译题干规则）====================
# 规则1: 可寻址单元数 = 2^n
addressable_units = 2 ** n          # 2^18 = 262144

# 规则2: 存储容量(bit) = 2^n × m
capacity_bit = addressable_units * m   # 262144 × 16 = 4194304 bit

# 规则3: 1 Byte = 8 bit → 容量(Byte)
capacity_Byte = capacity_bit // 8      # 524288 Byte

# 规则4: 1 KB = 1024 Byte → 容量(KB)
capacity_KB = capacity_Byte / 1024.0   # 512 KB

# ==================== 各选项正确值 ====================
# A: 正确结果
A_correct = capacity_KB                # 512 KB

# B: bit/Byte 混淆 —— 将 bit 数直接当 Byte 数（bit 数 / 1024 当 KB，不除 8）
B_correct = capacity_bit / 1024.0      # 4194304 / 1024 = 4096 KB（未除以 8）

# C: 忽略数据线位宽 —— 仅 2^n，未乘 m
capacity_bit_C = addressable_units     # 漏乘 16，只有 2^18 bit
C_correct = capacity_bit_C / 8 / 1024.0  # = 262144/8/1024 = 32 KB

# D: 幂次算错 —— 将 2^18 算成 2^19（相邻幂次，差 2 倍）
wrong_n = n + 1                        # 19
addressable_units_D = 2 ** wrong_n     # 2^19 = 524288
capacity_bit_D = addressable_units_D * m  # 524288 × 16 = 8388608 bit
D_correct = capacity_bit_D / 8 / 1024.0   # = 1024 KB

# ==================== 选项值汇总 ====================
A = A_correct     # 512 KB  正确
B = B_correct     # 4096 KB  bit/Byte混淆（未除8）
C = C_correct     # 32 KB    忽略数据线位宽
D = D_correct     # 1024 KB  2^18算成2^19

# ==================== 场景规则验证 ====================
# 规则1: 容量定义一致性
rule1 = (capacity_bit == 2 ** n * m)

# 规则2: 单位换算正确性
one_KB_in_bit = 1024 * 8   # 8192 bit
rule2 = (one_KB_in_bit == 8192) and (capacity_KB == capacity_bit / 8192)

# 规则3: 四选项互异
options = {"A": A, "B": B, "C": C, "D": D}
distinct = len(set(options.values())) == 4

# 规则4: 正确值唯一 → A 是唯一正确答案
A_unique = all(A != x for k, x in options.items() if k != "A")

# 规则5: 干扰项 ≠ A 且互不相同
distractors = {"B": B, "C": C, "D": D}
distractor_rule = all(v != A for v in distractors.values()) and len(set(distractors.values())) == 3

# ==================== 底部数据流 ====================
print("=" * 60)
print("PARAMS:", {"n(地址线)": n, "m(数据线位宽)": m})
print("-" * 60)
print("PROCESS:")
print("  2^n =", addressable_units)
print("  capacity_bit = 2^n × m =", capacity_bit)
print("  capacity_Byte = capacity_bit / 8 =", capacity_Byte)
print("  capacity_KB = capacity_Byte / 1024 =", capacity_KB)
print("  one_KB_in_bit = 1024 × 8 =", one_KB_in_bit)
print("  capacity_KB_via_bit_div_8192 = capacity_bit / 8192 =", capacity_bit / 8192)
print()
print("  B错误路径: capacity_bit 直接 / 1024 =", B_correct, "（未除以8，bit当Byte）")
print("  C错误路径: 2^n bit =", capacity_bit_C, "→ /8/1024 =", C_correct, "（漏乘m）")
print("  D错误路径: 2^%d = %s × %d = %d bit → /8/1024 = %s" % (wrong_n, addressable_units_D, m, capacity_bit_D, D_correct), "（幂次+1）")
print("-" * 60)
print("RESULT:")
print("  A =", A, "KB  ← 正确")
print("  B =", B, "KB  ← bit/Byte混淆")
print("  C =", C, "KB  ← 忽略数据线位宽")
print("  D =", D, "KB  ← 2^18算成2^19")
print("-" * 60)
print("RULE_CHECK:")
print("  规则1(容量定义 capacity_bit==2^n*m):", rule1)
print("  规则2(单位换算 1KB==8192bit 且 capacity_KB==bit/8192):", rule2)
print("  规则3(四选项互异):", distinct, "| 选项值:", options)
print("  规则4(A唯一正确):", A_unique)
print("  规则5(三干扰项≠A且互异):", distractor_rule)
print("  规则6(干扰项合理性): B=%s×A=%.1f倍 C=%.4f×A D=%.1f×A" % (B, B/A, C, D/A))
print("=" * 60)
