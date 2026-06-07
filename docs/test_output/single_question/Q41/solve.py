# ===== AVL树实现 =====

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

def right_rotate(y):
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    y.height = 1 + max(get_height(y.left), get_height(y.right))
    x.height = 1 + max(get_height(x.left), get_height(x.right))
    return x

def left_rotate(x):
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    x.height = 1 + max(get_height(x.left), get_height(x.right))
    y.height = 1 + max(get_height(y.left), get_height(y.right))
    return y

def insert(node, key):
    # 普通BST插入
    if not node:
        return Node(key)
    if key < node.key:
        node.left = insert(node.left, key)
    elif key > node.key:
        node.right = insert(node.right, key)
    else:
        return node  # 不插入重复值
    
    # 更新高度
    node.height = 1 + max(get_height(node.left), get_height(node.right))
    
    # 获取平衡因子
    balance = get_balance(node)
    
    # LL情况
    if balance > 1 and key < node.left.key:
        return right_rotate(node)
    
    # RR情况
    if balance < -1 and key > node.right.key:
        return left_rotate(node)
    
    # LR情况
    if balance > 1 and key > node.left.key:
        node.left = left_rotate(node.left)
        return right_rotate(node)
    
    # RL情况
    if balance < -1 and key < node.right.key:
        node.right = right_rotate(node.right)
        return left_rotate(node)
    
    return node

def preorder(node, result):
    if node:
        result.append(node.key)
        preorder(node.left, result)
        preorder(node.right, result)

def print_tree(node, prefix="", is_left=True):
    """打印树结构用于调试"""
    if node:
        print(f"{prefix}{'├── ' if is_left else '└── '}{node.key} (h={node.height}, bal={get_balance(node)})")
        if node.left or node.right:
            extension = "│   " if is_left else "    "
            print_tree(node.left, prefix + extension, True)
            print_tree(node.right, prefix + extension, False)

# ===== 题目参数定义 =====
keys = [30, 10, 50, 20, 40]

# ===== 依次插入并打印中间状态 =====
root = None
for i, key in enumerate(keys):
    root = insert(root, key)
    print(f"插入 {key} 后:")
    print_tree(root)
    print()

# ===== 前序遍历 =====
result = []
preorder(root, result)
print(f"前序遍历序列: {result}")
print(f"ANSWER: {result}")
