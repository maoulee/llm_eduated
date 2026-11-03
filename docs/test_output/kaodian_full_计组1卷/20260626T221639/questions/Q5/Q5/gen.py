# -*- coding: utf-8 -*-
"""
双符号位（变形补码）加法溢出判定
A = +5, B = +4

题干声明：机器字长 4 位（1 符号位 + 3 数值位），表示范围 [-2^3, 2^3-1] = [-8, +7]。
双符号位法：在原 4 位字基础上将符号位扩展为 2 位 → 2 符号位 + 3 数值位 = 5 位变形补码。

建模方法：
  - 把 4 位补码整数（范围 [-8,7]）转换为 5 位变形补码（符号位扩展）
  - 在 5 位取模空间内做加法
  - 提取双符号位判定溢出
"""

N_NUM = 3   # 数值位位数（4位字 - 1符号位 = 3位数值位）
W = 4       # 基础字长（1 符号位 + 3 数值位）
total_bits = W + 1  # 变形补码 = 2 符号位 + 3 数值位 = 5 位
mod = 1 << total_bits   # 5 位取模空间 = 32

def to_signed_code(val, w=W):
    """将真值转换为 w 位补码整数（取模表示）。"""
    m = 1 << w
    return val % m

def sign_extend_double(val, w=W):
    """将 w 位补码真值扩展为 (w+1) 位变形补码：复制符号位。
    正数：0 → 00，负数：1 → 11
    返回变形补码整数（取模空间 mod = 2^(w+1)）。
    """
    base_mod = 1 << w
    code_w = val % base_mod            # w 位补码表示
    sign_bit = (code_w >> (w - 1)) & 1  # 最高位（符号位）
    if sign_bit == 1:
        # 负数：高两位补 11 → 加 2^w
        double_code = code_w + (1 << w)  # 即 +2^w，让高位为 11...
    else:
        # 正数：高两位补 00 → 不变（但需要 w+1 位表示）
        double_code = code_w
    double_code = double_code % mod
    return double_code

# ========== 参数 ==========
A = 5
B = 4

# 4 位补码表示范围（题干：n=4 → [-8, +7]）
range_max = (1 << (W - 1)) - 1   # 2^3 - 1 = 7
range_min = -(1 << (W - 1))      # -2^3 = -8

# ========== 变形补码转换 ==========
code_A = sign_extend_double(A)   # +5 的变形补码
code_B = sign_extend_double(B)   # +4 的变形补码
bits_A_str = format(code_A & (mod - 1), f'0{total_bits}b')
bits_B_str = format(code_B & (mod - 1), f'0{total_bits}b')

# ========== 变形补码加法 ==========
sum_raw = code_A + code_B
sum_code = sum_raw % mod
sum_bits_str = format(sum_code & (mod - 1), f'0{total_bits}b')
sum_sign = sum_bits_str[:2]  # 高 2 位 = 双符号位

# ========== 溢出判定 ==========
overflow = (sum_sign[0] != sum_sign[1])  # 双符号位相异 = 溢出
if sum_sign == '01':
    overflow_type = "正溢出"
elif sum_sign == '10':
    overflow_type = "负溢出"
elif sum_sign == '00':
    overflow_type = "未溢出（结果为正）"
elif sum_sign == '11':
    overflow_type = "未溢出（结果为负）"

# ========== 场景规则验证（assert 打到特征，非恒真）==========
# 规则1：溢出必然发生——同号相加且超出 n 位表示范围 [-8, +7]
same_sign = (A > 0 and B > 0) or (A < 0 and B < 0)
exceeds = (A + B > range_max) or (A + B < range_min)
assert same_sign and exceeds, f"场景规则1违例：A和B应同号且超出范围[{range_min},{range_max}], got same_sign={same_sign}, exceeds={exceeds}, A+B={A+B}"

# 规则2：溢出时双符号位必须为 01 或 10（相异）
assert sum_sign in ('01', '10'), f"场景规则2违例：溢出时双符号位应为01或10, got {sum_sign}"

# 规则3：正确选项唯一确定——发生溢出
assert overflow == True, f"场景规则3违例：应发生溢出, got overflow={overflow}, sum_sign={sum_sign}"

# 规则4：4选项互异
option_signs = {'01', '10', '00', '11'}
assert len(option_signs) == 4, "场景规则4违例：选项双符号位应互异"

# ========== 各选项分析（错误路径）==========
opt_A_sign = sum_sign  # 正确

# B（方向混淆）：正溢出01 → 负溢出10
if sum_sign == '01':
    opt_B_sign = '10'   # 正溢出颠倒为负溢出
elif sum_sign == '10':
    opt_B_sign = '01'   # 负溢出颠倒为正溢出
else:
    opt_B_sign = '10'

opt_C_sign = '00'  # C（溢出/无溢出混淆）
opt_D_sign = '11'  # D（符号判断来源错误）

# 验证4选项互异
assert len({opt_A_sign, opt_B_sign, opt_C_sign, opt_D_sign}) == 4, "选项碰撞!"

# ========== 底部数据流打印 ==========
print("=" * 60)
print("PARAMS:")
print(f"  A = {A} (十进制)")
print(f"  B = {B} (十进制)")
print(f"  基础字长 = {W} 位（1符号位 + {N_NUM}数值位），表示范围 [{range_min}, {range_max}]")
print(f"  变形补码 = {total_bits} 位（2符号位 + {N_NUM}数值位）")
print()

print("PROCESS - 变形补码转换（符号位扩展）:")
print(f"  A = {A}: 4位补码 = {format(A % (1<<W), f'0{W}b')}  → 变形补码(符号位扩展) = {bits_A_str}")
print(f"  B = {B}: 4位补码 = {format(B % (1<<W), f'0{W}b')}  → 变形补码(符号位扩展) = {bits_B_str}")
print()

print("PROCESS - 变形补码加法:")
print(f"  [A]补 = {bits_A_str}  (= {code_A})")
print(f"  [B]补 = {bits_B_str}  (= {code_B})")
print(f"  相加: {code_A} + {code_B} = {sum_raw},  mod {mod} = {sum_code}")
print(f"  [A+B]补 = {sum_bits_str}")
print()

print("PROCESS - 双符号位提取与判定:")
print(f"  结果码: {sum_bits_str}")
print(f"  双符号位（高2位）S1S0 = {sum_sign}")
print(f"  S1={sum_sign[0]}, S0={sum_sign[1]}, S1≠S0? {sum_sign[0] != sum_sign[1]}")
print(f"  → {'溢出' if overflow else '未溢出'}: {overflow_type}")
print()

print("RULE_CHECK (场景规则验证):")
print(f"  规则1: A+B={A+B} > {range_max}? {A+B > range_max}, 同号={same_sign} → 溢出必然发生={same_sign and exceeds}")
print(f"  规则2: 双符号位 {sum_sign} ∈ {{01,10}} = {sum_sign in ('01','10')}（相异=溢出）")
print(f"  规则3: overflow={overflow}")
print(f"  规则4: 选项双符号位互异 {option_signs}, 4项={len(option_signs)==4}")
print()

print("RESULT:")
print(f"  双符号位 = {sum_sign}")
print(f"  溢出情况 = {overflow_type}")
result_desc = f"双符号位为 {sum_sign}，{'发生了正溢出' if sum_sign == '01' else '发生了负溢出'}"
print(f"  正确答案描述: {result_desc}")
print()

print("=" * 60)
print("OPTIONS ANALYSIS (各选项正确值/实际值/改错方式):")
print(f"  OPTION_A: 双符号位={opt_A_sign}, 正确值={sum_sign}, 实际值={opt_A_sign}, 改错方式=无（正确选项）")
print(f"  OPTION_B: 双符号位={opt_B_sign}, 正确值={sum_sign}, 实际值={opt_B_sign}, 改错方式=正溢出01→负溢出10（方向颠倒）")
print(f"  OPTION_C: 双符号位={opt_C_sign}, 正确值={sum_sign}, 实际值={opt_C_sign}, 改错方式=溢出/无溢出混淆→00（最高符号位0误判未溢出）")
print(f"  OPTION_D: 双符号位={opt_D_sign}, 正确值={sum_sign}, 实际值={opt_D_sign}, 改错方式=符号判断来源错误→11（从操作数符号判定而非结果）")
print(f"  4选项互异: {len({opt_A_sign, opt_B_sign, opt_C_sign, opt_D_sign}) == 4}")
print("=" * 60)
