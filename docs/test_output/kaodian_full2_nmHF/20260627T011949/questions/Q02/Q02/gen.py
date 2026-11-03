"""
IEEE 754 单精度浮点加法运算结果判断
操作数 A = 0x41266666, B = 0x3F8CCCCC
舍入模式：round to nearest even
"""
import struct

# ========== 参数注入 ==========
A_hex = 0x41266666
B_hex = 0x3F8CCCCC

# ========== 工具函数 ==========
def hex_to_float(h):
    return struct.unpack('>f', struct.pack('>I', h))[0]

def float_to_hex(f):
    return struct.unpack('>I', struct.pack('>f', f))[0]

def hex_to_bits(h, n=32):
    return format(h, f'0{n}b')

def bits_to_hex(bits):
    return format(int(bits, 2), '08X')

def decompose(hexval):
    bits = hex_to_bits(hexval)
    sign = int(bits[0])
    exp_field = int(bits[1:9], 2)
    mant_field = int(bits[9:], 2)
    return sign, exp_field, bits, mant_field

# ========== 选项 A：正确流程 ==========
def option_A_correct():
    sa, ea, bits_a, mf_a = decompose(A_hex)
    sb, eb, bits_b, mf_b = decompose(B_hex)
    
    ta = ea - 127  # 真值指数
    tb = eb - 127
    ediff = ta - tb  # 应为正，B右移
    
    # 完整尾数（含隐含1）= 1.mant
    man_a = (1 << 23) | mf_a
    man_b = (1 << 23) | mf_b
    
    # 对阶：B右移 ediff 位（小阶向大阶）
    # 取被移出的位（低位）用于舍入
    man_b_full = (man_b << ediff)
    guard_bits_str = bin(man_b)[2:]
    shifted_out_bits = bin(man_b)[2:][-ediff:] if len(bin(man_b)[2:]) > (23+1-ediff) else '0'
    
    # 保留移出位用更大位宽表示
    W = 23 + 1 + ediff  # 扩展位宽
    man_b_shifted = man_b  # 原值
    # 完整扩展值（保留移出的位）
    man_b_extended = man_b  # 24-bit
    # 右移ediff位，扩展位宽
    ext_width = 23 + 1 + ediff
    man_b_ext_val = man_b << 0  # 24 bit
    # 在ext_width中右移ediff位
    # man_b in 24 bits -> shifted right by ediff in ext_width bits
    # 高24-ediff位是保留的尾数，低ediff位是guard/sticky
    
    # 在 ext_width 位宽中：
    mb_ext = man_b  # 24 bits value
    # 右移ediff位 = 把24位值放到ext_width位的高24位，然后右移ediff
    # 等价于：(man_b) << ediff 不变, 在 ext_width 位中就是 man_b 原样放高24位，低ediff位是0
    # 然后实际右移ediff位 -> 得到 frac = man_b >> ediff, guard = 剩余位
    
    # 标准做法：用足够大的整数
    # man_a (24-bit) << ediff 使其对齐到与 man_b 相同的小数位
    man_a_shifted = man_a << ediff  # 升到 ext_width
    # man_b 已经是 24-bit, 不移位（它跟自己的小数位对齐）
    # 两者现在都在 ext_width 位宽
    sum_ext = man_a_shifted + man_b
    
    # sum_ext 在 ext_width 位宽，我们需要舍入到 24 位（保留1.xxxx的23位小数）
    # sum_ext >> ediff 得到高24位，低ediff位是舍入信息
    
    sum_24 = sum_ext >> ediff
    low_bits = sum_ext & ((1 << ediff) - 1)
    
    # Round to nearest even
    half = 1 << (ediff - 1)
    lsb_24 = sum_24 & 1
    round_up = (low_bits > half) or (low_bits == half and lsb_24 == 1)
    
    sum_rounded = sum_24 + 1 if round_up else sum_24
    
    # 检查是否需要右规（24位 -> 25位进位）
    if sum_rounded >= (1 << 24):
        # 右规1位
        sum_rounded >>= 1
        result_exp = ta + 1
    else:
        result_exp = ta
    
    # 组装结果
    result_sign = 0
    result_exp_field = result_exp + 127
    result_mant = sum_rounded & ((1 << 23) - 1)
    
    result_hex = (result_sign << 31) | (result_exp_field << 23) | result_mant
    
    return {
        'value_hex': format(result_hex, '08X'),
        'sign_a': sa, 'exp_field_a': ea, 'true_exp_a': ta,
        'sign_b': sb, 'exp_field_b': eb, 'true_exp_b': tb,
        'ediff': ediff,
        'man_a_24bit': format(man_a, '024b'),
        'man_b_24bit': format(man_b, '024b'),
        'man_a_shifted': format(man_a_shifted, f'0{24+ediff}b'),
        'sum_ext_bits': format(sum_ext, f'0{24+ediff}b'),
        'sum_ext_width': 24 + ediff,
        'sum_24': format(sum_24, '024b'),
        'low_bits_val': low_bits, 'low_bits_bits': format(low_bits, f'0{ediff}b'),
        'half_val': half,
        'lsb_24': lsb_24,
        'round_up': round_up,
        'sum_rounded': format(sum_rounded, '024b'),
        'right_norm': sum_rounded >= (1 << 24),
        'result_exp_field': result_exp_field,
        'result_mant': format(result_mant, '023b'),
        'result_bits': format(result_hex, '032b'),
    }

# ========== 选项 B：对阶方向错误（大阶向小阶对齐 = A左移） ==========
def option_B_align_wrong():
    sa, ea, bits_a, mf_a = decompose(A_hex)
    sb, eb, bits_b, mf_b = decompose(B_hex)
    
    ta = ea - 127
    tb = eb - 127
    ediff = ta - tb  # = 3
    
    man_a = (1 << 23) | mf_a
    man_b = (1 << 23) | mf_b
    
    # 错误：A左移ediff位（大阶向小阶对齐）
    # 在B的指数上对齐
    man_a_wrong = man_a << ediff  # A的尾数左移3位
    # B不变
    
    # 相加
    sum_wrong = man_a_wrong + man_b
    # sum_wrong 在 24+3=27 位中
    
    # 用B的指数（较小）作为公共指数
    common_exp = tb  # = 0
    
    # 舍入到24位
    sum_24_wrong = sum_wrong >> ediff
    low_bits = sum_wrong & ((1 << ediff) - 1)
    half = 1 << (ediff - 1)
    lsb_24 = sum_24_wrong & 1
    round_up = (low_bits > half) or (low_bits == half and lsb_24 == 1)
    sum_rounded = sum_24_wrong + 1 if round_up else sum_24_wrong
    
    # 规格化（可能是多次左规）
    while sum_rounded < (1 << 23) and sum_rounded > 0 and common_exp > -126:
        sum_rounded <<= 1
        common_exp -= 1
    
    # 检查右规
    while sum_rounded >= (1 << 24):
        sum_rounded >>= 1
        common_exp += 1
    
    result_exp_field = common_exp + 127
    result_mant = sum_rounded & ((1 << 23) - 1)
    result_hex = (0 << 31) | (result_exp_field << 23) | result_mant
    
    return {
        'value_hex': format(result_hex, '08X'),
        'error': '对阶方向错误：A左移ediff位（大阶向小阶对齐）',
        'man_a_wrong_shifted': format(man_a_wrong, f'0{24+ediff}b'),
        'sum_wrong': format(sum_wrong, f'0{24+ediff}b'),
        'common_exp': common_exp,
        'sum_rounded': format(sum_rounded, '024b'),
        'result_bits': format(result_hex, '032b'),
    }

# ========== 选项 C：忽略隐含位（尾数按0.xxxx处理） ==========
def option_C_no_implicit():
    sa, ea, bits_a, mf_a = decompose(A_hex)
    sb, eb, bits_b, mf_b = decompose(B_hex)
    
    ta = ea - 127
    tb = eb - 127
    ediff = ta - tb  # = 3
    
    # 错误：不补隐含1，尾数 = 0.mant（23位）
    man_a_wrong = mf_a  # 只有23位，没有前导1
    man_b_wrong = mf_b
    
    # 对阶：B右移ediff位
    W = 23 + ediff
    man_a_shifted = man_a_wrong << ediff
    sum_ext = man_a_shifted + man_b_wrong
    
    # 舍入到23位
    sum_23 = sum_ext >> ediff
    low_bits = sum_ext & ((1 << ediff) - 1)
    half = 1 << (ediff - 1)
    lsb_23 = sum_23 & 1
    round_up = (low_bits > half) or (low_bits == half and lsb_23 == 1)
    sum_rounded = sum_23 + 1 if round_up else sum_23
    
    # 规格化（左规）
    common_exp = ta
    while sum_rounded < (1 << 22) and sum_rounded > 0 and common_exp > -126:
        sum_rounded <<= 1
        common_exp -= 1
    
    result_exp_field = common_exp + 127
    result_mant = sum_rounded & ((1 << 23) - 1)
    result_hex = (0 << 31) | (result_exp_field << 23) | result_mant
    
    return {
        'value_hex': format(result_hex, '08X'),
        'error': '忽略隐含位：尾数按0.xxxx处理（不补前导1）',
        'man_a_wrong_23bit': format(mf_a, '023b'),
        'man_b_wrong_23bit': format(mf_b, '023b'),
        'sum_ext': format(sum_ext, f'0{23+ediff}b'),
        'sum_rounded': format(sum_rounded, '023b'),
        'common_exp': common_exp,
        'result_bits': format(result_hex, '032b'),
    }

# ========== 选项 D：不执行舍入（直接丢弃移出低位，truncation） ==========
def option_D_truncation():
    sa, ea, bits_a, mf_a = decompose(A_hex)
    sb, eb, bits_b, mf_b = decompose(B_hex)
    
    ta = ea - 127
    tb = eb - 127
    ediff = ta - tb
    
    man_a = (1 << 23) | mf_a
    man_b = (1 << 23) | mf_b
    
    man_a_shifted = man_a << ediff
    sum_ext = man_a_shifted + man_b
    
    sum_24 = sum_ext >> ediff
    low_bits = sum_ext & ((1 << ediff) - 1)
    
    # 错误：不做舍入修正，直接截断（丢弃移出的低位）
    sum_trunc = sum_24  # 不做 +1 修正
    
    # 检查右规（正确流程的规格化步骤仍执行）
    if sum_trunc >= (1 << 24):
        sum_trunc >>= 1
        result_exp = ta + 1
    else:
        result_exp = ta
    
    result_sign = 0
    result_exp_field = result_exp + 127
    result_mant = sum_trunc & ((1 << 23) - 1)
    result_hex = (result_sign << 31) | (result_exp_field << 23) | result_mant
    
    # 对比：正确流程是否舍入进位
    half = 1 << (ediff - 1)
    lsb_24 = sum_24 & 1
    round_up = (low_bits > half) or (low_bits == half and lsb_24 == 1)
    
    return {
        'value_hex': format(result_hex, '08X'),
        'error': '不执行舍入：直接丢弃移出低位（truncation），不做round to nearest even修正',
        'sum_ext_bits': format(sum_ext, f'0{24+ediff}b'),
        'sum_24_truncated': format(sum_24, '024b'),
        'low_bits_dropped': format(low_bits, f'0{ediff}b'),
        'round_up_correct': round_up,
        'sum_trunc': format(sum_trunc, '024b'),
        'result_exp_field': result_exp_field,
        'result_mant': format(result_mant, '023b'),
        'result_bits': format(result_hex, '032b'),
    }

# ========== 场景规则验证（assert） ==========
def verify_rules():
    a = option_A_correct()
    b = option_B_align_wrong()
    c = option_C_no_implicit()
    d = option_D_truncation()
    
    # 规则1：对阶方向 = 小阶向大阶，移位位数 = ediff ∈ [2,5]
    assert a['ediff'] >= 2 and a['ediff'] <= 5, f"对阶移位位数={a['ediff']}不在[2,5]"
    
    # 规则3：舍入触发——移出位非全零，舍入操作非空
    assert a['low_bits_val'] != 0, f"移出位全零，舍入未触发"
    
    # 规则4：结果合法——非±∞/±0/NaN
    result_exp_a = a['result_exp_field']
    assert result_exp_a != 0 and result_exp_a != 255, f"结果非法（exp_field={result_exp_a}）"
    
    # 规则5：选项互异性
    vals = [a['value_hex'], b['value_hex'], c['value_hex'], d['value_hex']]
    assert len(set(vals)) == 4, f"选项不互异: {vals}"
    
    return True

# ========== 执行 ==========
if __name__ == '__main__':
    print("=" * 70)
    print("PARAMS:")
    print(f"  A = 0x{A_hex:08X} -> float = {hex_to_float(A_hex)}")
    print(f"  B = 0x{B_hex:08X} -> float = {hex_to_float(B_hex)}")
    print(f"  A + B (Python精确) = {hex_to_float(A_hex) + hex_to_float(B_hex)}")
    print(f"  A + B (Python) hex  = 0x{float_to_hex(hex_to_float(A_hex) + hex_to_float(B_hex)):08X}")
    print()
    
    print("=" * 70)
    print("OPTION A (正确流程):")
    ra = option_A_correct()
    for k, v in ra.items():
        print(f"  {k}: {v}")
    print()
    
    print("=" * 70)
    print("OPTION B (对阶方向错误):")
    rb = option_B_align_wrong()
    for k, v in rb.items():
        print(f"  {k}: {v}")
    print()
    
    print("=" * 70)
    print("OPTION C (忽略隐含位):")
    rc = option_C_no_implicit()
    for k, v in rc.items():
        print(f"  {k}: {v}")
    print()
    
    print("=" * 70)
    print("OPTION D (不执行舍入/truncation):")
    rd = option_D_truncation()
    for k, v in rd.items():
        print(f"  {k}: {v}")
    print()
    
    print("=" * 70)
    print("场景规则验证:")
    try:
        verify_rules()
        print("  ALL ASSERTS PASSED ✓")
    except AssertionError as e:
        print(f"  ASSERT FAILED: {e}")
    
    print()
    print("=" * 70)
    print("SUMMARY:")
    print(f"  A (正确): 0x{ra['value_hex']}")
    print(f"  B (对阶方向错): 0x{rb['value_hex']}")
    print(f"  C (忽略隐含位): 0x{rc['value_hex']}")
    print(f"  D (不执行舍入): 0x{rd['value_hex']}")
    print(f"  选项互异: {len(set([ra['value_hex'], rb['value_hex'], rc['value_hex'], rd['value_hex']])) == 4}")
