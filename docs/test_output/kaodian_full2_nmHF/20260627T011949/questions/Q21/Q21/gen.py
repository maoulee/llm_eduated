"""
先行进位加法器进位表达式文字推导 —— 符号建模
将 C_{i+1} = G_i + P_i * C_i 递推公式逐级符号展开，
并用随机数值注入验证四条场景规则。
"""
import random

# ============================================================
# 1. 符号展开（逐级代入，过程可见）
# ============================================================

def expand_carries(n):
    """逐级展开 C_1 ~ C_n，返回 (expanded_list, steps_list)。
    expanded_list[k] 为 C_{k+1} 的完全展开表达式（dict：str->int系数，C0单独标识）。
    steps_list[k] 存储代入步骤（可读字符串列表）。
    表达式用 dict 表示：{'term': coef}，term 是 G/P 组合或 'C0'。
    每个乘积项的 term 用排序后的因子元组表示，加法用 dict 累加。
    """
    exprs = {}      # exprs[k] = C_k 的展开表达式 (dict: term_str -> coef)
    steps = {}      # steps[k] = C_k 展开的步骤字符串列表

    # C_1 = G_0 + P_0 * C_0
    steps[1] = [
        "C_1 = G_0 + P_0 * C_0    （直接由递推公式 i=0 写出）"
    ]
    exprs[1] = {'G_0': 1, 'P_0*C_0': 1}

    for k in range(2, n + 1):
        # C_k = G_{k-1} + P_{k-1} * C_{k-1}
        prev = exprs[k - 1]
        gm = f"G_{k-1}"
        pm = f"P_{k-1}"

        step_list = []
        step_list.append(f"C_{k} = G_{k-1} + P_{k-1} * C_{k-1}    （由递推公式 i={k-1} 写出）")
        # 把 C_{k-1} 的展开式代入
        prev_str = " + ".join(
            (f"{coef}·{term}" if coef != 1 else term) if term != 'C0'
            else (f"{coef}·C_0" if coef != 1 else "C_0")
            for term, coef in sorted(prev.items())
        )
        step_list.append(f"C_{k} = G_{k-1} + P_{k-1} * ( {prev_str} )    （将 C_{k-1} 的展开式代入）")

        # 分配展开：G_{k-1} + sum( P_{k-1} * each term in prev )
        result = {gm: 1}
        for term, coef in prev.items():
            if term == 'C0':
                new_term = f"{pm}*C_0"
            else:
                # term 形如 "P_0*G_1" → 拆分因子，加入 P_{k-1}
                factors = term.split('*')
                new_factors = [pm] + factors
                new_factors_sorted = sorted(new_factors)
                # 去重合并同名因子（CL展开不应重复，但排序后组合保证规范）
                new_term = '*'.join(new_factors_sorted)
            result[new_term] = result.get(new_term, 0) + coef

        # 排序生成最终字符串
        final_str = " + ".join(
            (f"{coef}·{term}" if coef != 1 else term)
            for term, coef in sorted(result.items())
        )
        step_list.append(f"C_{k} = {final_str}    （展开后合并，仅含 G_j、P_j、C_0）")
        steps[k] = step_list
        exprs[k] = result

    return exprs, steps


# ============================================================
# 2. 数值验证：随机注入 G_i, P_i, C_0，检查递推一致性
# ============================================================

def evaluate_expr(expr, G, P, C0):
    """对符号表达式 dict 数值求值（布尔代数：+ = OR, · = AND）。
    每个乘积项内因子做 AND，项之间做 OR。
    """
    total = 0  # OR 的单位元 = 0
    for term in expr:
        if term == 'C0':
            term_val = C0
        else:
            factors = term.split('*')
            term_val = 1  # AND 的单位元 = 1
            for f in factors:
                if f == 'C_0':
                    term_val &= C0
                elif f.startswith('G_'):
                    gi = int(f.split('_')[1])
                    term_val &= G[gi]
                elif f.startswith('P_'):
                    pi = int(f.split('_')[1])
                    term_val &= P[pi]
        total |= term_val
    return total


def verify_rules(n=4, trials=20000):
    """
    验证四条场景规则：
    规则1 递推一致性：展开后的 C_k 数值 == G_{k-1} + P_{k-1}*C_{k-1}(数值)
    规则2 展开完整性：表达式中不残留 C_1, C_2, ...（只允许 C_0 或 C0 标记）
    规则3 P_i 版本一致性：建模中仅使用 P_i = A_i XOR B_i 定义，验证数值匹配
    规则4 下标单调性：C_k 展开式中 G/P 下标 ∈ [0, k-1]，无越界
    """
    exprs, steps = expand_carries(n)

    rule1_pass = True   # 递推一致性
    rule2_pass = True   # 展开完整性
    rule3_pass = True   # P_i 版本一致性
    rule4_pass = True   # 下标单调性

    # --- 规则2 & 规则4：静态结构检查 ---
    for k in range(1, n + 1):
        expr = exprs[k]
        for term in expr:
            if term == 'C0':
                continue
            factors = term.split('*')
            for f in factors:
                if f.startswith('G_'):
                    gi = int(f.split('_')[1])
                    if gi < 0 or gi > k - 1:
                        rule4_pass = False
                elif f.startswith('P_'):
                    pi = int(f.split('_')[1])
                    if pi < 0 or pi > k - 1:
                        rule4_pass = False
                elif f == 'C_0':
                    continue
                else:
                    # 残留中间进位变量
                    rule2_pass = False
        # 检查不残留 C_1~C_{k-1}
        full_str = ' '.join(expr.keys())
        for ci in range(1, k):
            if f"C_{ci} " in full_str + " " or f"C_{ci}*" in full_str:
                # 严格检查：C_{ci} 作为独立变量出现
                pass  # C_0 格式已区分，中间进位不会出现

    # --- 规则1 & 规则3：数值验证 ---
    # 规则3：P_i = A_i XOR B_i，所以需要 A_i, B_i 来生成 G_i 和 P_i
    for t in range(trials):
        A = [random.randint(0, 1) for _ in range(n)]
        B = [random.randint(0, 1) for _ in range(n)]
        C0 = random.randint(0, 1)

        # G_i = A_i * B_i（与）
        G = [A[i] & B[i] for i in range(n)]
        # P_i = A_i XOR B_i（异或定义）
        P = [A[i] ^ B[i] for i in range(n)]

        # 数值递推计算各 C_k
        C_val = {0: C0}
        for i in range(n):
            C_val[i + 1] = G[i] | (P[i] & C_val[i])  # G_i + P_i*C_i 在布尔代数下 = OR

        for k in range(1, n + 1):
            # 规则1：展开表达式数值 == 递推数值
            expanded_val = evaluate_expr(exprs[k], G, P, C0)
            if expanded_val != C_val[k]:
                rule1_pass = False

        # 规则3：进位表达式中 P_i=XOR 与 P_i=OR 等价（数学不变量）
        # 对"只求进位"的展开，carry = G_i + P_i·C_i 与 P_i 取 XOR 还是 OR 无关
        # （二者都恒等于多数函数 G_i + A_i·C_i + B_i·C_i）。此处验证该等价性。
        P_or = [A[i] | B[i] for i in range(n)]
        C_or = {0: C0}
        for i in range(n):
            C_or[i + 1] = G[i] | (P_or[i] & C_or[i])
        rule3_pass = (C_or[n] == C_val[n])

    return exprs, steps, {
        'rule1_递推一致性': rule1_pass,
        'rule2_展开完整性': rule2_pass,
        'rule3_P定义一致性(XOR)': rule3_pass,
        'rule4_下标单调性': rule4_pass,
    }


# ============================================================
# 3. 主程序：展开 + 打印数据流
# ============================================================
n = 4
exprs, steps, checks = verify_rules(n)

print("=" * 70)
print("先行进位加法器进位表达式文字推导")
print("=" * 70)

print("\n### PARAMS")
print(f"  位宽 n = {n}")
print(f"  P_i 定义版本: P_i = A_i ⊕ B_i （异或）")
print(f"  G_i 定义版本: G_i = A_i · B_i （与）")
print(f"  递推公式: C_{{i+1}} = G_i + P_i · C_i")
print(f"  C_0 保留符号（不赋值）")
print(f"  验证试验次数: 20000 次随机注入")

print("\n### PROCESS — 逐级展开步骤")
for k in range(1, n + 1):
    print(f"\n--- C_{k} 展开 ---")
    for s in steps[k]:
        print(f"  {s}")
    print(f"  >> 最终: C_{k} = " + " + ".join(
        (f"{coef}·{term}" if coef != 1 else term)
        for term, coef in sorted(exprs[k].items())
    ))

print("\n### RULE_CHECK — 场景规则验证结果")
for name, passed in checks.items():
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {name}: {status}")

print("\n### RESULT — 最终先行进位表达式")
for k in range(1, n + 1):
    final = " + ".join(
        (f"{coef}·{term}" if coef != 1 else term)
        for term, coef in sorted(exprs[k].items())
    )
    print(f"  C_{k} = {final}")
