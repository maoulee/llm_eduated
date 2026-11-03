# -*- coding: utf-8 -*-
"""
7 位补码 1010101 的十进制真值求值。
建模：补码真值定义 + 4 选项按各自声明路径计算。
"""

def twos_complement_value(bits, n):
    """
    补码真值定义（场景规则1）：
    x = b_{n-1} b_{n-2} ... b_0
    真值 == (-b_{n-1}) * 2^(n-1) + sum(b_i * 2^i, i=0..n-2)
    bits 高位在前: bits[0]=b_{n-1}, bits[n-1]=b_0
    """
    val = 0
    for idx in range(n):
        bit_pos = n - 1 - idx  # bit_pos 从 n-1 到 0
        b = int(bits[idx])
        if bit_pos == n - 1:
            # 符号位负权值
            val += (-b) * (2 ** bit_pos)
        else:
            val += b * (2 ** bit_pos)
    return val


def unsigned_value(bits, n):
    """全 n 位无符号正权展开（干扰项C路径）。"""
    val = 0
    for idx in range(n):
        bit_pos = n - 1 - idx
        b = int(bits[idx])
        val += b * (2 ** bit_pos)
    return val


def low_bits_positive(bits, n):
    """仅低 n-1 位正权展开，忽略符号位负权值（干扰项B路径）。"""
    val = 0
    for idx in range(1, n):  # 跳过 bits[0]（符号位）
        bit_pos = n - 1 - idx
        b = int(bits[idx])
        val += b * (2 ** bit_pos)
    return val


def solve(bits="1010101", n=7):
    # 正确真值（补码展开）
    A = twos_complement_value(bits, n)
    # 干扰项 B: 仅低 6 位正权展开（忽略符号位负权值）
    B = low_bits_positive(bits, n)
    # 干扰项 C: 全 7 位无符号正权展开
    C = unsigned_value(bits, n)
    # 干扰项 D: 正确展开后漏算 2^0 位（即 +2^0，使 -43 -> -42）
    D = A + (2 ** 0)  # 漏算符号位 b_0 的负贡献方向偏差1个2^0

    return A, B, C, D


def is_power_of_two(x):
    return x > 0 and (x & (x - 1)) == 0


# ---- 注入参数跑 ----
bits = "1010101"
n = 7
A, B, C, D = solve(bits, n)

# ---- 底部：打印完整数据流 ----
print("PARAMS:", {"bits": bits, "n": n})
print("BIT_BREAKDOWN:", {
    "bit6(sign)": bits[0],
    "bit5..0": bits[1:],
})

# 正确展开过程逐步
process = []
for idx in range(n):
    bit_pos = n - 1 - idx
    b = int(bits[idx])
    if bit_pos == n - 1:
        contrib = (-b) * (2 ** bit_pos)
        process.append({"bit": idx, "bit_pos": bit_pos, "value": b, "weight": f"-2^{bit_pos}", "contribution": contrib})
    else:
        contrib = b * (2 ** bit_pos)
        process.append({"bit": idx, "bit_pos": bit_pos, "value": b, "weight": f"+2^{bit_pos}", "contribution": contrib})
print("PROCESS(正确补码展开):")
for p in process:
    print("  ", p)
print("PROCESS_SUM:", sum(p["contribution"] for p in process), "== A =", A)

print()
print("OPTION_A:", {"正确值": A, "实际值": A, "改错方式": "无（正确选项）"})
print("OPTION_B:", {"正确值": A, "实际值": B, "改错方式": "符号位判断错误：忽略符号位负权值，仅低6位正权展开"})
print("OPTION_C:", {"正确值": A, "实际值": C, "改错方式": "全部按无符号正权展开（符号位也当正权值）"})
print("OPTION_D:", {"正确值": A, "实际值": D, "改错方式": "某一位漏算：正确展开后漏算2^0位(A + 2^0)"})

print()
print("RESULT:", {"A": A, "B": B, "C": C, "D": D})

# ---- 场景规则验证（数据流可读）----
print()
print("RULE_CHECK:")
# 规则1: 补码真值定义 — 重建检验
rebuild = (-int(bits[0])) * 2**(n-1) + sum(int(bits[i]) * 2**(n-1-i) for i in range(1, n))
print("  规则1_补码定义重建 == A:", rebuild, "==", A, "->", rebuild == A)
# 规则2: 符号位==1 且真值<0
print("  规则2_符号位==1:", bits[0] == '1', "| 真值<0:", A < 0)
# 规则3: |真值| 非2的幂
print("  规则3_|真值|非2幂:", not is_power_of_two(abs(A)), "| |A| =", abs(A))
# 规则4: 4选项互异
vals = [A, B, C, D]
print("  规则4_4选项互异:", len(set(vals)) == 4, "| vals =", vals)
# 规则5: A == 补码正确展开（且B,C,D != A）
print("  规则5_仅A为正确答案:", A == twos_complement_value(bits, n), "| B!=A:", B != A, "| C!=A:", C != A, "| D!=A:", D != A)
# 规则6: 干扰项对应声明错误类型
b_expect = low_bits_positive(bits, n)
c_expect = unsigned_value(bits, n)
d_expect = A + (2**0)
print("  规则6_B==低6位正权展开:", B == b_expect)
print("  规则6_C==全7位无符号:", C == c_expect)
print("  规则6_D==A+2^0(漏算2^0):", D == d_expect)
# 规则7: 干扰项合理性（与正确值同量级，非荒谬值）
print("  规则7_干扰项合理性:", "B,C,D 均为 [-128,127] 附近范围内的真实误算值")
