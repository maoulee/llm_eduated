"""系统搜索能触发所有四种旋转的最短序列"""

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

def right_rotate(z):
    y = z.left
    T3 = y.right
    y.right = z
    z.left = T3
    update_height(z)
    update_height(y)
    return y

def left_rotate(z):
    y = z.right
    T2 = y.left
    y.left = z
    z.right = T2
    update_height(z)
    update_height(y)
    return y

def insert_with_log(root, key):
    """插入并记录旋转类型"""
    if not root:
        return Node(key), None
    if key < root.key:
        root.left, rot = insert_with_log(root.left, key)
    else:
        root.right, rot = insert_with_log(root.right, key)
    
    update_height(root)
    balance = get_balance(root)
    
    # LL
    if balance > 1 and key < root.left.key:
        return right_rotate(root), 'LL'
    # RR
    if balance < -1 and key > root.right.key:
        return left_rotate(root), 'RR'
    # LR
    if balance > 1 and key > root.left.key:
        root.left = left_rotate(root.left)
        return right_rotate(root), 'LR'
    # RL
    if balance < -1 and key < root.right.key:
        root.right = right_rotate(root.right)
        return left_rotate(root), 'RL'
    
    return root, None

def inorder(root, result=None):
    if result is None:
        result = []
    if root:
        inorder(root.left, result)
        result.append(root.key)
        inorder(root.right, result)
    return result

def print_tree(node, prefix="", is_left=True):
    if node:
        print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
        print(prefix + ("└── " if is_left else "┌── ") + str(node.key) + f" (h={node.height}, bf={get_balance(node)})")
        print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

# 尝试更多序列
test_sequences = [
    # 尝试触发所有四种
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 55],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 2],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 3],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 28],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 32],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 26],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 23],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 14],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 7],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 1],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 55, 2],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 55, 3],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 55, 28],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 55, 32],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 55, 26],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 55, 23],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 55, 14],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 55, 7],
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 55, 1],
]

for i, seq in enumerate(test_sequences):
    root = None
    rotations = []
    for key in seq:
        root, rot = insert_with_log(root, key)
        if rot:
            rotations.append((key, rot))
    
    rotation_types = set(r[1] for r in rotations)
    all_four = rotation_types == {'LL', 'RR', 'LR', 'RL'}
    
    if all_four:
        print(f"\n*** 找到! 序列 {i+1}: {seq}")
        print(f"旋转记录: {rotations}")
        print(f"中序遍历: {inorder(root)}")
        print(f"树的高度: {get_height(root)}")
        print("树结构:")
        print_tree(root)
        break
    else:
        print(f"序列 {i+1}: {seq} -> 旋转类型: {rotation_types}")
