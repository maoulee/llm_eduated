# -*- coding: utf-8 -*-
"""
建模：short(-100) -> unsigned short 的同宽度强制类型转换
场景规则：16位 -> 16位，位模式不变，按无符号语义重新解读
"""
WIDTH = 16
MOD = 1 << WIDTH          # 65536
S = -100                  # short 变量初值（补码表示）

# ---- 一次性建模 ----

# short 的 16 位补码位模式（Python 的 & 运算天然实现补码截断到 WIDTH 位）
bits = S % MOD            # 场景规则1：位模式，正整数表示

# 场景规则1：同宽度转换 = 位模式重解读，位模式不变
# unsigned short 的值 = 同一个 16 位位模式按无符号解读
u = bits                  # U == bits

# 场景规则2：U == 65536 + S （对负数 S 成立）
u_check = MOD + S         # 应等于 u

# ---- 干扰项：各错误路径的真实产物 ----
# B: 忽略 unsigned 语义，直接保留原负值
opt_B = S
# C: 误取绝对值（误以为转换仅去符号位）
opt_C = abs(S)
# D: 错误补码公式 65536 - 2*|S|（多减了一次 |S|）
opt_D = MOD - 2 * abs(S)

# ---- A 的正确值 ----
opt_A = u

# ---- 底部：打印完整数据流 ----
print("=" * 60)
print("PARAMS:")
print(f"  WIDTH = {WIDTH}")
print(f"  MOD   = {MOD}")
print(f"  S (short初值) = {S}")
print(f"  abs(S) = {abs(S)}")
print()
print("PROCESS:")
print(f"  S 的 {WIDTH} 位补码位模式 (S % MOD) = {bits}")
print(f"  位模式的二进制表示 = {bits:016b}")
print(f"  同宽度转换：unsigned 值 = 位模式按无符号解读 = {u}")
print(f"  验证公式 MOD + S = {MOD} + ({S}) = {u_check}")
print()
print("RESULT:")
print(f"  u (unsigned short) = {u}")
print()
print("RULE_CHECK (场景规则):")
print(f"  规则1 位模式不变: bits(S)={bits}, u={u}, 相同={bits == u}")
print(f"  规则2 U == MOD+S: u={u}, MOD+S={u_check}, 相等={u == u_check}")
print()
print("OPTIONS (各选项正确值 / 实际标的值 / 改错方式):")
print(f"  OPTION_A: 正确值={opt_A}, 实际值={opt_A}, 改错方式=无（正确选项）")
print(f"  OPTION_B: 正确值={opt_A}, 实际值={opt_B}, 改错方式=忽略unsigned语义直接保留原负值")
print(f"  OPTION_C: 正确值={opt_A}, 实际值={opt_C}, 改错方式=误取绝对值(误以为转换仅去符号位)")
print(f"  OPTION_D: 正确值={opt_A}, 实际值={opt_D}, 改错方式=错误补码公式(MOD-2*|S|)")
print()
print("DISTINCT_CHECK (四选项互异):")
opts = {"A": opt_A, "B": opt_B, "C": opt_C, "D": opt_D}
print(f"  A={opt_A}, B={opt_B}, C={opt_C}, D={opt_D}")
vals = list(opts.values())
all_distinct = len(set(vals)) == len(vals)
print(f"  四值互异 = {all_distinct}")
print(f"  D == MOD - 2*|S| = {MOD} - {2*abs(S)} = {opt_D}")
print("=" * 60)
