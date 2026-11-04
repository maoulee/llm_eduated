import random

# ========== 参数搜索 ==========
# 约束：
#   7 <= n <= 127
#   1 <= n1 <= n-3
#   (n - n1 - 1) 为正偶数
#   n0 = (n - n1 - 1)/2 + 1 >= 2
#   n1 != n2 (即 n1 != n0-1)，保证干扰C != 正确值
#   四个选项值互不相同
#
# 初始值：选 n=25, n1=5

def search_params(n_init, n1_init):
    """从初始值出发，验证约束，不满足则扫描调整。"""
    for n in range(max(7, n_init), 128):
        for n1 in range(max(1, n1_init), n - 2):
            # (n - n1 - 1) 必须为正偶数
            val = n - n1 - 1
            if val <= 0 or val % 2 != 0:
                continue
            n2 = val // 2
            n0 = n2 + 1
            if n0 < 2:
                continue
            # 一致性检查
            assert n == n0 + n1 + n2, f"一致性失败: {n} != {n0}+{n1}+{n2}"
            # 退化检查：n1 != n2
            if n1 == n2:
                continue
            # 构造四个选项值
            correct = n0              # 正确：n0 = n2 + 1
            dist_B = n2               # 混淆方向：取 n2 不加1
            dist_C = n1 + 1           # 误用 n1 代入：n0' = n1 + 1
            dist_D = val              # 遗漏分解：直接取 n - n1 - 1（未除以2）
            # 四值互不相同
            values = [correct, dist_B, dist_C, dist_D]
            if len(set(values)) != 4:
                continue
            return {
                'n': n, 'n1': n1, 'n2': n2, 'n0': n0,
                'correct': correct,
                'dist_B': dist_B, 'dist_C': dist_C, 'dist_D': dist_D,
            }
    return None

result = search_params(25, 5)
assert result is not None, "未找到满足约束的参数"

r = result
n, n1, n2, n0 = r['n'], r['n1'], r['n2'], r['n0']

print("========== 参数搜索结果 ==========")
print(f"n = {n}, n1 = {n1}")
print(f"n2 = {n2}")
print(f"n0 = {n0}")
print()

# ========== 验证 ==========
print("========== 约束验证 ==========")
assert 7 <= n <= 127, f"n 越界: {n}"
assert 1 <= n1 <= n - 3, f"n1 越界: {n1}"
assert (n - n1 - 1) > 0 and (n - n1 - 1) % 2 == 0, "n-n1-1 非正偶数"
assert n == n0 + n1 + n2, "总结点数不自洽"
assert n0 == n2 + 1, "n0 != n2+1"
assert n0 >= 2, "n0 < 2"
assert n1 != n2, "退化: n1 == n2"
print(f"✓ n 在 [7, 127] 范围内")
print(f"✓ n1 在 [1, n-3] 范围内")
print(f"✓ (n - n1 - 1) = {n - n1 - 1} 为正偶数")
print(f"✓ n = n0 + n1 + n2 = {n0} + {n1} + {n2} = {n0 + n1 + n2}")
print(f"✓ n0 = n2 + 1 = {n2} + 1 = {n0}")
print(f"✓ n1({n1}) != n2({n2})，干扰C有区分力")
print()

# ========== 求解数据流 ==========
print("========== 求解数据流 ==========")
print(f"已知：n = {n}, n1 = {n1}")
print(f"步骤1：由 n = n0 + n1 + n2 和 n0 = n2 + 1 联立")
print(f"  => n = (n2 + 1) + n1 + n2 = 2*n2 + 1 + n1")
print(f"  => n2 = (n - n1 - 1) / 2 = ({n} - {n1} - 1) / 2 = {n - n1 - 1} / 2 = {n2}")
print(f"步骤2：n0 = n2 + 1 = {n2} + 1 = {n0}")
print(f"答案：n0 = {n0}")
print()

# ========== 选项构造 ==========
print("========== 选项构造 ==========")
print(f"正确值 (n0 = n2+1):      {r['correct']}")
print(f"干扰B (取n2不加1):       {r['dist_B']}")
print(f"干扰C (误用n1+1):        {r['dist_C']}")
print(f"干扰D (未除以2, n-n1-1): {r['dist_D']}")
print()

# 随机排列正确答案到 A/B/C/D
correct_val = r['correct']
distractors = [r['dist_B'], r['dist_C'], r['dist_D']]
random.seed(42)
all_options = distractors + [correct_val]
random.shuffle(all_options)
labels = ['A', 'B', 'C', 'D']
for label, val in zip(labels, all_options):
    marker = " ← 正确" if val == correct_val else ""
    print(f"  {label}. {val}{marker}")
