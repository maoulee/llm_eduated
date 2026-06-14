# -*- coding: utf-8 -*-
"""
solve.py — 正确算法 DAG（§17.5）
二叉树遍历序列还原综合题
只算正确答案，不编码错误算法/干扰值。
"""

# ============================================================
# 初始参数（设计选择，非计算）
# 树结构：
#         A
#        / \
#       B   C
#      /   / \
#     D   E   F
#          \
#           G
# ============================================================

tree = {
    'A': ('B', 'C'),
    'B': ('D', None),
    'C': ('E', 'F'),
    'D': (None, None),
    'E': (None, 'G'),
    'F': (None, None),
    'G': (None, None),
}

ROOT = 'A'
THREADING_TARGET = 'E'

# ============================================================
# DAG 节点 1：遍历序列计算
# ============================================================

def preorder(node, tree, result):
    if node is None:
        return
    result.append(node)
    left, right = tree[node]
    preorder(left, tree, result)
    preorder(right, tree, result)

def inorder(node, tree, result):
    if node is None:
        return
    left, right = tree[node]
    inorder(left, tree, result)
    result.append(node)
    inorder(right, tree, result)

def postorder(node, tree, result):
    if node is None:
        return
    left, right = tree[node]
    postorder(left, tree, result)
    postorder(right, tree, result)
    result.append(node)

pre_list = []
in_list = []
post_list = []
preorder(ROOT, tree, pre_list)
inorder(ROOT, tree, in_list)
postorder(ROOT, tree, post_list)

preorder_seq = ''.join(pre_list)
inorder_seq = ''.join(in_list)
postorder_seq = ''.join(post_list)

# ============================================================
# DAG 节点 2：树性质计算
# ============================================================

def compute_height(node, tree):
    if node is None:
        return 0
    left, right = tree[node]
    return 1 + max(compute_height(left, tree), compute_height(right, tree))

def count_leaves(node, tree):
    if node is None:
        return 0
    left, right = tree[node]
    if left is None and right is None:
        return 1
    return count_leaves(left, tree) + count_leaves(right, tree)

height = compute_height(ROOT, tree)
leaf_count = count_leaves(ROOT, tree)

degree1_nodes = [n for n in tree
                 if (tree[n][0] is not None) != (tree[n][1] is not None)]
degree1_count = len(degree1_nodes)

# ============================================================
# DAG 节点 3：中序线索化分析（目标节点）
# ============================================================

target = THREADING_TARGET
t_left, t_right = tree[target]

# --- 中序前驱 ---
if t_left is not None:
    # 有左孩子：前驱 = 左子树最右下节点（沿 rchild 下行）
    pred = t_left
    while tree[pred][1] is not None:
        pred = tree[pred][1]
    pred_via = "孩子指针（左子树最右下节点，ltag=0）"
else:
    # 无左孩子：前驱通过线索指针（ltag=1）
    idx = in_list.index(target)
    pred = in_list[idx - 1] if idx > 0 else None
    pred_via = "线索指针（ltag=1，lchild 指向前驱）"

# --- 中序后继 ---
if t_right is not None:
    # 有右孩子：后继 = 右子树最左下节点（沿 lchild 下行）
    succ = t_right
    while tree[succ][0] is not None:
        succ = tree[succ][0]
    succ_via = "孩子指针（右子树最左下节点，rtag=0）"
else:
    # 无右孩子：后继通过线索指针（rtag=1）
    idx = in_list.index(target)
    succ = in_list[idx + 1] if idx < len(in_list) - 1 else None
    succ_via = "线索指针（rtag=1，rchild 指向后继）"

# ============================================================
# DAG 节点 4：参数约束验证
# ============================================================

assert len(preorder_seq) == len(inorder_seq), \
    "先序与中序长度不一致"
assert set(preorder_seq) == set(inorder_seq), \
    "先序与中序元素集合不一致"
assert 7 <= len(preorder_seq) <= 11, \
    f"节点数 N={len(preorder_seq)} 不在 [7, 11]"
assert 3 <= height <= 4, \
    f"树高 H={height} 不在 [3, 4]"
assert leaf_count >= 3, \
    f"叶子节点数 {leaf_count} < 3"
assert degree1_count >= 1, \
    f"度为1的节点数 {degree1_count} < 1"
assert target != ROOT, \
    "线索化目标节点是根节点"
assert tree[target] != (None, None), \
    "线索化目标节点是叶子节点"

# 非完全二叉树检查：同一层节点不能填满
# （本题树形态由设计保证，此处仅做基本验证）
all_nodes = list(tree.keys())
assert len(all_nodes) >= 7, "节点数不足"

# ============================================================
# 输出正确答案
# ============================================================

print("=" * 60)
print("参数验证")
print("=" * 60)
print(f"先序遍历序列: {preorder_seq}")
print(f"中序遍历序列: {inorder_seq}")
print(f"元素集合一致: {set(preorder_seq) == set(inorder_seq)}")
print(f"节点数 N: {len(preorder_seq)}")
print(f"树高 H: {height}")
print(f"叶子节点数: {leaf_count}")
print(f"度为1的节点: {degree1_nodes} (共 {degree1_count} 个)")
print()

print("=" * 60)
print("正确答案")
print("=" * 60)

# Q1: 树结构
print(f"Q1 正确: 二叉树结构（各节点左右孩子关系）")
print(f"  A: 左孩子=B, 右孩子=C")
print(f"  B: 左孩子=D, 右孩子=无")
print(f"  C: 左孩子=E, 右孩子=F")
print(f"  D: 叶子")
print(f"  E: 左孩子=无, 右孩子=G")
print(f"  F: 叶子")
print(f"  G: 叶子")
print()

# Q2: 后序遍历序列
print(f"Q2 正确: 后序遍历序列 = {postorder_seq}")
print()

# Q3: 树高和叶子数
print(f"Q3 正确: 树高 = {height}, 叶子节点数 = {leaf_count}")
print()

# Q4: 中序线索化分析
print(f"Q4 正确: 节点 {target} 的中序线索化分析")
print(f"  中序前驱: {pred}")
print(f"    到达方式: {pred_via}")
print(f"  中序后继: {succ}")
print(f"    到达方式: {succ_via}")
print()

# 线索化目标节点约束验证
target_parent = None
for n in tree:
    if tree[n][0] == target or tree[n][1] == target:
        target_parent = n
        break
print(f"  [验证] {target} 的父节点: {target_parent}")
print(f"  [验证] 前驱 {pred} 是否 {target} 的直接父子: "
      f"{'是' if pred == target_parent or tree[target][0] == pred or tree[target][1] == pred else '否'}")
print(f"  [验证] 后继 {succ} 是否 {target} 的直接父子: "
      f"{'是' if succ == target_parent or tree[target][0] == succ or tree[target][1] == succ else '否'}")
