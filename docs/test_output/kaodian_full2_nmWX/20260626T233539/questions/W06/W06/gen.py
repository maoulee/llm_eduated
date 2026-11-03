"""
IEEE754 单精度浮点加法运算全流程建模
题干规则：拆机器数 → 对阶(小阶尾数右移) → 尾数求和(考虑符号) → 规格化(左规/右规) → 就近舍入(向偶数) → 还原机器数

建模 = 把题干描述的运算步骤逐句翻译成代码。
底部 print 完整数据流供审核对照场景规则验证。
"""

# ============================================================
# IEEE754 解码：把 32 位机器数拆成 符号/阶码E/实际指数e/尾数(含隐含位)
# ============================================================
def decode_f32(hexval):
    bits = int(hexval, 16)
    sign = (bits >> 31) & 0x1
    exp_field = (bits >> 23) & 0xFF
    frac = bits & 0x7FFFFF
    mantissa = (1 << 23) | frac          # 1.xxx... 含隐含最高位 1，共 24 位
    return sign, exp_field, frac, mantissa


# ============================================================
# 全流程：solve(x_hex, y_hex)
# 逐句翻译题干 4 个步骤
# ============================================================
def solve(x_hex, y_hex):
    # ---- 拆机器数 ----
    s_a, E_a, frac_a, mant_a = decode_f32(x_hex)
    s_b, E_b, frac_b, mant_b = decode_f32(y_hex)
    e_a = E_a - 127
    e_b = E_b - 127

    print("=== PARAMS ===")
    print(f"x = {x_hex}, y = {y_hex}")
    print(f"A(x): sign={s_a}, E={E_a}, e={e_a}, mantissa(24b)={bin(mant_a)}")
    print(f"B(y): sign={s_b}, E={E_b}, e={e_b}, mantissa(24b)={bin(mant_b)}")

    # ---- (1) 对阶：小阶向大阶对齐，尾数右移 ----
    # 题干："确定哪个数需右移尾数、右移多少位"
    if E_a >= E_b:
        shift_count = E_a - E_b
        big_sign, big_E, big_mant = s_a, E_a, mant_a
        sml_sign, sml_E, sml_mant = s_b, E_b, mant_b
        shift_target = "A"   # 小阶数 A 需右移
    else:
        shift_count = E_b - E_a
        big_sign, big_E, big_mant = s_b, E_b, mant_b
        sml_sign, sml_E, sml_mant = s_a, E_a, mant_a
        shift_target = "B"

    common_E = big_E

    print(f"\n=== (1) 对阶 ===")
    print(f"大阶: E={big_E} ({'B' if E_a < E_b else 'A'})")
    print(f"小阶: E={sml_E} ({shift_target})")
    print(f"右移位数 shift_count = {shift_count}")

    # 小阶尾数右移 shift_count 位：大阶尾数不移位。
    # 扩展精度：EXT = shift_count + 3，保证被移出的 shift_count 位全部
    #   进入扩展精度的低位区（guard/round/sticky），不丢失。
    # 方法：把两个尾数都左移 EXT 位（放入定点点数格式），小阶尾数再右移 shift_count 位对齐。
    EXT = shift_count + 3
    big_ext = big_mant << EXT                    # 大阶尾数，不移位，低位补 0
    sml_full = sml_mant << EXT                   # 小阶尾数，先放入定点格式
    sml_shifted = sml_full >> shift_count         # 右移对齐；被移出的位进入低位区

    # 对阶中被移出的原始尾数低位（shift_count 位）
    orig_dropped = sml_mant & ((1 << shift_count) - 1)
    dropped_nonzero = (orig_dropped != 0)

    print(f"扩展精度 EXT = {EXT}")
    print(f"对阶后大阶尾数(定点{24+EXT}b): {bin(big_ext)}")
    print(f"对阶后小阶尾数(定点{24+EXT}b): {bin(sml_shifted)}")
    print(f"被移出原始尾数低位 = {bin(orig_dropped)}, nonzero = {dropped_nonzero}")

    # ---- (2) 尾数求和：考虑符号 ----
    # 题干："考虑两数符号，完成尾数的加减运算"
    val_big   =  big_ext    if big_sign == 0 else -(big_ext)
    val_sml_s =  sml_shifted if sml_sign == 0 else -(sml_shifted)
    sum_val = val_big + val_sml_s
    sum_sign = 0 if sum_val >= 0 else 1
    sum_abs  = abs(sum_val)

    print(f"\n=== (2) 尾数求和 ===")
    print(f"带符号大阶值 = {'+' if val_big>=0 else ''}{val_big}")
    print(f"带符号小阶值 = {'+' if val_sml_s>=0 else ''}{val_sml_s}")
    print(f"求和值 = {sum_val}, 符号={sum_sign}, 绝对值={bin(sum_abs)}")

    # ---- (3) 规格化 ----
    # 题干："判断求和结果是否需要规格化（左规或右规）"
    # 定点格式中规格化状态：最高有效位恰在 bit(23+EXT)（即整数部分第24位为隐含的1）
    target_bit = 23 + EXT
    norm_E = common_E
    norm_abs = sum_abs

    if sum_abs == 0:
        norm_dir = "zero"
    else:
        msb_pos = sum_abs.bit_length() - 1
        if msb_pos == target_bit:
            norm_dir = "none"
        elif msb_pos > target_bit:
            diff = msb_pos - target_bit
            norm_abs = norm_abs >> diff
            norm_E += diff
            norm_dir = f"right({diff})"
        else:
            diff = target_bit - msb_pos
            norm_abs = norm_abs << diff
            norm_E -= diff
            norm_dir = f"left({diff})"

    print(f"\n=== (3) 规格化 ===")
    print(f"规格化方向: {norm_dir}")
    print(f"规格化后尾数(定点{24+EXT}b): {bin(norm_abs)}")
    print(f"规格化后阶码 E = {norm_E}")

    # ---- (4) 舍入 (round-to-nearest-even) ----
    # 题干："采用 IEEE754 默认的就近舍入（round-to-nearest-even，向偶数舍入）规则"
    # guard = 扩展精度最高小数位，round = 次高，sticky = 其余位的或
    guard  = (norm_abs >> (EXT - 1)) & 1
    roundb = (norm_abs >> (EXT - 2)) & 1
    sticky = 0
    for i in range(EXT - 2):
        sticky |= (norm_abs >> i) & 1

    trunc_mant = norm_abs >> EXT   # 截断后的 24 位尾数（含隐含位）

    # round-to-nearest-even 逻辑
    half_way       = (guard == 1) and (roundb == 0) and (sticky == 0)
    more_than_half = (guard == 1) and ((roundb == 1) or (sticky == 1))

    if guard == 0:
        rounded_mant = trunc_mant
        round_detail = "向下舍入(截断)"
    elif more_than_half:
        rounded_mant = trunc_mant + 1
        round_detail = "向上舍入(进位)"
    else:  # half_way: 向偶数舍入
        if trunc_mant & 1:
            rounded_mant = trunc_mant + 1   # 奇→进位变偶
            round_detail = "向偶舍入(奇进位)"
        else:
            rounded_mant = trunc_mant        # 偶→不变
            round_detail = "向偶舍入(偶不变)"

    final_E = norm_E

    # 检查舍入后是否溢出（二次右规）
    second_right = False
    if rounded_mant >= (1 << 24):
        rounded_mant >>= 1
        final_E += 1
        second_right = True

    print(f"\n=== (4) 舍入与最终结果 ===")
    print(f"guard={guard}, round={roundb}, sticky={sticky}")
    print(f"舍入判定: {round_detail}")
    print(f"截断尾数(24b) = {bin(trunc_mant)}")
    print(f"舍入后尾数(24b) = {bin(rounded_mant)}, E = {final_E}")
    print(f"二次右规: {'是' if second_right else '否'}")

    # ---- 还原 IEEE754 机器数 ----
    final_frac = rounded_mant & 0x7FFFFF
    final_sign = sum_sign
    machine = (final_sign << 31) | (final_E << 23) | final_frac
    final_hex = f"0x{machine:08X}"

    print(f"最终符号={final_sign}, 阶码E={final_E}, 尾数frac={bin(final_frac)}")
    print(f"最终 IEEE754 机器数 = {final_hex}")

    # ============================================================
    # 场景规则验证（底部 print 数据流 + assert 逐条命中）
    # ============================================================
    print(f"\n=== 场景规则验证 ===")

    # 规则1：正常数约束 E_A, E_B ∈ [1,254]
    rule1 = (1 <= E_a <= 254) and (1 <= E_b <= 254)
    print(f"规则1 正常数约束: E_A={E_a}∈[1,254]={1<=E_a<=254}, E_B={E_b}∈[1,254]={1<=E_b<=254} => {rule1}")
    assert rule1, f"规则1失败: E_A={E_a}, E_B={E_b}"

    # 规则2：对阶非平凡 |E_A - E_B| ∈ [2,5]
    dE = abs(E_a - E_b)
    rule2 = (2 <= dE <= 5)
    print(f"规则2 对阶非平凡: |E_A-E_B|={dE}∈[2,5] => {rule2}")
    assert rule2, f"规则2失败: |E_A-E_B|={dE}"

    # 规则3：求和后需规格化（非 none）
    rule3 = (norm_dir != "none")
    print(f"规则3 求和后需规格化: 方向={norm_dir}, 需规格化={rule3}")
    assert rule3, f"规则3失败: 求和后已规格化无需操作"

    # 规则4：舍入非平凡（对阶右移丢掉有效位 + guard/round/sticky 不全0）
    rule4 = dropped_nonzero and (guard == 1 or roundb == 1 or sticky == 1)
    print(f"规则4 舍入非平凡: 对阶移出非零={dropped_nonzero}, guard/round/sticky非全零={guard==1 or roundb==1 or sticky==1} => {rule4}")
    assert rule4, f"规则4失败: 对阶移出全0或无舍入位"

    # 规则5：无溢出 E_final ∈ [2,253]
    rule5 = (2 <= final_E <= 253)
    print(f"规则5 无溢出: E_final={final_E}∈[2,253] => {rule5}")
    assert rule5, f"规则5失败: E_final={final_E}"

    # 规则6：结果非零
    rule6 = (sum_abs != 0)
    print(f"规则6 结果非零: sum_abs!=0 => {rule6}")
    assert rule6, f"规则6失败: 结果为零"

    print(f"\n=== 所有 6 条场景规则 assert 通过 ===")

    return {
        "x_hex": x_hex, "y_hex": y_hex,
        "A": {"sign": s_a, "E": E_a, "e": e_a, "mantissa": mant_a, "frac": frac_a},
        "B": {"sign": s_b, "E": E_b, "e": e_b, "mantissa": mant_b, "frac": frac_b},
        "shift_count": shift_count, "shift_target": shift_target,
        "EXT": EXT,
        "big_ext": big_ext, "sml_shifted": sml_shifted,
        "orig_dropped": orig_dropped, "dropped_nonzero": dropped_nonzero,
        "sum_sign": sum_sign, "sum_abs": sum_abs,
        "norm_dir": norm_dir, "norm_abs": norm_abs, "norm_E": norm_E,
        "guard": guard, "round": roundb, "sticky": sticky,
        "round_detail": round_detail,
        "trunc_mant": trunc_mant,
        "rounded_mant": rounded_mant, "final_E": final_E,
        "second_right": second_right,
        "final_hex": final_hex,
    }


# ============================================================
# 注入题干参数跑
# ============================================================
# 题干原始参数 x=0x3E800000 (E=125), y=0xC2A00000 (E=133) 阶码差=8，超出规则2范围[2,5]。
# 按题干场景规则声明，在允许范围内微调参数使全部约束满足。
# 新参数（同号两正数，对阶后求和触发右规+舍入进位）：
#   x = 0x3F000007 : sign=0, E=126(e=-1), frac=0x000007 → 尾数=1.00000000000000000000111
#   y = 0x40FFFFFF : sign=0, E=129(e=+2), frac=0x7FFFFF → 尾数=1.11111111111111111111111
#   阶码差 = 3 ∈ [2,5] ✓，对阶右移3位丢掉低位111 → 舍入非平凡 ✓
#   同号相加 → 尾数进位到25位 → 右规 ✓
result = solve("0x3F000007", "0x40FFFFFF")

# 用 Python float 交叉验证（参考，非通过条件）
import struct
x_bits = int("0x3F000007", 16)
y_bits = int("0x40FFFFFF", 16)
x_float = struct.unpack('>f', struct.pack('>I', x_bits))[0]
y_float = struct.unpack('>f', struct.pack('>I', y_bits))[0]
sum_float = x_float + y_float
sum_machine = struct.unpack('>I', struct.pack('>f', sum_float))[0]
print(f"\n=== Python float 交叉验证 ===")
print(f"x = {x_float}")
print(f"y = {y_float}")
print(f"x + y = {sum_float}")
print(f"Python 机器数 = 0x{sum_machine:08X}")
print(f"本题机器数   = {result['final_hex']}")
print(f"一致 = {f'0x{sum_machine:08X}' == result['final_hex']}")
