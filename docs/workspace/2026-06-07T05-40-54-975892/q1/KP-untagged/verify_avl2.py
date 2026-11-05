"""
AVL树插入序列验证脚本 - 版本2
目标：设计一个插入序列，触发LL、RR、LR、RL四种旋转
使用更系统的搜索方法
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
    if not root:
        return Node(key), rotations
    
    if key < root.key:
        root.left, r = insert(root.left, key)
        rotations.extend(r)
    elif key > root.key:
        root.right, r = insert(root.right, key)
        rotations.extend(r)
    else:
        return root, rotations
    
    update_height(root)
    balance = get_balance(root)
    
    if balance > 1 and key < root.left.key:
        rotations.append(("LL", root.key))
        return right_rotate(root), rotations
    if balance < -1 and key > root.right.key:
        rotations.append(("RR", root.key))
        return left_rotate(root), rotations
    if balance > 1 and key > root.left.key:
        rotations.append(("LR", root.key))
        root.left = left_rotate(root.left)
        return right_rotate(root), rotations
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

def test_sequence(seq):
    root = None
    all_rotations = []
    for key in seq:
        root, rotations = insert(root, key)
        for r in rotations:
            all_rotations.append((key, r[0], r[1]))
    rot_types = set(r[1] for r in all_rotations)
    return rot_types, all_rotations, inorder(root)

# 关键洞察：LR和RL旋转需要"之字形"插入
# LR: 先插左孩子，再插左孩子的右孙子
# RL: 先插右孩子，再插右孩子的左孙子

# 策略：构建一棵树，使得在不同阶段触发不同旋转
# 1. 先构建基础结构
# 2. 在左子树触发LL
# 3. 在右子树触发RR
# 4. 在某个子树触发LR
# 5. 在某个子树触发RL

# 尝试序列：使用12个节点，增加触发机会
candidates = [
    # 序列1: 尝试在左子树触发LR
    [30, 20, 40, 10, 25, 5, 35, 50, 15, 45, 55, 2],
    # 序列2: 尝试在右子树触发RL
    [30, 20, 40, 10, 35, 5, 50, 25, 15, 45, 55, 2],
    # 序列3: 交替插入
    [30, 20, 40, 25, 10, 35, 5, 50, 15, 45, 55, 2],
    # 序列4: 先右后左
    [30, 40, 20, 35, 50, 10, 25, 5, 45, 15, 55, 2],
    # 序列5: 更小的数字
    [8, 4, 12, 6, 2, 10, 14, 5, 7, 1, 3, 11],
    # 序列6
    [8, 4, 12, 6, 2, 10, 14, 5, 7, 1, 3, 9],
    # 序列7
    [8, 12, 4, 10, 14, 2, 6, 1, 3, 5, 7, 11],
    # 序列8
    [10, 5, 15, 3, 7, 12, 18, 1, 4, 6, 8, 14],
    # 序列9
    [10, 5, 15, 3, 7, 12, 18, 2, 4, 6, 8, 16],
    # 序列10
    [10, 15, 5, 12, 18, 3, 7, 1, 4, 6, 8, 14],
    # 序列11: 尝试触发RL
    [30, 40, 20, 35, 50, 10, 25, 5, 45, 15, 55, 2],
    # 序列12
    [30, 40, 20, 35, 50, 10, 25, 5, 45, 15, 55, 25],
    # 序列13: 10个节点
    [30, 20, 40, 25, 10, 35, 5, 50, 15, 45],
    # 序列14
    [30, 40, 20, 35, 10, 25, 5, 50, 15, 45],
    # 序列15
    [30, 20, 40, 10, 35, 5, 50, 25, 15, 45],
    # 序列16
    [30, 40, 20, 35, 10, 25, 5, 50, 15, 45],
    # 序列17
    [50, 25, 75, 10, 35, 60, 80, 5, 15, 30],
    # 序列18
    [50, 25, 75, 10, 35, 60, 80, 5, 15, 40],
    # 序列19
    [50, 25, 75, 10, 35, 60, 80, 5, 20, 30],
    # 序列20
    [50, 25, 75, 10, 35, 60, 80, 5, 20, 40],
]

for i, seq in enumerate(candidates):
    rot_types, all_rotations, inorder_result = test_sequence(seq)
    has_all = rot_types == {"LL", "RR", "LR", "RL"}
    print(f"\n序列{i+1}: {seq}")
    print(f"旋转记录: {all_rotations}")
    print(f"旋转类型: {rot_types}")
    print(f"覆盖全部四种: {has_all}")
    if has_all:
        print("✓✓✓ 找到满足条件的序列！")
