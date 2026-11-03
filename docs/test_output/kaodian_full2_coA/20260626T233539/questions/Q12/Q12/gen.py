# -*- coding: utf-8 -*-
"""
海明码纠错定位 —— gen.py
题干规则翻译为代码，底部打印完整数据流，5条场景规则翻译为 assert。
"""

def solve(H):
    """
    输入 H: 长度7的列表 H[1..7]（索引1~7，H[0]占位）。
    偶校验：校验结果 = 校验组内所有位的异或值。
    """
    # ---- 题干：校验组定义（偶校验，组内异或）----
    # S1 对应 P1 组: H1,H3,H5,H7
    S1 = H[1] ^ H[3] ^ H[5] ^ H[7]
    # S2 对应 P2 组: H2,H3,H6,H7
    S2 = H[2] ^ H[3] ^ H[6] ^ H[7]
    # S4 对应 P4 组: H4,H5,H6,H7
    S4 = H[4] ^ H[5] ^ H[6] ^ H[7]

    # ---- 题干：指误字 S = S4 S2 S1 ----
    S_dec = S4 * 4 + S2 * 2 + S1 * 1

    # ---- 第2问：定位 + 纠错 ----
    # 题干：指误字十进制 = 错误位号（海明码定位原理）
    error_pos = S_dec  # 0 表示无错
    H_corrected = H[:]
    if error_pos != 0:
        H_corrected[error_pos] = 1 - H_corrected[error_pos]  # 翻转

    # 纠错后重新计算指误字，验证
    S1_c = H_corrected[1] ^ H_corrected[3] ^ H_corrected[5] ^ H_corrected[7]
    S2_c = H_corrected[2] ^ H_corrected[3] ^ H_corrected[6] ^ H_corrected[7]
    S4_c = H_corrected[4] ^ H_corrected[5] ^ H_corrected[6] ^ H_corrected[7]
    S_dec_c = S4_c * 4 + S2_c * 2 + S1_c

    # ---- 第3问：提取数据位 ----
    # 排列规则: H1=P1, H2=P2, H3=D1, H4=P4, H5=D2, H6=D3, H7=D4
    D1 = H_corrected[3]
    D2 = H_corrected[5]
    D3 = H_corrected[6]
    D4 = H_corrected[7]

    return {
        'S1': S1, 'S2': S2, 'S4': S4,
        'S_bin': f"{S4}{S2}{S1}",
        'S_dec': S_dec,
        'error_pos': error_pos,
        'has_error': error_pos != 0,
        'H_corrected': H_corrected,
        'S_dec_corrected': S_dec_c,
        'D1': D1, 'D2': D2, 'D3': D3, 'D4': D4,
        'data_str': f"{D1}{D2}{D3}{D4}",
    }


# ---- 注入参数跑 ----
H = [0, 0, 1, 1, 0, 1, 1, 1]  # H[1..7] = 0 1 1 0 1 1 1
result = solve(H)

# ============================================================
# 底部：打印完整数据流
# ============================================================
print("=" * 60)
print("PARAMS:")
print(f"  H1..H7 = {' '.join(str(H[i]) for i in range(1,8))}")
print(f"  校验方式: 偶校验（组内异或）")
print()
print("PROCESS - 第1问: 各校验组结果")
print(f"  P1组 (H1^H3^H5^H7) = {H[1]}^{H[3]}^{H[5]}^{H[7]} = {result['S1']}  → S1={result['S1']}")
print(f"  P2组 (H2^H3^H6^H7) = {H[2]}^{H[3]}^{H[6]}^{H[7]} = {result['S2']}  → S2={result['S2']}")
print(f"  P4组 (H4^H5^H6^H7) = {H[4]}^{H[5]}^{H[6]}^{H[7]} = {result['S4']}  → S4={result['S4']}")
print()
print("PROCESS - 指误字组合")
print(f"  S = S4 S2 S1 = {result['S_bin']}")
print(f"  S(十进制) = {result['S_dec']}")
print()
print("PROCESS - 第2问: 定位与纠错")
print(f"  指误字十进制 = {result['S_dec']} → 错误位号 = H{result['error_pos']}")
print(f"  接收码字 H1..H7 = {' '.join(str(H[i]) for i in range(1,8))}")
print(f"  纠错后   H1..H7 = {' '.join(str(result['H_corrected'][i]) for i in range(1,8))}")
print(f"  纠错后指误字 S' = {result['S_dec_corrected']} (验证纠错正确)")
print()
print("PROCESS - 第3问: 提取数据位")
print(f"  排列: H3=D1={result['D1']}, H5=D2={result['D2']}, H6=D3={result['D3']}, H7=D4={result['D4']}")
print(f"  原始信息 D1D2D3D4 = {result['data_str']}")
print()
print("RESULT:")
print(f"  指误字 S = {result['S_bin']} (十进制 {result['S_dec']})")
print(f"  错误位 = H{result['error_pos']}")
print(f"  纠错后码字 = {''.join(str(result['H_corrected'][i]) for i in range(1,8))}")
print(f"  原始数据 D1D2D3D4 = {result['data_str']}")
print("=" * 60)

# ============================================================
# 场景规则 → assert（翻译自 question.md 的5条约束）
# ============================================================

# 规则1: 指误字非零且指向有效位 ∈ {1..7}
assert result['S_dec'] in {1, 2, 3, 4, 5, 6, 7}, \
    f"规则1违反: 指误字={result['S_dec']} 不在有效范围 {{1..7}}"

# 规则2: 错误发生在数据位 ∈ {3,5,6,7}
assert result['error_pos'] in {3, 5, 6, 7}, \
    f"规则2违反: 错误位号={result['error_pos']} 不是数据位(3/5/6/7)"

# 规则3: 纠错后全部校验组通过 → 新指误字 = 0
assert result['S_dec_corrected'] == 0, \
    f"规则3违反: 纠错后指误字={result['S_dec_corrected']} 不为0"

# 规则4: 原始信息非平凡（不全0不全1）
data_set = {result['D1'], result['D2'], result['D3'], result['D4']}
assert data_set != {0} and data_set != {1}, \
    f"规则4违反: 数据位全0或全1, D1D2D3D4={result['data_str']}"

# 规则5: 指误字十进制 = 错误位号
assert result['S_dec'] == result['error_pos'], \
    f"规则5违反: 指误字十进制={result['S_dec']} ≠ 错误位号={result['error_pos']}"

print("\n全部5条场景规则 assert 通过 ✓")
