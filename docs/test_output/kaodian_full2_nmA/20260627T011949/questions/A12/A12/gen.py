# -*- coding: utf-8 -*-
"""
IEEE754 单精度浮点加法分步推演：Z = X + Y
X = 0x40780000, Y = 0x3F780003

建模忠实实现 IEEE754 加法流程：拆解→对阶→尾数加法→规格化→舍入→组装
底部打印完整数据流，并将场景规则翻译为 assert（命中题目成立特征）。
"""

def decompose(hexstr):
    """从 32 位十六进制机器数拆解 IEEE754 单精度：符号、阶码字段、尾数字段。"""
    bits = int(hexstr, 16)
    sign = (bits >> 31) & 1
    exp_field = (bits >> 23) & 0xFF
    frac_field = bits & 0x7FFFFF
    return sign, exp_field, frac_field, bits


def frac_to_bits(frac_field):
    """尾数字段（23 位整数）→ 二进制字符串（23 位），前补零。"""
    return format(frac_field, '023b')


def ieee754_add(X_hex, Y_hex):
    """忠实实现 IEEE754 单精度加法流程（同号正数，无减法分支）。"""
    # ========== 第(1)题：拆解 ==========
    sX, eX_f, fX, rawX = decompose(X_hex)
    sY, eY_f, fY, rawY = decompose(Y_hex)
    eX = eX_f - 127          # 实际指数
    eY = eY_f - 127          # 实际指数

    # 1.M 形式尾数：还原隐含前导 1
    # X 尾数 = 1 + frac/2^23, Y 同理
    mantX = (1 << 23) + fX    # 24-bit unsigned: 1.M × 2^23
    mantY = (1 << 23) + fY    # 24-bit unsigned: 1.M × 2^23

    step1 = {
        "X": {
            "sign": sX, "exp_field": eX_f, "exp_actual": eX,
            "frac_field_bits": frac_to_bits(fX),
            "mant_1M_bits": "1." + frac_to_bits(fX),
            "mant_int": mantX,
        },
        "Y": {
            "sign": sY, "exp_field": eY_f, "exp_actual": eY,
            "frac_field_bits": frac_to_bits(fY),
            "mant_1M_bits": "1." + frac_to_bits(fY),
            "mant_int": mantY,
        },
    }

    # ========== 第(2)题：对阶 ==========
    # 小阶向大阶对齐
    e_diff = eX - eY
    if e_diff > 0:
        # Y 是小阶，右移 Y
        shift_op = "Y"
        shift_count = e_diff
        big_exp = eX
        mant_big = mantX       # 不移位
        mant_small_raw = mantY # 要右移
    else:
        shift_op = "X"
        shift_count = -e_diff
        big_exp = eY
        mant_big = mantY
        mant_small_raw = mantX

    shift_count = abs(e_diff)
    big_exp = max(eX, eY)

    # 小阶尾数右移 shift_count 位，用精确整数扩展记录移出位
    # mant_small_raw 是 24 位，右移后丢掉的位进入 Guard/Round/Sticky
    # 用扩展精度（无截断）记录移出的位
    # Guard = 右移后第 24 位之后第 1 位, Round = 第 2 位, Sticky = 其余 OR
    # 但更准确：右移 n 位后，低 n 位是被移出的部分
    # 在对齐后的 1.xx...x.G R S 表示中：
    #   原尾数 24 bit (1.M)，右移 shift_count 位
    #   高 24 位 = 对齐后尾数（含隐含1）
    #   低 shift_count 位 = 移出部分

    shifted = mant_small_raw  # 24-bit
    # 精确计算：右移 shift_count 位
    aligned_small = shifted >> shift_count
    shifted_out = shifted & ((1 << shift_count) - 1)

    # Guard/Round/Sticky（对阶后尾数附加的 3 位保护位）
    # 对阶后尾数是 aligned_small（24 bit），后面跟 shift_count 位移出位
    # 但在 IEEE754 运算的标准表示中，对阶后小阶尾数表示为：
    #   1.MMMMMM... (24 bit aligned) + 移出的位作为 G/R/S
    # Guard = 移出部分的最高位
    # Round  = 移出部分的次高位
    # Sticky = 移出部分其余位的 OR（若 shift_count >= 3）
    #          若 shift_count == 2，则 Guard=最高位, Round=次高位, Sticky=0(无其余位)
    #          但题干说 Sticky 至少为1，需 shift_count>=3 才有 Sticky

    # 构造移出部分的二进制（从高位到低位）
    shifted_out_bits = format(shifted_out, '0{}b'.format(shift_count)) if shift_count > 0 else ""

    if shift_count >= 1:
        # Guard = shifted_out 的最高位
        G = (shifted_out >> (shift_count - 1)) & 1
    else:
        G = 0
    if shift_count >= 2:
        R = (shifted_out >> (shift_count - 2)) & 1
    else:
        R = 0
    # Sticky = 其余低位的 OR（shift_count - 2 位）
    if shift_count > 2:
        rest = shifted_out & ((1 << (shift_count - 2)) - 1)
        S = 1 if rest != 0 else 0
    else:
        S = 0

    step2 = {
        "shift_op": shift_op,
        "shift_count": shift_count,
        "big_exp": big_exp,
        "mant_big_int": mant_big,
        "mant_big_1M_bits": int_to_1M_bits(mant_big),
        "mant_small_aligned_int": aligned_small,
        "mant_small_aligned_1M_bits": int_to_1M_bits(aligned_small),
        "shifted_out_bits": shifted_out_bits,
        "shifted_out_int": shifted_out,
        "Guard": G,
        "Round": R,
        "Sticky": S,
    }

    # ========== 第(3)题：尾数加法 + 规格化 + 舍入 + 组装 ==========
    # 尾数加法（包含 G/R/S 保护位）
    # 将 aligned_small 的 24 位 + G R S 拼成 27 位数参与加法
    # 实际上 mant_big 也是 24 位（1.M × 2^23）
    # 加法在扩展精度下进行：
    #   mant_big:          [1.MMMM...MMMM] (24 bits) 后面补 G=R=S=0
    #   aligned_small:     [1.MMMM...MMMM] (24 bits) 后面跟 shifted_out

    # 用精确整数表示：在 shift_count 位精度下做加法
    # mant_big 的表示精度扩展到 shift_count 位（末尾补零）
    big_extended = mant_big << shift_count   # mant_big 后面补 shift_count 个零
    small_extended = aligned_small << shift_count | shifted_out  # aligned + 移出位

    mant_sum_raw = big_extended + small_extended  # 精确和，位宽 = 24 + shift_count

    # 确定是否有 carry out（尾数之和 >= 2.0，即第 24 位有进位到第 25 位）
    # mant_big 和 aligned_small 都是 24 位 (1.M × 2^23)，值范围 [2^23, 2^24)
    # 它们的和范围 [2^24, 2^25)，所以 mant_sum_raw 的位宽是 25 bit（含 carry）
    # 但因为我们扩展了 shift_count 位，所以 mant_sum_raw 实际位宽 = 25 + shift_count
    # 25 位意味着进位到第 25 位 → 1.xxx × 2，需右规

    # 提取整数和的位模式来检查是否 >= 2.0
    # 原始尾数以 2^23 为单位（1.M = mant / 2^23），和 = mant_sum_raw / 2^(23+shift_count)
    # 但更直观：看 24+shift_count 位以上的进位
    # mant_sum_raw >> (24 + shift_count) 如果 == 1 → 进位 → 右规

    carry_bit = mant_sum_raw >> (24 + shift_count)  # 0 或 1

    if carry_bit == 1:
        # 右规：尾数右移 1 位，阶码 +1
        needs_right_norm = True
        # 右移后，新的移出位 = mant_sum_raw 的最低位
        # 但我们先保留完整精度用于舍入
        # 右移 1 位
        mant_after_norm = mant_sum_raw >> 1
        norm_shifted_out = mant_sum_raw & 1  # 右规移出的 1 位
        final_exp = big_exp + 1
    else:
        needs_right_norm = False
        mant_after_norm = mant_sum_raw
        norm_shifted_out = 0
        final_exp = final_exp if carry_bit else big_exp
        final_exp = big_exp

    # 现在做舍入（round to nearest even）
    # mant_after_norm 包含隐含1 + 23位尾数 + 保护位(GRS或移出位)
    # 我们需要保留 24 位（1.M），对低位做舍入

    # mant_after_norm 的位宽 = 24 + shift_count（或 25 + shift_count - 1 = 24 + shift_count 右规后）
    # 需要保留的位数：24 bit（1 + 23 尾数）
    # 低 (total_bits - 24) 位要舍入

    total_bits = mant_after_norm.bit_length()
    keep_bits = 24
    round_bits = total_bits - keep_bits

    if round_bits > 0:
        round_mask = (1 << round_bits) - 1
        round_part = mant_after_norm & round_mask
        kept_part = mant_after_norm >> round_bits

        half = 1 << (round_bits - 1)  # 舍入阈值

        if round_part > half:
            # 向上舍入
            mant_rounded = kept_part + 1
            round_decision = "up (round_part > half)"
        elif round_part < half:
            # 向下舍入（截断）
            mant_rounded = kept_part
            round_decision = "down (round_part < half)"
        else:
            # 恰好在中间，round to even
            if kept_part & 1:
                mant_rounded = kept_part + 1
                round_decision = "up (tie to even, LSB odd)"
            else:
                mant_rounded = kept_part
                round_decision = "down (tie to even, LSB even)"
    else:
        round_part = 0
        kept_part = mant_after_norm
        mant_rounded = mant_after_norm
        round_decision = "no rounding needed"

    # 检查舍入是否产生新的进位（mant_rounded 可能变成 25 位）
    if mant_rounded >> 24 == 1:
        # 尾数再次溢出（1.111...111 + 1 = 10.000...000），右移，阶码再 +1
        # 但此时 mant_rounded 正好是 2^24，右移后 = 2^23，阶码 +1
        # 这种情况极少，但需处理
        mant_rounded = mant_rounded >> 1
        final_exp = final_exp + 1
        carry_after_round = True
    else:
        carry_after_round = False

    # 提取最终尾数字段（去掉隐含前导 1）
    final_frac = mant_rounded & 0x7FFFFF  # 低 23 位
    final_frac_field = eX_f  # placeholder, will set below
    final_exp_field = final_exp + 127

    # 组装 IEEE754 机器数
    sign_bit = 0  # 同号正数
    Z_bits = (sign_bit << 31) | (final_exp_field << 23) | final_frac
    Z_hex = "0x{:08X}".format(Z_bits)

    step3 = {
        "mant_sum_raw": mant_sum_raw,
        "mant_sum_raw_bin": format(mant_sum_raw, '0{}b'.format(24 + shift_count)),
        "carry_bit": carry_bit,
        "needs_right_norm": needs_right_norm,
        "mant_after_norm": mant_after_norm,
        "norm_shifted_out": norm_shifted_out,
        "total_bits": total_bits,
        "round_bits": round_bits,
        "round_part": round_part,
        "round_part_bin": format(round_part, '0{}b'.format(round_bits)) if round_bits > 0 else "0",
        "kept_part": kept_part,
        "round_decision": round_decision,
        "mant_rounded": mant_rounded,
        "mant_rounded_1M_bits": int_to_1M_bits(mant_rounded),
        "carry_after_round": carry_after_round,
        "final_frac": final_frac,
        "final_frac_bits": frac_to_bits(final_frac),
        "final_exp": final_exp,
        "final_exp_field": final_exp_field,
        "final_exp_field_bits": format(final_exp_field, '08b'),
        "Z_bits": Z_bits,
        "Z_hex": Z_hex,
    }

    return step1, step2, step3


def int_to_1M_bits(val):
    """24-bit unsigned → '1.MMMMM...' 格式字符串。"""
    b = format(val, '024b')
    return b[0] + "." + b[1:]


# ==================== 主程序 ====================
X_hex = "0x40780000"
Y_hex = "0x3EF80003"

step1, step2, step3 = ieee754_add(X_hex, Y_hex)

# ========== 打印完整数据流 ==========
print("=" * 70)
print("PARAMS:")
print("  X =", X_hex)
print("  Y =", Y_hex)
print("  bias = 127, round mode = round to nearest even")
print()

print("=" * 70)
print("【第(1)题】IEEE754 拆解")
print()
print("X:")
for k, v in step1["X"].items():
    print("  {:20s}: {}".format(k, v))
print()
print("Y:")
for k, v in step1["Y"].items():
    print("  {:20s}: {}".format(k, v))
print()

print("=" * 70)
print("【第(2)题】对阶")
print()
for k, v in step2.items():
    print("  {:25s}: {}".format(k, v))
print()

print("=" * 70)
print("【第(3)题】尾数加法 + 规格化 + 舍入 + 组装")
print()
for k, v in step3.items():
    print("  {:25s}: {}".format(k, v))
print()

print("=" * 70)
print("RESULT:")
print("  Z = X + Y 的 IEEE754 机器数 =", step3["Z_hex"])
print("  最终阶码 =", step3["final_exp"], "(十进制), 阶码字段 =", step3["final_exp_field_bits"], "(二进制),", step3["final_exp_field"], "(十进制)")
print("  规格化尾数(1.M) =", step3["mant_rounded_1M_bits"], ", 23位尾数字段 =", step3["final_frac_bits"])
print()

# ========== 场景规则验证（assert） ==========
print("=" * 70)
print("场景规则验证：")
print()

sX, eX_f, fX, rawX = decompose(X_hex)
sY, eY_f, fY, rawY = decompose(Y_hex)

# 规则1：有效规格化数（阶码字段 1-254）
r1 = (1 <= eX_f <= 254) and (1 <= eY_f <= 254)
print("规则1 有效规格化数: eX_f={}, eY_f={}, 均在1-254 → {}".format(eX_f, eY_f, r1))
assert r1, "规则1失败"

# 规则2：同号加法（符号相同，均为0正数）
r2 = (sX == sY)
print("规则2 同号加法: sX={}, sY={} → {}".format(sX, sY, r2))
assert r2, "规则2失败"

# 规则3：阶码差 ≥ 2
eX = eX_f - 127
eY = eY_f - 127
e_diff = abs(eX - eY)
r3 = (e_diff >= 2)
print("规则3 阶码差≥2: |exp(X)-exp(Y)|={}={} → {}".format(e_diff, r3, r3))
assert r3, "规则3失败"

# 规则4：触发右规（对阶后尾数和≥2.0）
r4 = (step3["carry_bit"] == 1)
print("规则4 触发右规: 尾数和carry_bit={} → {}".format(step3["carry_bit"], r4))
assert r4, "规则4失败"

# 规则5：结果不溢出（最终阶码字段 1-254）
final_ef = step3["final_exp_field"]
r5 = (1 <= final_ef <= 254)
print("规则5 结果不溢出: 最终阶码字段={} 在1-254 → {}".format(final_ef, r5))
assert r5, "规则5失败"

# 规则6：移出位有效（对阶过程中小阶操作数尾数有非零位被移出，
#   Guard/Round/Sticky 至少 Sticky 位为 1，使舍入判断步骤非平凡）
#   shift_count >= 3 保证有 Sticky 定义域；小阶尾数低位含非零位落入 Sticky 区间。
r6 = (step2["Sticky"] == 1)
print("规则6 移出位有效: shifted_out_bits={}, Guard={}, Round={}, Sticky={} → {}".format(
    step2["shifted_out_bits"], step2["Guard"], step2["Round"], step2["Sticky"], r6))
assert r6, "规则6失败: Sticky={} (要求Sticky==1)".format(step2["Sticky"])

# 规则7：舍入正确性（Z值与struct.pack结果一致）
import struct
X_float = struct.unpack('!f', struct.pack('!I', rawX))[0]
Y_float = struct.unpack('!f', struct.pack('!I', rawY))[0]
Z_float = X_float + Y_float
Z_bits_computed = struct.unpack('!I', struct.pack('!f', Z_float))[0]
r7 = (Z_bits_computed == step3["Z_bits"])
print("规则7 舍入正确性: Python float加法结果=0x{:08X}, 本模型结果={} → {}".format(
    Z_bits_computed, step3["Z_hex"], r7))
assert r7, "规则7失败: Python=0x{:08X} vs 模型={}".format(Z_bits_computed, step3["Z_hex"])

print()
print(">>> 全部 7 条场景规则验证通过 <<<")
