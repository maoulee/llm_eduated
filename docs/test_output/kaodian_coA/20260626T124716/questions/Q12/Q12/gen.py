"""
海明码纠错定位 — gen.py
题干→代码翻译：确定校验位数、校验位/信息位分布、分组计算指误字、伴随式定位纠错、提取信息位。
"""

# ============ PARAMS ============
received = [0, 1, 1, 0, 1, 1, 1]   # 位号1~7 (index 0~6)
m = 4  # 信息位数

# ============ 确定校验位数 k ============
k = 0
while not (2**k >= m + k + 1):
    k += 1

print("=== PARAMS ===")
print(f"信息位数 m = {m}")
print(f"校验位数 k = {k}  (2^k={2**k} >= m+k+1={m+k+1})")
print(f"k=2 是否满足: 2^2={2**2} >= 4+2+1={4+2+1} ? {2**2 >= 4+2+1}")
print(f"总码长 n = {m+k}")
print(f"接收码(位号1~7): {''.join(map(str, received))}")

# ============ 校验位/信息位分布 ============
n = m + k
check_positions = {1, 2, 4}  # 2^0, 2^1, 2^2
positions = {}
for i in range(1, n+1):
    positions[i] = 'P' if i in check_positions else 'D'

print(f"\n=== 位置分布 ===")
print(f"校验位位置: {sorted(check_positions)}")
print(f"信息位位置: {[i for i in range(1,n+1) if i not in check_positions]}")

# ============ 分组计算指误字 ============
# 偶校验：S = XOR of H[i] for all i whose binary representation has that bit set
def calc_syndrome(H):
    # 位号 i (1-based)，bit j: i 的第 j 位为 1
    S = {1: 0, 2: 0, 4: 0}
    for power in [1, 2, 4]:
        bit_idx = {1:0, 2:1, 4:2}[power]
        xor_val = 0
        for i in range(1, len(H)+1):
            if (i >> bit_idx) & 1:
                xor_val ^= H[i-1]
        S[power] = xor_val
    return S

S = calc_syndrome(received)
syndrome_val = S[4]*4 + S[2]*2 + S[1]

print(f"\n=== 指误字 ===")
print(f"S1 (位号二进制含 bit0: {{1,3,5,7}}): H1^H3^H5^H7 = {received[0]}^{received[2]}^{received[4]}^{received[6]} = {S[1]}")
print(f"S2 (位号二进制含 bit1: {{2,3,6,7}}): H2^H3^H6^H7 = {received[1]}^{received[2]}^{received[5]}^{received[6]} = {S[2]}")
print(f"S4 (位号二进制含 bit2: {{4,5,6,7}}): H4^H5^H6^H7 = {received[3]}^{received[4]}^{received[5]}^{received[6]} = {S[4]}")
print(f"伴随式 S4S2S1 = {S[4]}{S[2]}{S[1]} = {syndrome_val}")
print(f"错误位号: {syndrome_val}")

# ============ 纠错 ============
corrected = list(received)
corrected[syndrome_val - 1] ^= 1
print(f"\n=== 纠错 ===")
print(f"纠错: H{syndrome_val} 翻转 {received[syndrome_val-1]} -> {corrected[syndrome_val-1]}")
print(f"纠错后码字: {''.join(map(str, corrected))}")

# ============ 提取信息位 ============
info_positions = [i for i in range(1, n+1) if i not in check_positions]
info_bits = [corrected[i-1] for i in info_positions]
info_str = ''.join(map(str, info_bits))
info_decimal = int(info_str, 2)

print(f"\n=== 提取信息位 ===")
print(f"信息位位置(按位号): {info_positions}")
print(f"D1D2D3D4 = {info_str}")
print(f"十进制值: {info_decimal}")

# ============ 验证 ============
# 1) 校验位数正确
assert k == 3, f"k应为3, 得{k}"
assert 2**k >= m + k + 1, "k不满足海明不等式"
assert 2**(k-1) < m + k, "k=2应不满足(否则k偏大)"

# 2) 指误字非零且指向信息位
assert syndrome_val != 0, "伴随式应为非零(有1位错误)"
assert syndrome_val in {3,5,6,7}, f"错误应落在信息位, 得位号{syndrome_val}"

# 3) 纠错后码字合法(全部偶校验等式成立)
S_after = calc_syndrome(corrected)
assert S_after[1]==0 and S_after[2]==0 and S_after[4]==0, "纠错后码字应满足全部偶校验"

# 4) 纠错自洽: XOR仅1位为1
xor_diff = [received[i]^corrected[i] for i in range(n)]
assert sum(xor_diff) == 1, f"应恰翻转1位, 实际翻转{sum(xor_diff)}位"

# 5) 信息位提取正确(4位)
assert len(info_bits) == 4, "信息位应恰好4位"

print("\n=== ASSERT: 全部通过 ===")

# ============ ANSWER ============
print(f"""
=== ANSWER ===
第1问:
  最少校验位数 k = {k}
  确定依据: 2^k >= m+k+1, 即 2^3=8 >= 4+3+1=8; 而 k=2 时 4 < 7 不满足
  校验位位置(位号): 1, 2, 4
  信息位位置(位号): 3, 5, 6, 7

第2问:
  S1 = {S[1]}, S2 = {S[2]}, S4 = {S[4]}
  伴随式 S4S2S1 = {S[4]}{S[2]}{S[1]} = {syndrome_val}
  错误位号: H{syndrome_val}
  纠错后码字: {''.join(map(str, corrected))}

第3问:
  D1D2D3D4 = {info_str}
  十进制值: {info_decimal}
""")
