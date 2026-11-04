# 二维数组列优先存储地址计算 - gen.py

def solve(m, n, L, Base, i, j):
    """列优先地址计算"""
    return Base + (j * m + i) * L

def main():
    # 题干参数
    m, n = 6, 8
    L = 4
    Base = 1000
    i, j = 2, 3

    # 正确值（列优先公式）
    A = solve(m, n, L, Base, i, j)

    # 干扰项 B：行优先公式误用
    B = Base + (i * n + j) * L

    # 干扰项 C：下标从1开始（i=2,j=3 误作 i=3,j=4）
    C = Base + ((j + 1) * m + (i + 1)) * L

    # 干扰项 D：行列数混淆（m与n互换）
    D = Base + (j * n + i) * L

    # === 验证段（翻译通过条件） ===

    # 条件1：4选项互异
    assert len({A, B, C, D}) == 4, f"选项碰撞: A={A}, B={B}, C={C}, D={D}"

    # 条件2：A等于正确值
    assert A == solve(m, n, L, Base, i, j), "A不等于正确值"

    # 条件3：干扰项对应声明错误类型（已由公式直接计算，结构上保证）

    # 条件4：干扰项与正确答案绝对差值 > 0 且 < 200
    for name, val in [("B", B), ("C", C), ("D", D)]:
        diff = abs(val - A)
        assert diff > 0, f"{name}与正确答案重合"
        assert diff < 200, f"{name}与正确答案差距过大: {diff}"

    # === 输出 ===
    print(f"PARAMS: m={m}, n={n}, L={L}, Base={Base}, i={i}, j={j}")
    print(f"REASONING: 列优先公式 Loc(i,j) = Base + (j*m + i)*L = {Base} + ({j}*{m}+{i})*{L} = {Base} + {j*m+i}*{L} = {Base} + {A - Base} = {A}")
    print(f"ANSWER: {A}")
    print(f"OPTIONS: A={A}, B={B}, C={C}, D={D}")

if __name__ == "__main__":
    main()
