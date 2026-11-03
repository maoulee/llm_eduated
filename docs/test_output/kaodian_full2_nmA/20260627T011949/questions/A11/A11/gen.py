# -*- coding: utf-8 -*-
"""
变形补码加减运算与溢出判断 —— gen.py
9位变形补码（2位符号位 + 7位数值位），表示范围 [-128, +127]
x = +95, y = +73

场景规则:
1. x, y 均在 [-128, +127] 内
2. x+y 溢出，x-y 不溢出（恰好一组溢出一组不溢出）
3. 正数双符号位00，负数双符号位11；[-y]变补 = 对[+y]变补连符号位取反加一
4. 双符号位判断法 == 真值范围判断法（超出[-128,127] ⟺ 双符号位不同）
"""

WIDTH = 9                    # 9位变形补码：2符号 + 7数值
VALUE_BITS = WIDTH - 2       # 7位数值位
MOD = 1 << WIDTH             # 512，模运算
RANGE_MAX = (1 << VALUE_BITS) - 1   # 127
RANGE_MIN = -(1 << VALUE_BITS)      # -128


def to_deformed_complement(val):
    """真值 -> 9位变形补码整数值（0~511）。
    正数: 双符号位00 + 绝对值7位
    负数: 双符号位11 + 绝对值取反加一（等同 MOD+val 当 val<0）
    """
    if val >= 0:
        return val & (MOD - 1)
    else:
        return (MOD + val) & (MOD - 1)


def show_bits(code_val):
    """9位变形补码整数值 -> 二进制字符串（9位）"""
    return format(code_val, '09b')


def get_syms(code_val):
    """取变形补码的高2位（双符号位）"""
    return (code_val >> VALUE_BITS) & 0b11


def code_to_trueval(code_val):
    """9位变形补码 -> 对应真值（最高位为符号位）"""
    top_sym = (code_val >> (WIDTH - 1)) & 1
    if top_sym:
        return code_val - MOD
    return code_val


def deformed_add(a_code, b_code):
    """变形补码加法（符号位参与运算）"""
    return (a_code + b_code) % MOD


def is_overflow_by_syms(code_val):
    """双符号位溢出判断: 相同(00/11)->不溢出; 不同(01/10)->溢出"""
    s1 = (code_val >> (WIDTH - 1)) & 1
    s2 = (code_val >> (WIDTH - 2)) & 1
    return s1 != s2


def invert_add_one(code_val):
    """连符号位一起取反加一（求[-y]变形补码）"""
    return (MOD - code_val) % MOD


# ============================================================
# 题目参数
# ============================================================
x = 95
y = 73

print("=" * 60)
print("PARAMS:", {"x": x, "y": y, "编码宽度": WIDTH, "模数": MOD,
                   "符号位": 2, "数值位": VALUE_BITS,
                   "表示范围": f"[{RANGE_MIN}, +{RANGE_MAX}]"})
print("=" * 60)

# ============================================================
# 第(1)问: 真值 -> 变形补码
# ============================================================
print("\n--- 第(1)问: 变形补码表示 ---")

x_code = to_deformed_complement(x)
y_code = to_deformed_complement(y)

x_bits = show_bits(x_code)
y_bits = show_bits(y_code)

x_abs_bits = format(abs(x), '07b')
y_abs_bits = format(abs(y), '07b')

print(f"x = +{x}:")
print(f"  绝对值7位二进制 = {x_abs_bits}")
print(f"  双符号位(正数)  = 00")
print(f"  [x]变补(9位)    = {x_bits}  (整数值={x_code})")

print(f"y = +{y}:")
print(f"  绝对值7位二进制 = {y_abs_bits}")
print(f"  双符号位(正数)  = 00")
print(f"  [y]变补(9位)    = {y_bits}  (整数值={y_code})")

# 场景规则3（正数部分）: 双符号位为00
assert get_syms(x_code) == 0b00, "x变形补码双符号位应为00"
assert get_syms(y_code) == 0b00, "y变形补码双符号位应为00"

# ============================================================
# 第(2)问: [x]变补 + [y]变补，判断溢出
# ============================================================
print("\n--- 第(2)问: 变形补码 x + y ---")

sum_code = deformed_add(x_code, y_code)
sum_bits = show_bits(sum_code)
sum_syms = get_syms(sum_code)
sum_overflow_syms = is_overflow_by_syms(sum_code)

print("  变形补码加法竖式:")
print(f"    [x]变补  = {x_bits}")
print(f"  + [y]变补  = {y_bits}")
print(f"  {'─' * 13}")
print(f"    结果     = {sum_bits}  (整数值={sum_code})")
print(f"  双符号位   = {format(sum_syms, '02b')}")
print(f"  双符号位判断溢出 = {sum_overflow_syms}")

sum_trueval = x + y
print(f"  真值 x+y   = {sum_trueval}")
sum_range_overflow = not (RANGE_MIN <= sum_trueval <= RANGE_MAX)
print(f"  真值是否超出[{RANGE_MIN},+{RANGE_MAX}] = {sum_range_overflow}")
print(f"  结论: {'溢出！原因: x+y=+168 超出7位数值位表示范围[' + str(RANGE_MIN) + ',+' + str(RANGE_MAX) + ']，正溢出' if sum_overflow_syms else '不溢出'}")

# 场景规则2: x+y 溢出
assert sum_overflow_syms == True, "x+y应溢出"
# 场景规则4: 双符号位判断与真值范围判断一致
assert sum_range_overflow == sum_overflow_syms, "x+y: 双符号位判断应与真值范围判断一致"

# ============================================================
# 第(3)问: [x]变补 + [-y]变补，判断溢出
# ============================================================
print("\n--- 第(3)问: 变形补码 x - y ---")

# 先求[-y]变形补码: 连同符号位取反加一
neg_y_code = invert_add_one(y_code)
neg_y_bits = show_bits(neg_y_code)
y_inv_bits = show_bits((~y_code + 1) % MOD)  # 取反加一
y_not_bits = show_bits((~y_code) % MOD)       # 仅取反

print(f"  求 [-y] 变补（对 [y]变补 连同符号位取反加一）:")
print(f"    [y]变补     = {y_bits}  (整数值={y_code})")
print(f"    取反        = {y_not_bits}")
print(f"    取反加一    = {y_inv_bits}  ([-y]变补 整数值={neg_y_code})")

# 验证: [-y]变补真值是否等于 -73
neg_y_trueval = code_to_trueval(neg_y_code)
print(f"    [-y]变补对应真值 = {neg_y_trueval} (应为{-y})")
assert neg_y_trueval == -y, "[-y]变补对应真值应为-y"

diff_code = deformed_add(x_code, neg_y_code)
diff_bits = show_bits(diff_code)
diff_syms = get_syms(diff_code)
diff_overflow_syms = is_overflow_by_syms(diff_code)

print(f"\n  变形补码加法竖式 [x]变补 + [-y]变补:")
print(f"    [x]变补    = {x_bits}")
print(f"  + [-y]变补   = {neg_y_bits}")
print(f"  {'─' * 14}")
print(f"    结果       = {diff_bits}  (整数值={diff_code})")
print(f"  双符号位     = {format(diff_syms, '02b')}")
print(f"  双符号位判断溢出 = {diff_overflow_syms}")

diff_trueval = x - y
diff_result_trueval = code_to_trueval(diff_code)
print(f"  真值 x-y    = {diff_trueval}")
print(f"  结果变形补码对应真值 = {diff_result_trueval}")
diff_range_overflow = not (RANGE_MIN <= diff_trueval <= RANGE_MAX)
print(f"  真值是否超出[{RANGE_MIN},+{RANGE_MAX}] = {diff_range_overflow}")
print(f"  结论: {'溢出' if diff_overflow_syms else '不溢出，运算结果真值为 ' + str(diff_trueval)}")

# 场景规则2: x-y 不溢出
assert diff_overflow_syms == False, "x-y应不溢出"
# 场景规则4
assert diff_range_overflow == diff_overflow_syms, "x-y: 双符号位判断应与真值范围判断一致"

# ============================================================
# 场景规则总验证
# ============================================================
print("\n" + "=" * 60)
print("场景规则验证 (SCENE_RULE_CHECK):")
print("=" * 60)

# 规则1: x, y 在 [-128, +127] 内
r1 = (RANGE_MIN <= x <= RANGE_MAX) and (RANGE_MIN <= y <= RANGE_MAX)
print(f"规则1 表示范围: x={x}∈[{RANGE_MIN},{RANGE_MAX}]={RANGE_MIN<=x<=RANGE_MAX}, "
      f"y={y}∈[{RANGE_MIN},{RANGE_MAX}]={RANGE_MIN<=y<=RANGE_MAX}")
assert r1, "x,y应在表示范围内"

# 规则2: 恰好一组溢出一组不溢出
r2 = sum_overflow_syms != diff_overflow_syms
print(f"规则2 溢出分布: x+y溢出={sum_overflow_syms}, x-y溢出={diff_overflow_syms}, 恰一={r2}")
assert r2, "x+y与x-y应恰一组溢出"

# 规则3: 转换正确性
r3a = get_syms(x_code) == 0b00
r3b = get_syms(y_code) == 0b00
r3c = neg_y_code == (MOD - y_code) % MOD
print(f"规则3 转换正确性: x双符号={format(get_syms(x_code),'02b')}(应00={r3a}), "
      f"y双符号={format(get_syms(y_code),'02b')}(应00={r3b}), "
      f"[-y]取反加一得到={r3c}")
assert r3a and r3b and r3c

# 规则4: 双符号位判断 == 真值范围判断
r4_sum = sum_range_overflow == sum_overflow_syms
r4_diff = diff_range_overflow == diff_overflow_syms
print(f"规则4 判断一致性: x+y→符号法{sum_overflow_syms}==范围法{sum_range_overflow}={r4_sum}, "
      f"x-y→符号法{diff_overflow_syms}==范围法{diff_range_overflow}={r4_diff}")
assert r4_sum and r4_diff

# ============================================================
# RESULT 汇总
# ============================================================
print("\n" + "=" * 60)
print("RESULT:")
print("=" * 60)
result = {
    "第1问": {
        "[x]变补": x_bits,
        "[y]变补": y_bits,
    },
    "第2问": {
        "[x]变补+[y]变补": sum_bits,
        "双符号位": format(sum_syms, '02b'),
        "溢出": sum_overflow_syms,
        "真值x+y": sum_trueval,
        "结论": "溢出（正溢出，x+y=+168 > +127）",
    },
    "第3问": {
        "[-y]变补": neg_y_bits,
        "[x]变补+[-y]变补": diff_bits,
        "双符号位": format(diff_syms, '02b'),
        "溢出": diff_overflow_syms,
        "真值x-y": diff_trueval,
        "结论": f"不溢出，结果真值为 +{diff_trueval}",
    },
}
for k, v in result.items():
    print(f"  {k}:")
    for kk, vv in v.items():
        print(f"    {kk}: {vv}")

print("\n所有场景规则验证通过 ✓")
