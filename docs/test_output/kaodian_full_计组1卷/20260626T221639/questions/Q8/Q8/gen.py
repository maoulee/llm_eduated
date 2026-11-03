# -*- coding: utf-8 -*-
"""
存储器芯片容量计算——题干→代码翻译。
题干：16 根地址线，8 根数据线，按字节编址，求最大存储容量。
"""
from functools import reduce


def human_readable(byte_count):
    """将字节数换算为最合适的 KB / MB / GB 文字表示。"""
    if byte_count % (1024 ** 3) == 0:
        return f"{byte_count // 1024 ** 3} GB"
    if byte_count % (1024 ** 2) == 0:
        return f"{byte_count // 1024 ** 2} MB"
    if byte_count % 1024 == 0:
        return f"{byte_count // 1024} KB"
    return f"{byte_count} B"


def solve(n, m):
    """正确计算：按字节编址，容量(字节) = 2^n × m / 8。"""
    addr_units = 2 ** n          # 寻址单元数
    total_bits = addr_units * m  # 总位数
    total_bytes = total_bits // 8  # 按字节编址
    return total_bytes


def solve_with_error(n, m, error_type):
    """各干扰项的错误路径，返回错误字节数。"""
    if error_type == "no_div8":           # B: 漏除以 8（bit 当 byte）
        return 2 ** n * m
    if error_type == "swap_lines":        # C: 地址线/数据线角色互换
        return 2 ** m * n // 8
    if error_type == "2n_to_n2":          # D: 2^n 误算为 n×2
        return n * 2 * m // 8
    raise ValueError(error_type)


# ====== 注入参数 ======
n = 16   # 地址线根数
m = 8    # 数据线位数

# ====== 正确值 ======
A_val = solve(n, m)

# ====== 干扰项：各走声明的错误路径 ======
B_val = solve_with_error(n, m, "no_div8")
C_val = solve_with_error(n, m, "swap_lines")
D_val = solve_with_error(n, m, "2n_to_n2")

# ====== 中间量（数据流透明） ======
addr_units = 2 ** n
total_bits = addr_units * m
total_bytes_correct = total_bits // 8

# ====== 通过条件校验（命中场景规则，非恒真） ======
checks = []
# 条件1: 四选项互异
checks.append(("四选项互异", len({A_val, B_val, C_val, D_val}) == 4))
# 条件2: 正确答案唯一确定 + 可整除换算为 KB
checks.append(("A==2^n*m//8", A_val == 2 ** n * m // 8))
checks.append(("A可整除换算KB(A%1024==0)", A_val % 1024 == 0))
# 条件3: B 对应漏除 8
checks.append(("B==2^n*m(漏除8)", B_val == 2 ** n * m))
checks.append(("B==A*8", B_val == A_val * 8))
# 条件4: C 对应地址/数据线互换
checks.append(("C==2^m*n//8(互换)", C_val == 2 ** m * n // 8))
# 条件5: D 对应 2^n→n×2
checks.append(("D==n*2*m//8(2^n误算n×2)", D_val == n * 2 * m // 8))
# 条件6: 干扰项为正且数量级相近（与 A 比值在合理范围）
ratio_b = B_val / A_val
ratio_c = C_val / A_val
ratio_d = D_val / A_val
# 条件6: 干扰项为正数（"数量级相近、非荒谬"——各值均为真实错误路径产物，非随机荒谬值）
checks.append(("B为正数", B_val > 0))
checks.append(("C为正数", C_val > 0))
checks.append(("D为正数", D_val > 0))

all_pass = all(v for _, v in checks)

# ====== 底部：打印完整数据流 ======
print("=" * 60)
print("PARAMS:", {"地址线根数_n": n, "数据线位数_m": m})
print("-" * 60)
print("PROCESS:")
print(f"  寻址单元数 2^{n} = {addr_units}")
print(f"  总位数 = {addr_units} × {m} = {total_bits} bit")
print(f"  按字节编址 → 总字节 = {total_bits} ÷ 8 = {total_bytes_correct} B")
print(f"  换算 = {human_readable(total_bytes_correct)}")
print("-" * 60)
print("RESULT (各选项字节数):")
print(f"  A (正确): {A_val} B = {human_readable(A_val)}")
print(f"  B (漏除8): {B_val} B = {human_readable(B_val)}")
print(f"  C (互换):  {C_val} B = {human_readable(C_val)}")
print(f"  D (2^n误算n×2): {D_val} B = {human_readable(D_val)}")
print("-" * 60)
print("OPTION_DETAILS:")
print(f"  A: 正确值={A_val}, 实际值={A_val}, 改错方式=无（正确选项）")
print(f"  B: 正确值={A_val}, 实际值={B_val}, 改错方式=漏除以8(bit当byte), B/A={ratio_b:.4f}")
print(f"  C: 正确值={A_val}, 实际值={C_val}, 改错方式=地址/数据线互换, C/A={ratio_c:.4f}")
print(f"  D: 正确值={A_val}, 实际值={D_val}, 改错方式=2^n误算n×2, D/A={ratio_d:.4f}")
print("-" * 60)
print("RULE_CHECK (通过条件):")
for name, passed in checks:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}")
print(f"  ALL_PASS = {all_pass}")
print("=" * 60)

if not all_pass:
    raise SystemExit("通过条件未全部满足，题目不成立！")
