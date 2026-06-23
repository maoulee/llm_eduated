# KMP next数组计算 - 建模代码
# 模式串 P = "ababac", 求 next[5]

P = "ababac"
target_j = 5

# ============================================================
# 方法1：暴力枚举法（基准）
# ============================================================
def compute_next_brute(P):
    """暴力枚举：对每个j，枚举P[0..j-1]的所有真前后缀，找最长相等的"""
    n = len(P)
    next_arr = [0] * (n + 1)  # next[0..n]
    
    for j in range(1, n + 1):
        sub = P[0:j]  # P[0..j-1]
        max_len = 0
        # 枚举所有可能的真前后缀长度（1到j-1）
        for length in range(1, j):
            prefix = sub[0:length]
            suffix = sub[j - length:j]
            if prefix == suffix and length > max_len:
                max_len = length
        next_arr[j] = max_len
    
    return next_arr

# ============================================================
# 方法2：标准KMP递推法（修复后）
# ============================================================
def compute_next_kmp(P):
    """标准KMP next数组递推"""
    n = len(P)
    next_arr = [0] * (n + 1)
    k = 0
    for j in range(2, n + 1):  # 从j=2开始，next[1]已为0
        while k > 0 and P[k] != P[j - 1]:
            k = next_arr[k]
        if P[k] == P[j - 1]:
            k += 1
        next_arr[j] = k
    return next_arr

# ============================================================
# 求解
# ============================================================
next_brute = compute_next_brute(P)
next_kmp = compute_next_kmp(P)

# 交叉验证：两种方法结果一致
assert next_brute == next_kmp, f"交叉验证失败: brute={next_brute}, kmp={next_kmp}"

correct_value = next_brute[target_j]

print(f"PARAMS: P=\"{P}\", target_j={target_j}")
print(f"REASONING:")
print(f"  P[0..{target_j-1}] = \"{P[0:target_j]}\"")
print(f"  暴力枚举next数组: {next_brute}")
print(f"  KMP递推next数组:  {next_kmp}")
print(f"  交叉验证: {'通过' if next_brute == next_kmp else '失败'}")
print(f"  next[{target_j}] = LPS(\"{P[0:target_j]}\") = {correct_value}")

# ============================================================
# 干扰项生成
# ============================================================

# B: 错误理解next定义（将next[j]误认为LPS(P[0..j-1])+1）
distractor_B = correct_value + 1
print(f"  干扰项B (LPS+1): {distractor_B}")

# C: 前后缀匹配判断错误（仅匹配到较短的相等前后缀）
# 对于"ababa"，真前后缀中"a"(长度1)和"aba"(长度3)都相等
# 错误地只匹配到"a"，得到1
sub = P[0:target_j]  # "ababa"
shorter_match = 0
for length in range(1, target_j):
    prefix = sub[0:length]
    suffix = sub[target_j - length:target_j]
    if prefix == suffix:
        shorter_match = length
        break  # 只取第一个（最短的）匹配
distractor_C = shorter_match
print(f"  干扰项C (最短匹配): {distractor_C}")

# D: 混淆next[j]与next[j+1]（误用P[0..j]的LPS值）
# 即求P[0..5]="ababac"的LPS
sub_j_plus_1 = P[0:target_j + 1]  # "ababac"
lps_j_plus_1 = 0
for length in range(1, target_j + 1):
    prefix = sub_j_plus_1[0:length]
    suffix = sub_j_plus_1[target_j + 1 - length:target_j + 1]
    if prefix == suffix and length > lps_j_plus_1:
        lps_j_plus_1 = length
distractor_D = lps_j_plus_1
print(f"  干扰项D (next[j+1]): {distractor_D}")

# ============================================================
# 通过条件验证（assert）
# ============================================================

# 条件1: next[5]非平凡
assert correct_value >= 1, f"条件1失败: next[{target_j}]={correct_value} < 1"

# 条件2: 4选项互异
A, B, C, D = correct_value, distractor_B, distractor_C, distractor_D
assert len({A, B, C, D}) == 4, f"条件2失败: 选项不互异 {{A={A}, B={B}, C={C}, D={D}}}"

# 条件3: 正确值唯一确定（暴力=KMP已assert）
# 条件4: 干扰项对应声明错误类型（已在生成逻辑中体现）
# 条件5: 干扰项有合理性（已在生成逻辑中体现）

print(f"\nANSWER: A={A}")
print(f"OPTIONS: B={B}, C={C}, D={D}")
print(f"\n验证: 4选项互异 = {len({A,B,C,D}) == 4}")
print(f"验证: next[{target_j}] >= 1 = {correct_value >= 1}")
