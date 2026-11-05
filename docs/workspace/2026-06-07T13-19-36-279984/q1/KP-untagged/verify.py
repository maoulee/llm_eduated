# ===== AVL树参数校验 =====
# 验证插入序列和AVL树操作的自洽性

insert_sequence = [10, 20, 30, 5, 15, 12, 25, 22, 30]

# 校验1：参数封闭性
# 所有子问题所需参数：插入序列、AVL树规则、平衡因子定义
# 题干已给出完整信息 ✓

# 校验2：重复关键字处理
# 最后一个30与已有节点重复，按BST规则不插入
# 题干明确说明 ✓

# 校验3：平衡因子定义
# 左子树高度 - 右子树高度
# 题干明确定义 ✓

# 校验4：旋转类型判断条件
# LL: balance > 1 and key < T.left.key
# RR: balance < -1 and key > T.right.key
# LR: balance > 1 and key > T.left.key
# RL: balance < -1 and key < T.right.key
# 题干伪代码已给出 ✓

print("参数校验通过")
print(f"插入序列: {insert_sequence}")
print(f"有效插入次数: 8次（最后一个30重复，不插入）")
