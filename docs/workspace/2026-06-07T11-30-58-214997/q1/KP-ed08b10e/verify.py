# ===== 题目参数 =====
page_sequence = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]

# ===== 校验1：参数封闭性 =====
# 页面访问序列已给出，物理块数量在叙述中给出（3块、4块）
# 所有必要参数都在题干中

# ===== 校验2：序列长度 =====
print(f"页面访问序列: {page_sequence}")
print(f"序列长度: {len(page_sequence)}")
print(f"不同页面数: {len(set(page_sequence))}")

# ===== 校验3：物理块数量合理性 =====
# 3块和4块都小于不同页面数(5)，所以会发生缺页
assert 3 < len(set(page_sequence)), "3块物理块应小于页面总数"
assert 4 < len(set(page_sequence)), "4块物理块应小于页面总数"

print("参数校验通过")
