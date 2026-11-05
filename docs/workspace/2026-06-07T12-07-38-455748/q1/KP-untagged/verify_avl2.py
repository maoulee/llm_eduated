"""寻找最短的能触发所有四种旋转的AVL插入序列"""

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

def insert(root, key):
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
        return right_rotate(root)
    # RR
    if balance < -1 and key > root.right.key:
        return left_rotate(root)
    # LR
    if balance > 1 and key > root.left.key:
        root.left = left_rotate(root.left)
        return right_rotate(root)
    # RL
    if balance < -1 and key < root.right.key:
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

# 尝试更短的序列
test_sequences = [
    # 尝试1: 10个节点
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 50],
    # 尝试2: 10个节点
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 55],
    # 尝试3: 10个节点
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 28],
    # 尝试4: 10个节点
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 32],
    # 尝试5: 10个节点
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 2],
    # 尝试6: 10个节点
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 3],
    # 尝试7: 10个节点
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 26],
    # 尝试8: 10个节点
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 23],
    # 尝试9: 10个节点
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 14],
    # 尝试10: 10个节点
    [30, 20, 40, 10, 25, 5, 35, 15, 45, 7],
]

for i, seq in enumerate(test_sequences):
    rotations = []
    root = None
    for key in seq:
        root = insert(root, key)
    
    rotation_types = set()
    # 重新插入以记录旋转
    root = None
    for key in seq:
        root = insert(root, key)
    
    print(f"\n序列 {i+1}: {seq}")
    print(f"中序遍历: {inorder(root)}")
    print(f"树的高度: {get_height(root)}")

# 现在用详细模式测试序列1
print("\n" + "="*60)
print("详细分析序列1: [30, 20, 40, 10, 25, 5, 35, 15, 45, 50]")
print("="*60)

seq = [30, 20, 40, 10, 25, 5, 35, 15, 45, 50]
root = None
for j, key in enumerate(seq):
    root = insert(root, key)
    print(f"\n插入 {key} 后:")
    print_tree(root)
