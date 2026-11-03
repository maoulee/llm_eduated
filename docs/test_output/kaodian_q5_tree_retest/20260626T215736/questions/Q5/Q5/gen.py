# -*- coding: utf-8 -*-
"""
二叉树叶子结点数与度为2结点数的关系应用
N=74, n1=1, 求 n0

场景规则（通过条件）：
  1. 度数守恒: n0 + n1 + n2 = N
  2. 二叉树性质: n0 = n2 + 1
  3. 结果正整数: n0>=1, n2>=1
  4. (N-n1) 为奇数 -> 保证唯一正整数解
  5. 四选项互异

干扰项设计（4选项互异）：
  A = n0 正确值
  B = 漏减 n1: 误用 n0+n2=N（不减n1）联立求解
  C = 混淆 n0 与 n2: 正确求出后误选 n2 的值
  D = 记反公式代入: 正确求出 n2 后，误用 n0=n2-1 直接代入
"""


def solve_correct(N, n1):
    """正确解法：联立 n0=n2+1 与 n0+n1+n2=N"""
    # 约束1: n0 + n1 + n2 = N  ->  n0 + n2 = N - n1
    # 约束2: n0 = n2 + 1  ->  代入: (n2+1) + n2 = N - n1
    #   2*n2 + 1 = N - n1  ->  n2 = (N - n1 - 1) / 2
    #   n0 = n2 + 1 = (N - n1 + 1) / 2
    n2 = (N - n1 - 1) // 2
    n0 = n2 + 1
    return n0, n2


def solve_error_B(N, n1):
    """B: 联立时漏减 n1，误用 n0 + n2 = N，然后 n0 = N - n2
    先联立 n0 = n2 + 1 与 n0 + n2 = N 得 n2 = (N-1)/2
    然后误用 n0 = N - n2（未减 n1 的直接补法）
    """
    n2 = (N - 1) // 2
    n0 = N - n2   # 未减 n1，直接 N - n2 当 n0
    return n0, n2


def solve_error_C(N, n1):
    """C: 混淆 n0 与 n2
    正确求出 n2，但把 n2 的值当作 n0 选
    """
    n2 = (N - n1 - 1) // 2
    n0_selected = n2  # 误选 n2 当 n0
    return n0_selected, n2


def solve_error_D(N, n1):
    """D: 记反公式，正确求出 n2 后误用 n0 = n2 - 1 代入
    正确: n2 = (N-n1-1)/2
    记反: n0 = n2 - 1（公式方向记反，+1 记成 -1）
    """
    n2 = (N - n1 - 1) // 2
    n0 = n2 - 1  # 记反公式直接代入
    return n0, n2


# ---- 注入参数 ----
N = 74
n1 = 1

# ---- 正确解 ----
n0_correct, n2_correct = solve_correct(N, n1)

# ---- B/C/D 各算其错误产物 ----
n0_B, n2_B = solve_error_B(N, n1)          # B: 漏减 n1
n0_C, n2_C = solve_error_C(N, n1)          # C: 混淆 n0/n2
n0_D, n2_D = solve_error_D(N, n1)          # D: 记反公式代入

# ---- 选项赋值 ----
A = n0_correct
B = n0_B
C = n0_C
D = n0_D

# ============================================================
# 底部：打印完整数据流（审核对照场景规则验证）
# ============================================================
print("=" * 60)
print("PARAMS:", {"N": N, "n1": n1, "N-n1": N - n1, "N-n1奇偶": "奇数" if (N - n1) % 2 == 1 else "偶数"})

print("-" * 60)
print("PROCESS（正确解法 A）:")
print("  约束1: n0 + n1 + n2 = N  =>  n0 + n2 = N - n1 = {}".format(N - n1))
print("  约束2: n0 = n2 + 1")
print("  代入: (n2+1) + n2 = {}  =>  2*n2 = {}  =>  n2 = {}".format(N - n1, N - n1 - 1, n2_correct))
print("  回代: n0 = n2 + 1 = {}".format(n0_correct))

print("-" * 60)
print("PROCESS（干扰项 B: 漏减 n1, 误用 n0+n2=N 后 n0=N-n2）:")
print("  联立 n0=n2+1 与 n0+n2=N={}".format(N))
print("  (n2+1)+n2={} => n2={}".format(N, n2_B))
print("  误用 n0=N-n2={}-{}={}".format(N, n2_B, n0_B))

print("-" * 60)
print("PROCESS（干扰项 C: 混淆 n0 与 n2）:")
print("  正确求出 n2={}".format(n2_correct))
print("  误将 n2 的值当作 n0  =>  C = {}".format(n0_C))

print("-" * 60)
print("PROCESS（干扰项 D: 记反公式 n0=n2-1, 正确求n2后代入）:")
print("  正确求出 n2={}".format(n2_correct))
print("  误记 n0=n2-1  =>  n0 = {} - 1 = {}".format(n2_correct, n0_D))

print("-" * 60)
print("RESULT:", {"n0": n0_correct, "n2": n2_correct, "n1": n1, "N": N})

print("-" * 60)
print("RULE_CHECK (场景规则):")
print("  度数守恒 n0+n1+n2={}+{}+{}={}".format(n0_correct, n1, n2_correct, n0_correct + n1 + n2_correct))
print("  性质公式 n0==n2+1: {}=={}+1={}".format(n0_correct, n2_correct, n2_correct + 1))
print("  正整数: n0={}>=1 {}, n2={}>=1 {}".format(n0_correct, n0_correct >= 1, n2_correct, n2_correct >= 1))

print("-" * 60)
print("OPTIONS:")
print("  A={} (正确)".format(A))
print("  B={} (漏减n1)".format(B))
print("  C={} (混淆n0/n2)".format(C))
print("  D={} (记反公式代入)".format(D))
print("  四选项值集合: {}".format(sorted([A, B, C, D])))
print("  四选项互异: {}".format(len(set([A, B, C, D])) == 4))
print("=" * 60)
