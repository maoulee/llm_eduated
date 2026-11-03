def decode_f32(bits):
    sign = (bits >> 31) & 0x1
    exp_field = (bits >> 23) & 0xFF
    frac = bits & 0x7FFFFF
    mantissa = (1 << 23) | frac
    return sign, exp_field, frac, mantissa

def test_v2(x_bits, y_bits):
    s_a, E_a, frac_a, mant_a = decode_f32(x_bits)
    s_b, E_b, frac_b, mant_b = decode_f32(y_bits)
    dE = abs(E_a - E_b)
    if E_a >= E_b:
        shift_count = E_a - E_b
        big_sign, big_E, big_mant = s_a, E_a, mant_a
        sml_sign, sml_mant = s_b, mant_b
    else:
        shift_count = E_b - E_a
        big_sign, big_E, big_mant = s_b, E_b, mant_b
        sml_sign, sml_mant = s_a, mant_a
    common_E = big_E
    EXT = shift_count + 3
    big_ext = big_mant << EXT
    sml_full = sml_mant << EXT
    sml_shifted = sml_full >> shift_count
    orig_dropped = sml_mant & ((1 << shift_count) - 1)
    dropped_nonzero = orig_dropped != 0
    val_big = big_ext if big_sign == 0 else -(big_ext)
    val_sml_s = sml_shifted if sml_sign == 0 else -(sml_shifted)
    sum_val = val_big + val_sml_s
    sum_abs = abs(sum_val)
    target_bit = 23 + EXT
    msb_pos = sum_abs.bit_length() - 1
    if msb_pos == target_bit:
        norm_dir = "none"
    elif msb_pos > target_bit:
        diff = msb_pos - target_bit
        norm_abs = sum_abs >> diff
        norm_E = common_E + diff
        norm_dir = f"right({diff})"
    else:
        diff = target_bit - msb_pos
        norm_abs = sum_abs << diff
        norm_E = common_E - diff
        norm_dir = f"left({diff})"
    guard = (norm_abs >> (EXT - 1)) & 1
    roundb = (norm_abs >> (EXT - 2)) & 1
    sticky = 0
    for i in range(EXT - 2):
        sticky |= (norm_abs >> i) & 1
    trunc_mant = norm_abs >> EXT
    more_than_half = (guard == 1) and ((roundb == 1) or (sticky == 1))
    if guard == 0:
        rounded_mant = trunc_mant
        detail = "down"
    elif more_than_half:
        rounded_mant = trunc_mant + 1
        detail = "up"
    else:
        rounded_mant = trunc_mant + 1 if (trunc_mant & 1) else trunc_mant
        detail = "even"
    final_E = norm_E
    second_right = False
    if rounded_mant >= (1 << 24):
        rounded_mant >>= 1
        final_E += 1
        second_right = True
    final_frac = rounded_mant & 0x7FFFFF
    final_sign = 0 if sum_val >= 0 else 1
    machine = (final_sign << 31) | (final_E << 23) | final_frac
    return {
        "x": f"0x{x_bits:08X}", "y": f"0x{y_bits:08X}",
        "dE": dE, "EXT": EXT, "shift_count": shift_count,
        "norm_dir": norm_dir, "guard": guard, "round": roundb, "sticky": sticky,
        "detail": detail, "final_E": final_E, "second_right": second_right,
        "orig_dropped": bin(orig_dropped), "dropped_nonzero": dropped_nonzero,
        "final_hex": f"0x{machine:08X}",
    }

# Test several candidate params
candidates = [
    (0x3F000001, 0x40FFFFFF),  # both pos, dE=3
    (0x3F000007, 0x40FFFFFF),  # both pos, dE=3, frac_a=7
    (0x3F000005, 0x40FFFFFF),  # both pos
    (0x3F100001, 0x40FFFFFF),  # both pos
    (0x3F200001, 0x40FFFFFF),  # both pos
    # opposite sign candidates (left norm)
    (0x3F000007, 0xC0FFFFFF),  # opposite sign
    (0x3F000001, 0xC0800000),  # opposite sign, dE=2
]
for xa, yb in candidates:
    r = test_v2(xa, yb)
    if r:
        print(r)
    else:
        print(f"0x{xa:08X}, 0x{yb:08X}: FAILS rules")
