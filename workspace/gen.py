#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补码加减交替法（不恢复余数法）除法建模程序。
定点小数 X / Y，n 位小数（不含符号位），双符号位变形补码参与运算。

规则（教材标准，n+1 步法）：
  - 被除数 X、除数 Y 均用双符号位变形补码。
  - 第一步：按被除数 X 与除数 Y 的符号关系决定加减，求出初始余数 R1：
        同号：R1 = [X]补 + [-Y]补   （减 Y）
        异号：R1 = [X]补 + [Y]补    （加 Y）
    并上商位 q0：
        R1 与 Y 同号 -> q0 = 1
        R1 与 Y 异号 -> q0 = 0
  - 之后每一步（共 n 步，得到 q1..qn）：
        (1) 左移余数：R <- 2R（双符号位算术左移，保号）
        (2) 按移位后 R 与 Y 的符号关系加减：
              同号 -> R <- R + [-Y]补（减 Y），商位 = 1
              异号 -> R <- R + [Y]补（加 Y），商位 = 0
        即"同号减异号加；同号商1，异号商0"。
  - 共得到 n+1 位商（q0..qn），其中 q0 是符号位。
  - 异号除法（X、Y 异号）时：末位商恒置 1 校正。
  - 同号除法时：若最低位商为 0，需在最低位恢复（+/-Y 一次）校正余数；
    若末位为 1 则无需恢复。等价地：最终 R 与 X 异号时，恢复一次。
  - 真实余数 R* = 2^(-n) * R。
"""

from fractions import Fraction

N = 4  # 小数部分位数（不含符号位）


# ------------------- 双符号位补码字符串工具 -------------------
# code 形如 "11.0101"（2 位符号 + n 位小数），按 2+n 位 2's complement，
# 数值 = integer(code) / 2^n，其中 integer 按 2^(2+n) 位 2's comp 解释。

def str_to_signed(bits_no_sign, sign):
    """符号 + 数值位串 -> 真值 Fraction。"""
    val = Fraction(0)
    for i, b in enumerate(bits_no_sign, start=1):
        if b == '1':
            val += Fraction(1, 2 ** i)
    return val if sign == '+' else -val


def frac_to_twocomp(x, n=N):
    """真值 x -> 双符号位补码字符串 'SS.xxxx'（n 位小数）。
    把 x * 2^n 当作整数，做 (2+n+1) 位 2's complement 后取低 (2+n) 位。"""
    total = 2 + n
    scale = 2 ** n
    int_val = int(round(x * scale))      # x * 2^n 的整数
    int_val_mod = int_val % (2 ** total)  # 2's complement 取低 total 位
    s = format(int_val_mod, '0{}b'.format(total))
    return s[:2] + '.' + s[2:]


def twocomp_to_frac(code):
    """双符号位补码字符串 -> 真值 Fraction（按 2+n 位 2's complement 解释）。"""
    code = code.replace('.', '')
    total = len(code)
    n = total - 2
    val = int(code, 2)
    if val >= 2 ** (total - 1):  # 最高位为 1 -> 负数
        val -= 2 ** total
    return Fraction(val, 2 ** n)


def neg_twocomp_code(code):
    """[-x]补：对补码整数取相反数后取模。"""
    code = code.replace('.', '')
    total = len(code)
    val = int(code, 2)
    neg_val = (-val) % (2 ** total)
    s = format(neg_val, '0{}b'.format(total))
    return s[:2] + '.' + s[2:]


def add_code(a, b):
    """双符号位补码加法（允许中间 01/10 溢出表示）。"""
    a2 = a.replace('.', '')
    b2 = b.replace('.', '')
    total = len(a2)
    s = (int(a2, 2) + int(b2, 2)) % (2 ** total)
    ss = format(s, '0{}b'.format(total))
    return ss[:2] + '.' + ss[2:]


def left_shift_code(code):
    """双符号位算术左移 1 位：整体左移，最高位丢弃，末位补 0，
    最高符号位用真符号位（原第 2 位）填充以保持符号。"""
    code = code.replace('.', '')
    sign = code[1]              # 真符号位
    shifted = code[1:] + '0'    # 丢最高位，末位补 0
    shifted = sign + shifted[1:]
    return shifted[:2] + '.' + shifted[2:]


def sign_of_code(code):
    """补码字符串代表的数符号: '+' / '-'。0 视为 '+'。"""
    return '+' if twocomp_to_frac(code) >= 0 else '-'


def solve(X_sign, X_bits, Y_sign, Y_bits):
    """
    X_sign/Y_sign: '+' or '-'；X_bits/Y_bits: 小数数值位串（如 '1011'）。
    返回 (reasoning_lines, answer_dict, X, Y, Xc, Yc)。
    """
    global N
    N = len(X_bits)
    assert len(Y_bits) == N, "X, Y 位数必须一致"

    lines = []
    X = str_to_signed(X_bits, X_sign)
    Y = str_to_signed(Y_bits, Y_sign)
    Xc = frac_to_twocomp(X)
    Yc = frac_to_twocomp(Y)
    negYc = neg_twocomp_code(Yc)

    lines.append(f"被除数 X = {X_sign}0.{X_bits} = {X}    [X]补 = {Xc}")
    lines.append(f"除数  Y = {Y_sign}0.{Y_bits} = {Y}    [Y]补 = {Yc}")
    lines.append(f"[-Y]补 = {negYc}")
    same_global = (X_sign == Y_sign)
    lines.append(f"X, Y {'同号' if same_global else '异号'}  =>  "
                 f"{'同号除法' if same_global else '异号除法（末位恒置1校正）'}")
    lines.append("")

    q_bits = []
    R = Xc  # 初始余数 = [X]补

    # ---- 第 0 步：不左移，按 X 与 Y 符号加减，上商位 q0（符号位）----
    r_sign = sign_of_code(R)
    same_sign = (r_sign == Y_sign)
    if same_sign:
        op = f"R 与 Y 同号 -> 减 Y：R = [X]补 + [-Y]补 = {Xc} + {negYc}"
        R = add_code(R, negYc)
    else:
        op = f"R 与 Y 异号 -> 加 Y：R = [X]补 + [Y]补 = {Xc} + {Yc}"
        R = add_code(R, Yc)
    q0 = '1' if same_sign else '0'
    lines.append(f"第 0 步（求商的符号位 q0，不左移）：")
    lines.append(f"    {op}")
    lines.append(f"    新余数 R = {R}")
    lines.append(f"    商位 q0 = {q0}（{'同号取1' if q0 == '1' else '异号取0'}）")
    lines.append("")
    q_bits.append(q0)

    # ---- 后续 n 步：左移 + 加减 + 上数值位 q1..qn ----
    for step in range(1, N + 1):
        R_shift = left_shift_code(R)
        r_sign = sign_of_code(R_shift)
        same_sign = (r_sign == Y_sign)
        lines.append(f"第 {step} 步：")
        lines.append(f"    左移余数：R = {R}  ->  2R = {R_shift}")
        if same_sign:
            op = f"2R 与 Y 同号 -> 减 Y：R = {R_shift} + [-Y]补 = {R_shift} + {negYc}"
            R = add_code(R_shift, negYc)
        else:
            op = f"2R 与 Y 异号 -> 加 Y：R = {R_shift} + [Y]补 = {R_shift} + {Yc}"
            R = add_code(R_shift, Yc)
        q = '1' if same_sign else '0'
        lines.append(f"    {op}")
        lines.append(f"    新余数 R = {R}")
        lines.append(f"    商位 q{step} = {q}（{'同号取1' if q == '1' else '异号取0'}）")
        lines.append("")
        q_bits.append(q)

    raw_Q = ''.join(q_bits)

    # ---- 末位恒置 1 校正（仅异号除法）----
    corrected = False
    if X_sign != Y_sign:
        q_list = list(raw_Q)
        q_list[-1] = '1'
        raw_Q = ''.join(q_list)
        corrected = True
        lines.append(f"异号除法：末位恒置 1 校正 => Q = {raw_Q}")
        lines.append("")

    # ---- 余数校正：R 与 X 异号则恢复一次（+/-Y）----
    R_sign = sign_of_code(R)
    R_final = R
    restored = False
    if R_sign != X_sign:
        if X_sign == Y_sign:
            op = f"R 与 X 异号 -> 加 Y 恢复：R = {R} + [Y]补 = {R} + {Yc}"
            R_final = add_code(R, Yc)
        else:
            op = f"R 与 X 异号 -> 减 Y 恢复：R = {R} + [-Y]补 = {R} + {negYc}"
            R_final = add_code(R, negYc)
        restored = True
        lines.append(f"余数校正：{op}")
        lines.append(f"    恢复后 [R]补 = {R_final}")
        lines.append("")

    R_final_val = twocomp_to_frac(R_final) * Fraction(1, 2 ** N)
    Q_val = twocomp_to_frac(raw_Q)

    answer = {
        "Q_compact": raw_Q,
        "R_compact": R_final,
        "Q_value": Q_val,
        "R_value_true": R_final_val,
        "R_restored": restored,
        "Q_corrected": corrected,
    }
    return lines, answer, X, Y, Xc, Yc


def main():
    # 选定参数：X = -0.1011, Y = 0.1101
    # |X| = 11/16 < |Y| = 13/16，异号，4 步数值迭代，非平凡。
    X_sign, X_bits = '-', '1011'
    Y_sign, Y_bits = '+', '1101'

    print("=== PARAMS ===")
    reasoning, answer, X, Y, Xc, Yc = solve(X_sign, X_bits, Y_sign, Y_bits)
    print(f"X = {X_sign}0.{X_bits}    [X]补 = {Xc}")
    print(f"Y = {Y_sign}0.{Y_bits}    [Y]补 = {Yc}")
    print(f"|X| = {abs(X)}, |Y| = {abs(Y)}, 满足 |X|<|Y|：{abs(X) < abs(Y)}")
    print()
    print("=== REASONING ===")
    for ln in reasoning:
        print(ln)
    print("=== ANSWER ===")
    print(f"[Q]补 = {answer['Q_compact']}    (真值 Q = {answer['Q_value']})")
    print(f"[R]补 = {answer['R_compact']}    "
          f"(真实余数 R* = 2^(-{N}) * R = {answer['R_value_true']})")

    # 验算：X = Q*Y + R*
    print()
    print("=== 验算 ===")
    check = X - answer['Q_value'] * Y
    print(f"X - Q*Y = {X} - ({answer['Q_value']})*({Y}) = {check}")
    ok = (check == answer['R_value_true'])
    print(f"真实余数 R* = {answer['R_value_true']}，与 X - Q*Y {'一致' if ok else '不一致'}")


if __name__ == '__main__':
    main()
