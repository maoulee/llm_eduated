"""
IEEE754 单精度浮点加法运算——步骤填空
A = 0x41E00000, B = 0x40FFFFFF

把题干描述的运算规则翻译成代码：
  分解 → 对阶 → 求和 → 规格化 → 舍入 → 封装
底部 print 完整数据流(PARAMS/PROCESS/RESULT + 场景规则量)。
"""

BIAS = 127

def decompose(hexval):
    """分解 IEEE754 单精度数：符号、阶码字段、阶码真值、尾数(含隐藏位，整数形式)"""
    x = int(hexval, 16)
    sign = (x >> 31) & 0x1
    exp_field = (x >> 23) & 0xFF          # 阶码字段（移码）
    frac = x & 0x7FFFFF                     # 23位尾数字段
    e_true = exp_field - BIAS               # 阶码真值
    # 恢复隐藏位：1.f → 24位尾数
    mant = (1 << 23) | frac                 # 整数形式，共24位
    return sign, exp_field, e_true, frac, mant

def solve():
    A_hex = "0x41E00000"
    B_hex = "0x40FFFFFF"

    # ===== 第一步：分解操作数 =====
    sa, ef_a, ea, frac_a, mant_a = decompose(A_hex)
    sb, ef_b, eb, frac_b, mant_b = decompose(B_hex)

    print("="*70)
    print("PARAMS:")
    print(f"  A = {A_hex}  sign={sa}  exp_field={ef_a}  E_A={ea}  frac_field=0x{frac_a:06X}({frac_a:023b})")
    print(f"  B = {B_hex}  sign={sb}  exp_field={ef_b}  E_B={eb}  frac_field=0x{frac_b:06X}({frac_b:023b})")
    print(f"  A mantissa(含隐藏位) = {mant_a:024b}  (= {mant_a})")
    print(f"  B mantissa(含隐藏位) = {mant_b:024b}  (= {mant_b})")

    # ===== 第二步：对阶（小阶向大阶对齐）=====
    deltaE = abs(ea - eb)
    if ea >= eb:
        # A 阶码大 → B 右移对齐到 A
        large_mant = mant_a
        small_mant = mant_b
        align_dir = "将 B 右移对齐到 A"
        final_e = ea
    else:
        # B 阶码大 → A 右移对齐到 B
        large_mant = mant_b
        small_mant = mant_a
        align_dir = "将 A 右移对齐到 B"
        final_e = eb

    # 小阶尾数右移 deltaE 位
    # 用 GRS 扩展表示：24位尾数右移 deltaE 位
    # 被移出的 deltaE 位中：
    #   G(保护位) = 最高位移出位 = small_mant 的 bit[deltaE-1]
    #   R(舍入位) = 次位移出位   = small_mant 的 bit[deltaE-2]  (deltaE>=2时)
    #   S(粘位)   = 其余移出位的 OR = bit[deltaE-3 .. 0] 的 OR  (deltaE>=3时)
    lost_mask = (1 << deltaE) - 1
    lost_bits = small_mant & lost_mask   # 被移出的低位

    if deltaE >= 1:
        g = (small_mant >> (deltaE - 1)) & 1
    else:
        g = 0
    if deltaE >= 2:
        r = (small_mant >> (deltaE - 2)) & 1
    else:
        r = 0
    if deltaE >= 3:
        s = 1 if (small_mant & ((1 << (deltaE - 2)) - 1)) != 0 else 0
    else:
        s = 0

    # 对阶后的尾数主体（右移后保留的整数部分，24位，高位补0）
    aligned_small_main = small_mant >> deltaE

    # 对阶后尾数 + GRS（拼成一个整数：主体在高位，GRS在低3位）
    # 用于后续求和
    aligned_small_ext = (aligned_small_main << 3) | (g << 2) | (r << 1) | s

    print("\n" + "="*70)
    print("PROCESS: 第二步 对阶")
    print(f"  deltaE = |{ea} - {eb}| = {deltaE}")
    print(f"  对阶方向: {align_dir}")
    print(f"  小阶数尾数(含隐藏位, 24位) = {small_mant:024b}")
    print(f"  右移 {deltaE} 位:")
    print(f"  对阶后尾数主体(24位) = {aligned_small_main:024b}")
    print(f"  被移出位({deltaE}位) = {lost_bits:0{deltaE}b}")
    print(f"  G(保护位)={g}, R(舍入位)={r}, S(粘位)={s}")
    print(f"  对阶后完整(主体+GRS) = {aligned_small_main:024b} | {g}{r}{s}")

    # ===== 第三步：尾数求和 =====
    # 两尾数对齐后求和（同号加法）
    # large_mant 扩展 GRS（低位补0）
    large_ext = (large_mant << 3) | 0   # 27位整数（24位 + 3位GRS=0）
    sum_raw = large_ext + aligned_small_ext  # 求和，可能进位到28位

    print("\n" + "="*70)
    print("PROCESS: 第三步 尾数求和")
    print(f"  大阶数尾数(扩展GRS, 27位) = {large_ext:027b}")
    print(f"  对阶后尾数(扩展GRS, 27位) = {aligned_small_ext:027b}")
    print(f"  求和原始结果(含GRS)       = {sum_raw:0{max(sum_raw.bit_length(),27)}b}")
    sum_bits = sum_raw.bit_length()
    print(f"  原始结果位数 = {sum_bits} 位")
    # 求和结果主体（去掉GRS低3位）
    sum_main = sum_raw >> 3
    print(f"  求和结果主体(去掉GRS) = {sum_main:024b}")
    main_int = sum_main >> 23  # 整数部分
    print(f"  整数部分 = {main_int}  (二进制 {bin(main_int)})")

    # ===== 第四步：规格化 =====
    print("\n" + "="*70)
    print("PROCESS: 第四步 规格化")
    norm_e = final_e
    norm_raw = sum_raw  # 含 GRS

    if main_int >= 2:
        norm_dir = "右规"
        # 右规：尾数右移1位，阶码+1
        norm_raw = norm_raw >> 1
        norm_e = norm_e + 1
        print(f"  整数部分={main_int}(>=2) → 右规：尾数右移1位，阶码+1")
    elif main_int == 0:
        norm_dir = "左规"
        while (norm_raw >> (23+3)) == 0:
            norm_raw = norm_raw << 1
            norm_e = norm_e - 1
        print(f"  整数部分=0 → 左规")
    else:
        norm_dir = "已规格化无需调整"
        print(f"  整数部分={main_int} → 已规格化")

    # 规格化后尾数（含GRS）
    norm_main = norm_raw >> 3
    norm_grs = norm_raw & 0x7
    norm_g = (norm_grs >> 2) & 1
    norm_r = (norm_grs >> 1) & 1
    norm_s = norm_grs & 1
    print(f"  规格化后阶码真值 = {norm_e}")
    print(f"  规格化后尾数主体(24位) = {norm_main:024b}")
    print(f"  规格化后GRS = G={norm_g}, R={norm_r}, S={norm_s}")
    print(f"  规格化后完整(主体+GRS) = {norm_main:024b} | {norm_g}{norm_r}{norm_s}")

    # ===== 第五步：舍入（就近偶数 Round-to-Nearest-Even）=====
    print("\n" + "="*70)
    print("PROCESS: 第五步 舍入（就近偶数）")
    # 规格化后尾数：norm_main（24位主体）+ norm_grs（3位GRS）
    # 舍入时：round_bit = G（第一个移除位），sticky_bit = R | S
    round_bit = norm_g
    sticky_bit = norm_r | norm_s
    lsb = norm_main & 1  # 保留部分最低位

    print(f"  GRS = G={norm_g}, R={norm_r}, S={norm_s}")
    print(f"  舍入位(round/G)={round_bit}, 粘位(sticky=R|S)={sticky_bit}")
    print(f"  保留部分最低位(LSB)={lsb}")

    round_carry = False
    rounded_mant = norm_main  # 24位主体

    if round_bit == 1 and sticky_bit == 1:
        # 向上舍入
        rounded_mant = rounded_mant + 1
        print(f"  round=1,sticky=1 → 向上舍入(+1)")
    elif round_bit == 1 and sticky_bit == 0:
        # tie → 向偶数
        if lsb == 1:
            rounded_mant = rounded_mant + 1
            print(f"  tie且LSB=1 → 向偶数舍入(+1)")
        else:
            print(f"  tie且LSB=0 → 已是偶数，无需调整")
    else:
        print(f"  round=0 → 向下舍入(截断)")

    # 检查舍入后是否尾数溢出（超过24位）
    if rounded_mant > 0xFFFFFF:
        # 进位导致尾数溢出 → 再右规1位
        rounded_mant = rounded_mant >> 1
        norm_e = norm_e + 1
        round_carry = True
        print(f"  舍入进位导致溢出 → 尾数右移1位，阶码+1")
    else:
        round_carry = False

    print(f"  舍入后尾数(24位) = {rounded_mant:024b}")
    print(f"  舍入后阶码真值 = {norm_e}")

    # ===== 第六步：溢出判断与封装 =====
    print("\n" + "="*70)
    print("PROCESS: 第六步 溢出判断与封装")
    final_exp_field = norm_e + BIAS
    if final_exp_field > 254:
        overflow = "上溢"
    elif final_exp_field < 1:
        overflow = "下溢"
    else:
        overflow = "无溢出"

    # 组装 IEEE754 编码
    result_frac = rounded_mant & 0x7FFFFF  # 去掉隐藏位
    final_sign = sa  # 同号加法，符号不变
    result_hex = (final_sign << 31) | (final_exp_field << 23) | result_frac

    # 十进制真值
    final_mant_full = rounded_mant / (1 << 23)  # 1.xxx 形式
    decimal_value = (-1)**final_sign * final_mant_full * (2 ** norm_e)

    print(f"  最终阶码移码值 = {norm_e} + {BIAS} = {final_exp_field}")
    print(f"  溢出判断: {overflow}")
    print(f"  最终尾数(含隐藏位) = {rounded_mant:024b}")
    print(f"  最终尾数字段(去隐藏位) = {result_frac:023b}")
    print(f"  符号位 = {final_sign}")

    # ===== RESULT =====
    print("\n" + "="*70)
    print("RESULT:")
    print(f"  空①: E_A = {ea}, E_B = {eb}")
    print(f"  空②: deltaE = {deltaE}, 对阶方向 = {align_dir}")
    print(f"  空③: 对阶后被右移尾数主体 = {aligned_small_main:024b} | G={g} R={r} S={s}")
    print(f"  空④: 求和原始结果(含GRS) = {sum_raw:0{max(sum_raw.bit_length(),27)}b}")
    print(f"  空⑤: 规格化方向 = {norm_dir}, 规格化后尾数 = {norm_main:024b} | GRS={norm_g}{norm_r}{norm_s}")
    print(f"  空⑥: 规格化后阶码真值 = {norm_e}")
    print(f"  空⑦: 舍入后尾数 = {rounded_mant:024b}, 进位溢出 = {'是' if round_carry else '否'}")
    print(f"  空⑧: 最终移码 = {final_exp_field}, 溢出 = {overflow}")
    print(f"  空⑨: IEEE754编码 = 0x{result_hex:08X}")
    print(f"  空⑩: 十进制真值 = {decimal_value}")

    # ===== 场景规则验证（assert + 数据流对照）=====
    print("\n" + "="*70)
    print("RULE_CHECK (场景规则验证):")

    # 规则1 合法性：阶码字段 ∈ [1,254]
    assert 1 <= ef_a <= 254, f"规则1失败: A阶码字段{ef_a}不在[1,254]"
    assert 1 <= ef_b <= 254, f"规则1失败: B阶码字段{ef_b}不在[1,254]"
    print(f"  规则1(合法性): A阶码字段={ef_a}∈[1,254]=True, B阶码字段={ef_b}∈[1,254]=True")

    # 规则2 阶码差 ≥ 2
    assert deltaE >= 2, f"规则2失败: 阶码差{deltaE}<2"
    print(f"  规则2(阶码差): |E_A-E_B| = |{ea}-{eb}| = {deltaE} >= 2 = True")

    # 规则3 对阶方向唯一：两数阶码不相等
    assert ea != eb, f"规则3失败: 阶码相等({ea}={eb})，无对阶"
    print(f"  规则3(对阶方向唯一): E_A != E_B → {ea} != {eb} = True")

    # 规则4 求和触发规格化：整数部分 ≥2(右规) 或 ==0(左规)
    assert (main_int >= 2) or (main_int == 0), f"规则4失败: 求和整数部分={main_int}，无需规格化"
    print(f"  规则4(求和触发规格化): 求和整数部分={main_int}, 触发=是")

    # 规则5 舍入非平凡：round_bit=1 使就近偶数舍入可能改变LSB
    assert round_bit == 1, f"规则5失败: round_bit=0，舍入不可能改变LSB"
    print(f"  规则5(舍入非平凡): 对阶后G={g}R={r}S={s}, 规格化后GRS={norm_g}{norm_r}{norm_s}, round={round_bit}→舍入改变LSB=是")

    # 规则6 无溢出：最终移码 ∈ [1,254]
    assert 1 <= final_exp_field <= 254, f"规则6失败: 最终移码{final_exp_field}不在[1,254]"
    print(f"  规则6(无溢出): 最终移码={final_exp_field} ∈ [1,254] → True")

    # 规则7 隐藏位恢复：操作数和结果的隐藏位均为1
    assert (mant_a >> 23) == 1, f"规则7失败: A隐藏位≠1"
    assert (mant_b >> 23) == 1, f"规则7失败: B隐藏位≠1"
    assert (rounded_mant >> 23) == 1, f"规则7失败: 结果隐藏位≠1"
    print(f"  规则7(隐藏位恢复): A隐藏位={mant_a>>23}, B隐藏位={mant_b>>23}, 结果隐藏位={rounded_mant>>23}")

    # 规则8 串行一致性：数据流依赖链不断裂
    assert sum_raw == large_ext + aligned_small_ext, "规则8失败: 求和数据流不一致"
    assert norm_raw == sum_raw >> 1, "规则8失败: 规格化数据流不一致(右规>>1)"
    print(f"  规则8(串行一致性): sum_raw = large_ext + aligned_small_ext → True")
    print(f"                    norm_raw == sum_raw >> 1 → True")
    print(f"                    rounded_mant 由 norm_main 经舍入得到")

    return {
        "ea": ea, "eb": eb, "deltaE": deltaE, "align_dir": align_dir,
        "sum_raw": sum_raw, "norm_dir": norm_dir, "norm_e": norm_e,
        "rounded_mant": rounded_mant, "final_exp_field": final_exp_field,
        "overflow": overflow, "result_hex": result_hex, "decimal_value": decimal_value,
        "round_carry": round_carry
    }

if __name__ == "__main__":
    result = solve()
