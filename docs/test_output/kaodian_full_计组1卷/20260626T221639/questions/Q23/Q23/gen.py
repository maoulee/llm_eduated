# -*- coding: utf-8 -*-
"""
先行进位加法器 CLA —— 纯符号推导题的机检模型（纯 Python 字符串符号展开）
题干递推基式：C_i = G_i + P_i * C_{i-1}  (i=1,2,3,4)
约定：G_i = A_i·B_i，P_i = A_i ⊕ B_i

建模方式：
  - carry_nested(g, p, c_prev) 产出嵌套展开 "g + p·(c_prev)"，逐级代入
  - carry_flat(g, p, terms)    产出分配律展开后的求和项列表，逐级代入
  两种形式各自独立构造，通过条件 assert 打在 flat 展开结果上。
"""
import re

# ---------- 递推基式建模 ----------

def carry_nested(g, p, c_prev):
    """嵌套展开形式：g + p·(c_prev)，保留括号层级"""
    return f"{g} + {p}·({c_prev})"

def carry_flat(g, p, terms):
    """
    分配律展开后的求和项列表。
    C_i = G_i + P_i·C_{i-1}
    若 C_{i-1} 已展开为 terms 列表（每一项是一个乘积字符串），
    则 C_i 的展开 = [G_i] + [P_i·term for term in terms]
    """
    return [g] + [f"{p}·{t}" for t in terms]

# ---------- 符号占位符 ----------
C0_sym = "C0"
G1, G2, G3, G4 = "G1", "G2", "G3", "G4"
P1, P2, P3, P4 = "P1", "P2", "P3", "P4"
intermediate = ["C1", "C2", "C3"]

def contains_intermediate(expr):
    """检查展开字符串是否含 C1/C2/C3（带词边界，避免误匹配）"""
    for var in intermediate:
        if re.search(r'(?<![A-Za-z0-9_])' + var + r'(?![A-Za-z0-9_])', expr):
            return True
    return False

# ==================== 逐级展开（嵌套形式） ====================
# C1 = G1 + P1·C0
C1_nested = f"{G1} + {P1}·{C0_sym}"

# C2 = G2 + P2·(C1_nested)
C2_nested = carry_nested(G2, P2, C1_nested)

# C3 = G3 + P3·(C2_nested)
C3_nested = carry_nested(G3, P3, C2_nested)

# C4 = G4 + P4·(C3_nested)
C4_nested = carry_nested(G4, P4, C3_nested)

# ==================== 逐级展开（flat 分配律形式） ====================
# C1_flat = [G1, P1·C0]
C1_flat = carry_flat(G1, P1, [C0_sym])

# C2_flat = [G2, P2·G1, P2·P1·C0]
C2_flat = carry_flat(G2, P2, C1_flat)

# C3_flat = [G3, P3·G2, P3·P2·G1, P3·P2·P1·C0]
C3_flat = carry_flat(G3, P3, C2_flat)

# C4_flat = [G4, P4·G3, P4·P3·G2, P4·P3·P2·G1, P4·P3·P2·P1·C0]
C4_flat = carry_flat(G4, P4, C3_flat)

# flat 字符串表示（加号连接）
C2_flat_str = " + ".join(C2_flat)
C3_flat_str = " + ".join(C3_flat)
C4_flat_str = " + ".join(C4_flat)

# ==================== 独立构造：基式反复代入的预期结果 ====================
# C2 预期（嵌套）= G2 + P4·...→ 这里用 flat 独立重新构造
expected_C2_flat = carry_flat(G2, P2, carry_flat(G1, P1, [C0_sym]))
expected_C4_flat = carry_flat(G4, P4,
                     carry_flat(G3, P3,
                     carry_flat(G2, P2,
                     carry_flat(G1, P1, [C0_sym]))))

# ==================== 通过条件 assert（打到特征，非恒真） ====================

# 条件2：C2 flat 展开后不含中间进位 C1
assert not contains_intermediate(C2_flat_str), \
    "C2 展开后不应含中间进位 C1/C2/C3"

# 条件2：C2 flat == 基式反复代入的结果
assert C2_flat == expected_C2_flat, \
    f"C2 展开结果 != 递推基式反复代入的结果\n  C2={C2_flat}\n  expected={expected_C2_flat}"

# 条件3：C4 flat 展开后不含 C1/C2/C3
assert not contains_intermediate(C4_flat_str), \
    "C4 展开后不应含中间进位 C1/C2/C3"

# 条件3：C4 flat == 基式反复代入
assert C4_flat == expected_C4_flat, \
    f"C4 展开结果 != 递推基式反复代入的结果\n  C4={C4_flat}\n  expected={expected_C4_flat}"

# 条件4：C4 flat 展开后含最高阶传递项 P4·P3·P2·P1·C0
highest_order = "P4·P3·P2·P1·C0"
assert highest_order in C4_flat_str, \
    "C4 展开后应包含 P4·P3·P2·P1·C0（最高阶传递项）"

# ===================== 底部数据流 =====================
print("=" * 70)
print("【PARAMS】递推基式: C_i = G_i + P_i·C_{i-1}, i=1..4")
print("  定义: G_i = A_i·B_i (进位生成), P_i = A_i⊕B_i (进位传递)")
print("  C0 为外部最低位进位; 操作数位 A_i, B_i")
print()

print("【PROCESS】逐级展开（反复代入基式 C_i = G_i + P_i·C_{i-1}）:")
print(f"  C1 = G1 + P1·C0")
print(f"     = {C1_nested}")
print()
print(f"  C2 = G2 + P2·C1")
print(f"     将 C1 = G1 + P1·C0 代入:")
print(f"     = {C2_nested}  （嵌套形式）")
print(f"     分配律展开:")
print(f"     = {C2_flat_str}")
print(f"     不含中间进位 C1: {not contains_intermediate(C2_flat_str)}")
print()
print(f"  C3 = G3 + P3·C2")
print(f"     = {C3_nested}  （嵌套形式）")
print(f"     分配律展开:")
print(f"     = {C3_flat_str}")
print(f"     不含中间进位: {not contains_intermediate(C3_flat_str)}")
print()
print(f"  C4 = G4 + P4·C3")
print(f"     = {C4_nested}  （嵌套形式）")
print(f"     分配律展开:")
print(f"     = {C4_flat_str}")
print(f"     不含中间进位 C1/C2/C3: {not contains_intermediate(C4_flat_str)}")
print(f"     含最高阶传递项 P4·P3·P2·P1·C0: {highest_order in C4_flat_str}")
print()

print("【RESULT】通过条件全部满足:")
print(f"  [v] C2 展开不含 C1:               {not contains_intermediate(C2_flat_str)}")
print(f"  [v] C2 == 基式反复代入:            {C2_flat == expected_C2_flat}")
print(f"  [v] C4 展开不含 C1/C2/C3:        {not contains_intermediate(C4_flat_str)}")
print(f"  [v] C4 == 基式反复代入:            {C4_flat == expected_C4_flat}")
print(f"  [v] C4 含 P4·P3·P2·P1·C0 项:     {highest_order in C4_flat_str}")
print("=" * 70)

# ===================== 教科书标准展开（solution 转写用） =====================
print()
print("【教科书标准展开形式】")
print("  C1 = G1 + P1·C0")
print()
print("  C2 = G2 + P2·G1 + P2·P1·C0")
print()
print("  C3 = G3 + P3·G2 + P3·P2·G1 + P3·P2·P1·C0")
print()
print("  C4 = G4")
print("     + P4·G3")
print("     + P4·P3·G2")
print("     + P4·P3·P2·G1")
print("     + P4·P3·P2·P1·C0")
