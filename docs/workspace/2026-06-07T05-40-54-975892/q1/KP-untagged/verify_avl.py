"""
AVL树插入序列验证脚本
目标：设计一个插入序列，触发LL、RR、LR、RL四种旋转
"""

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    if not node:
        return 0
    return node.height

def get_balance(node):
    if not node:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(y):
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    update_height(y)
    update_height(x)
    return x

def left_rotate(x):
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    update_height(x)
    update_height(y)
    return y

def insert(root, key):
    rotations = []
    # 普通BST插入
    if not root:
        return Node(key), rotations
    
    if key < root.key:
        root.left, r = insert(root.left, key)
        rotations.extend(r)
    elif key > root.key:
        root.right, r = insert(root.right, key)
        rotations.extend(r)
    else:
        return root, rotations  # 不允许重复
    
    update_height(root)
    balance = get_balance(root)
    
    # LL
    if balance > 1 and key < root.left.key:
        rotations.append(("LL", root.key))
        return right_rotate(root), rotations
    # RR
    if balance < -1 and key > root.right.key:
        rotations.append(("RR", root.key))
        return left_rotate(root), rotations
    # LR
    if balance > 1 and key > root.left.key:
        rotations.append(("LR", root.key))
        root.left = left_rotate(root.left)
        return right_rotate(root), rotations
    # RL
    if balance < -1 and key < root.right.key:
        rotations.append(("RL", root.key))
        root.right = right_rotate(root.right)
        return left_rotate(root), rotations
    
    return root, rotations

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def print_tree(node, prefix="", is_left=True):
    if node:
        print_tree(node.right, prefix + ("│        " if is_left else "        "), False)
        print(prefix + ("└── " if is_left else "┌── ") + str(node.key))
        print_tree(node.left, prefix + ("        " if is_left else "│        "), True)

# 设计能触发四种旋转的序列
# 思路：
# LL: 先插右子节点，再插左子节点的左孩子 → 如 30, 20, 10
# RR: 先插左子节点，再插右子节点的右孩子 → 如 30, 40, 50
# LR: 先插左子节点，再插左子节点的右孩子 → 如 30, 20, 25
# RL: 先插右子节点，再插右子节点的左孩子 → 如 30, 40, 35

# 关键：需要在一个序列中交替触发
# 策略：构建一棵树，在不同分支上分别触发不同旋转

# 序列设计：
# 1. 插入 30 (根)
# 2. 插入 20 (左子)
# 3. 插入 40 (右子)
# 4. 插入 10 (20的左子) → 此时 30的左子树高度2，右子树高度1，平衡因子1，不旋转
# 5. 插入 5 (10的左子) → 30的左子树高度3，右子树高度1，平衡因子2 → LL旋转(30)
# 6. 插入 50 (40的右子) → 可能触发RR
# 7. 插入 25 (20的右子) → 可能触发LR
# 8. 插入 35 (40的左子) → 可能触发RL

# 让我用更系统的方法：
# 先触发LL: 30, 20, 10 → LL at 30
# 然后触发RR: 需要右子树不平衡 → 30, 20, 10, 40, 50 → RR at 30
# 然后触发LR: 需要左子节点有右孩子 → 30, 20, 25 → LR at 30
# 然后触发RL: 需要右子节点有左孩子 → 30, 40, 35 → RL at 30

# 问题：每次旋转后树结构改变，需要在新结构上继续触发

# 更好的策略：在不同子树上分别触发
# 根节点触发一种，左子树触发一种，右子树触发一种

# 尝试序列：
# 1. 30 (根)
# 2. 20 (左)
# 3. 40 (右)
# 4. 10 (20的左) → 树: 30(左:20(左:10), 右:40)，平衡
# 5. 5 (10的左) → 30的左子树高3，右子树高1 → LL at 30
#    旋转后: 20(左:10(左:5), 右:30(右:40))
# 6. 50 (40的右) → 30的右子树高2，20的右子树高2 → 平衡
# 7. 60 (50的右) → 30的右子树高3 → RR at 30? 需要检查
#    20(左:10(左:5), 右:30(右:40(右:50(右:60))))
#    30的平衡因子 = 0-3 = -3? 不对，需要重新计算

# 让我用代码暴力搜索

import itertools

def test_sequence(seq):
    root = None
    all_rotations = []
    for key in seq:
        root, rotations = insert(root, key)
        for r in rotations:
            all_rotations.append((key, r[0], r[1]))
    rot_types = set(r[1] for r in all_rotations)
    return rot_types, all_rotations, inorder(root)

# 手动设计几个候选序列
candidates = [
    # 序列A: 尝试在不同子树触发
    [30, 20, 40, 10, 5, 50, 60, 25, 35, 15],
    # 序列B
    [30, 20, 40, 10, 5, 50, 60, 25, 15, 35],
    # 序列C
    [50, 30, 70, 20, 10, 80, 90, 25, 35, 40],
    # 序列D
    [40, 20, 60, 10, 5, 70, 80, 25, 35, 50],
    # 序列E: 先构建平衡树，再在叶子处触发
    [30, 20, 40, 10, 25, 35, 50, 5, 45, 55],
    # 序列F
    [30, 40, 20, 50, 10, 35, 25, 45, 5, 15],
    # 序列G
    [50, 25, 75, 10, 35, 60, 80, 5, 15, 30],
    # 序列H
    [40, 20, 60, 10, 30, 50, 70, 5, 25, 55],
    # 序列I
    [30, 20, 40, 10, 25, 35, 50, 15, 5, 45],
    # 序列J
    [50, 30, 70, 20, 40, 60, 80, 10, 25, 35],
    # 序列K: 更小的数字
    [8, 4, 12, 2, 6, 10, 14, 1, 3, 5],
    # 序列L
    [8, 4, 12, 2, 6, 10, 14, 3, 5, 7],
    # 序列M
    [8, 12, 4, 14, 2, 10, 6, 16, 1, 3],
    # 序列N
    [10, 5, 15, 3, 7, 12, 18, 1, 4, 6],
    # 序列O
    [10, 5, 15, 3, 7, 12, 18, 4, 6, 8],
    # 序列P
    [10, 15, 5, 18, 3, 12, 7, 20, 1, 2],
    # 序列Q
    [10, 5, 15, 3, 7, 12, 18, 2, 4, 6],
    # 序列R
    [10, 5, 15, 3, 7, 12, 18, 1, 4, 8],
    # 序列S
    [10, 5, 15, 3, 7, 12, 18, 1, 4, 9],
    # 序列T
    [10, 5, 15, 3, 7, 12, 18, 1, 4, 11],
]

for name, seq in [("A", [30, 20, 40, 10, 5, 50, 60, 25, 35, 15]),
                   ("B", [30, 20, 40, 10, 5, 50, 60, 25, 15, 35]),
                   ("C", [50, 30, 70, 20, 10, 80, 90, 25, 35, 40]),
                   ("D", [40, 20, 60, 10, 5, 70, 80, 25, 35, 50]),
                   ("E", [30, 20, 40, 10, 25, 35, 50, 5, 45, 55]),
                   ("F", [30, 40, 20, 50, 10, 35, 25, 45, 5, 15]),
                   ("G", [50, 25, 75, 10, 35, 60, 80, 5, 15, 30]),
                   ("H", [40, 20, 60, 10, 30, 50, 70, 5, 25, 55]),
                   ("I", [30, 20, 40, 10, 25, 35, 50, 15, 5, 45]),
                   ("J", [50, 30, 70, 20, 40, 60, 80, 10, 25, 35]),
                   ("K", [8, 4, 12, 2, 6, 10, 14, 1, 3, 5]),
                   ("L", [8, 4, 12, 2, 6, 10, 14, 3, 5, 7]),
                   ("M", [8, 12, 4, 14, 2, 10, 6, 16, 1, 3]),
                   ("N", [10, 5, 15, 3, 7, 12, 18, 1, 4, 6]),
                   ("O", [10, 5, 15, 3, 7, 12, 18, 4, 6, 8]),
                   ("P", [10, 15, 5, 18, 3, 12, 7, 20, 1, 2]),
                   ("Q", [10, 5, 15, 3, 7, 12, 18, 2, 4, 6]),
                   ("R", [10, 5, 15, 3, 7, 12, 18, 1, 4, 8]),
                   ("S", [10, 5, 15, 3, 7, 12, 18, 1, 4, 9]),
                   ("T", [10, 5, 15, 3, 7, 12, 18, 1, 4, 11])]:
    rot_types, all_rotations, inorder_result = test_sequence(seq)
    has_all = rot_types == {"LL", "RR", "LR", "RL"}
    print(f"\n序列{name}: {seq}")
    print(f"旋转记录: {all_rotations}")
    print(f"旋转类型: {rot_types}")
    print(f"覆盖全部四种: {has_all}")
    if has_all:
        print("✓✓✓ 找到满足条件的序列！")
