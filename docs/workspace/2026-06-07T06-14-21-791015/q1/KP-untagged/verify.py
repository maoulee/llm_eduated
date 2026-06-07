"""
独立验证AVL树插入过程
"""

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1
    
    def __repr__(self):
        return f"Node({self.key})"

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
    """右旋：z为失衡节点"""
    y = z.left
    T3 = y.right
    
    y.right = z
    z.left = T3
    
    update_height(z)
    update_height(y)
    
    return y

def left_rotate(z):
    """左旋：z为失衡节点"""
    y = z.right
    T2 = y.left
    
    y.left = z
    z.right = T2
    
    update_height(z)
    update_height(y)
    
    return y

def insert(node, key):
    # 标准BST插入
    if not node:
        return Node(key)
    
    if key < node.key:
        node.left = insert(node.left, key)
    elif key > node.key:
        node.right = insert(node.right, key)
    else:
        return node  # 不允许重复
    
    update_height(node)
    balance = get_balance(node)
    
    # LL
    if balance > 1 and key < node.left.key:
        return right_rotate(node)
    
    # RR
    if balance < -1 and key > node.right.key:
        return left_rotate(node)
    
    # LR
    if balance > 1 and key > node.left.key:
        node.left = left_rotate(node.left)
        return right_rotate(node)
    
    # RL
    if balance < -1 and key < node.right.key:
        node.right = right_rotate(node.right)
        return left_rotate(node)
    
    return node

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
        print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
        print(prefix + ("└── " if is_left else "┌── ") + str(node.key))
        print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

def get_all_balances(node):
    """获取所有节点的平衡因子"""
    result = {}
    if node:
        result[node.key] = get_balance(node)
        result.update(get_all_balances(node.left))
        result.update(get_all_balances(node.right))
    return result

def get_non_leaf_balances(node):
    """获取所有非叶子节点的平衡因子"""
    result = {}
    if node:
        is_leaf = (node.left is None and node.right is None)
        if not is_leaf:
            result[node.key] = get_balance(node)
        result.update(get_non_leaf_balances(node.left))
        result.update(get_non_leaf_balances(node.right))
    return result

def is_avl(node):
    """检查是否为合法AVL树"""
    if not node:
        return True
    balance = get_balance(node)
    if abs(balance) > 1:
        return False
    return is_avl(node.left) and is_avl(node.right)

# 构建初始树
root = Node(10)
root.left = Node(5)
root.right = Node(15)
root.left.left = Node(3)
root.left.right = Node(7)
root.right.left = Node(12)
root.right.right = Node(18)

# 更新高度
for node in [root.left.left, root.left.right, root.right.left, root.right.right, root.left, root.right, root]:
    update_height(node)

print("=" * 60)
print("初始树")
print("=" * 60)
print("所有节点平衡因子:", get_all_balances(root))
print("是否为合法AVL树:", is_avl(root))
print("中序遍历:", inorder(root))
print()

# 插入2
print("=" * 60)
print("插入2后")
print("=" * 60)
root = insert(root, 2)
print("所有节点平衡因子:", get_all_balances(root))
print("非叶子节点平衡因子:", get_non_leaf_balances(root))
print("是否为合法AVL树:", is_avl(root))
print("中序遍历:", inorder(root))
print()

# 插入1
print("=" * 60)
print("插入1后")
print("=" * 60)
root = insert(root, 1)
print("所有节点平衡因子:", get_all_balances(root))
print("非叶子节点平衡因子:", get_non_leaf_balances(root))
print("是否为合法AVL树:", is_avl(root))
print("中序遍历:", inorder(root))
print("树结构:")
print_tree(root)
print()

# 插入14
print("=" * 60)
print("插入14后")
print("=" * 60)
root = insert(root, 14)
print("所有节点平衡因子:", get_all_balances(root))
print("非叶子节点平衡因子:", get_non_leaf_balances(root))
print("是否为合法AVL树:", is_avl(root))
print("中序遍历:", inorder(root))
print("树结构:")
print_tree(root)
