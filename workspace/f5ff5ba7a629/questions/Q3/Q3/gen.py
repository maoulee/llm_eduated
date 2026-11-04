"""
Q3 选择题：二维数组列优先存储地址计算
gen.py：建模约束 + 给初始值 + 模拟机制 + 验证四选项互不相同
"""

import math

# ============ 初始值（LLM 大胆给）============
m = 5        # 行数 (非2的幂次，满足"数字非完全友好")
n = 7        # 列数 (非2的幂次，与m无固定比例关系)
s = 4        # 每个元素存储单元数 ∈ {2,4,8}
BASE = 200   # 基地址 100~9999
k_start = 1  # 下标起始值 0 或 1，这里选 1
# 目标元素非退化：不取首元素也不取末元素
# 需要 (j-k)*(m-1) != (i-k)*(n-1) 使正确答案与行优先干扰不同
#   (j-k)*(5-1) != (i-k)*(7-1) → 4*(j-1) != 6*(i-1)
# i=2,j=3: 4*2=8 vs 6*1=6 → 不同 ✓
i = 2       # 目标行下标 (非首行非末行)
j = 3       # 目标列下标 (非首列非末列)

# ============ 约束检查 ============
assert 3 <= m <= 10, f"m={m} 不在 3~10"
assert 3 <= n <= 10, f"n={n} 不在 3~10"
assert m * n <= 100, f"m*n={m*n} > 100"
assert s in {2, 4, 8}, f"s={s} 不在 {{2,4,8}}"
assert 100 <= BASE <= 9999, f"BASE={BASE} 不在 100~9999"
assert k_start in {0, 1}, f"k_start={k_start} 不在 {{0,1}}"

# 非退化检查：目标元素不取首元素(i=i0,j=j0)也不取末元素(i=m-1+k_start,j=n-1+k_start)
i0, j0 = k_start, k_start
assert not (i == i0 and j == j0), "目标元素为首元素，退化"
assert not (i == m - 1 + k_start and j == n - 1 + k_start), "目标元素为末元素，退化"
# 行列下标在合法范围
assert k_start <= i <= m - 1 + k_start, f"行下标 i={i} 越界"
assert k_start <= j <= n - 1 + k_start, f"列下标 j={j} 越界"

# 数字非完全友好：m, n 至少一个非2的幂次
def is_power_of_two(x):
    return x > 0 and (x & (x - 1)) == 0
assert not (is_power_of_two(m) and is_power_of_two(n)), "m和n都是2的幂次，太友好"

# ============ 求解：四个公式的计算结果 ============

# 正确答案（列优先）: BASE + ((j - k_start) * m + (i - k_start)) * s
correct = BASE + ((j - k_start) * m + (i - k_start)) * s

# 干扰B（行优先混淆）: BASE + ((i - k_start) * n + (j - k_start)) * s
distract_B = BASE + ((i - k_start) * n + (j - k_start)) * s

# 干扰C（下标起始忽略）: BASE + (j * m + i) * s
distract_C = BASE + (j * m + i) * s

# 干扰D（行列互换）: BASE + ((j - k_start) * n + (i - k_start)) * s
distract_D = BASE + ((j - k_start) * n + (i - k_start)) * s

# ============ 验证四选项两两不同 ============
values = {
    "正确(列优先)": correct,
    "干扰B(行优先混淆)": distract_B,
    "干扰C(下标起始忽略)": distract_C,
    "干扰D(行列互换)": distract_D,
}

print("=" * 60)
print(f"参数: m={m}, n={n}, s={s}, BASE={BASE}, k_start={k_start}")
print(f"目标元素: A[{i}][{j}]")
print("=" * 60)

for label, val in values.items():
    print(f"  {label}: {val}")

print()
all_vals = list(values.values())
all_distinct = len(set(all_vals)) == 4
print(f"四选项两两不同: {all_distinct}")

# 验证计算过程
print("\n--- 计算过程 ---")
di = i - k_start
dj = j - k_start
print(f"行偏移 di = i - k_start = {i} - {k_start} = {di}")
print(f"列偏移 dj = j - k_start = {j} - {k_start} = {dj}")
print(f"列优先前置元素数 = dj × m + di = {dj} × {m} + {di} = {dj*m + di}")
print(f"地址偏移 = {dj*m + di} × s = {dj*m + di} × {s} = {(dj*m + di)*s}")
print(f"正确地址 = BASE + {(dj*m + di)*s} = {BASE} + {(dj*m + di)*s} = {correct}")

print("\n--- 选项构造 ---")
print(f"  正确答案 = {correct}")
print(f"  干扰B(行优先) = {distract_B}")
print(f"  干扰C(忽略起始) = {distract_C}")
print(f"  干扰D(行列互换) = {distract_D}")

# 打乱选项字母分配
import random
random.seed(42)
options_pool = [
    (correct, "正确答案"),
    (distract_B, "行优先混淆"),
    (distract_C, "下标起始忽略"),
    (distract_D, "行列互换"),
]
random.shuffle(options_pool)
letters = ['A', 'B', 'C', 'D']
print("\n--- 最终选项分配 ---")
correct_letter = None
for idx, (val, desc) in enumerate(options_pool):
    letter = letters[idx]
    marker = " ← 正确" if desc == "正确答案" else ""
    print(f"  {letter}. {val}  ({desc}){marker}")
    if desc == "正确答案":
        correct_letter = letter

print(f"\n正确选项: {correct_letter}")
print(f"四选项两两不同验证通过: {all_distinct}")
assert all_distinct, "四选项有重合！需要调整参数"
print("\n✅ 所有验证通过")
