"""验证AVL插入序列是否能触发所有四种旋转"""

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

rotations = []

def insert(root, key):
    global rotations
    if not root:
        return Node(key)
    if key < root.key:
        root.left = insert(root.left, key)
    else:
        root.right = insert(root.right, key)
    
    update_height(root)
    balance = get_balance(root)
    
    # LL
    if balance > 1 and key < root.left.key:
        rotations.append(('LL', root.key, key))
        return right_rotate(root)
    # RR
    if balance < -1 and key > root.right.key:
        rotations.append(('RR', root.key, key))
        return left_rotate(root)
    # LR
    if balance > 1 and key > root.left.key:
        rotations.append(('LR', root.key, key))
        root.left = left_rotate(root.left)
        return right_rotate(root)
    # RL
    if balance < -1 and key < root.right.key:
        rotations.append(('RL', root.key, key))
        root.right = right_rotate(root.right)
        return left_rotate(root)
    
    return root

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

# 测试序列
test_sequences = [
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50, 55, 2, 3, 28, 1, 7, 14, 23, 26, 32],
    [50, 25, 75, 12, 37, 62, 87, 6, 18, 31, 43, 56, 68, 72, 78, 81, 84],
    [10, 20, 30, 40, 50, 25, 5, 35, 15, 45, 55, 2, 8, 12, 18, 22, 28, 32, 38, 42],
]

for i, seq in enumerate(test_sequences):
    rotations = []
    root = None
    for key in seq:
        root = insert(root, key)
    
    rotation_types = set(r[0] for r in rotations)
    print(f"\n序列 {i+1}: {seq}")
    print(f"旋转记录: {rotations}")
    print(f"旋转类型: {rotation_types}")
    print(f"中序遍历: {inorder(root)}")
    print(f"树的高度: {get_height(root)}")
    print("树结构:")
    print_tree(root)
