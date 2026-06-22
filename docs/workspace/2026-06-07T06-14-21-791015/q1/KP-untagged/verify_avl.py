"""
独立验证 AVL 树插入过程
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
    # Standard BST insert
    if not root:
        return Node(key)
    if key < root.key:
        root.left = insert(root.left, key)
    else:
        root.right = insert(root.right, key)
    
    update_height(root)
    balance = get_balance(root)
    
    # LL case
    if balance > 1 and key < root.left.key:
        return right_rotate(root)
    
    # RR case
    if balance < -1 and key > root.right.key:
        return left_rotate(root)
    
    # LR case
    if balance > 1 and key > root.left.key:
        root.left = left_rotate(root.left)
        return right_rotate(root)
    
    # RL case
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

def print_tree(root, prefix="", is_left=True):
    if root:
        print_tree(root.right, prefix + ("│   " if is_left else "    "), False)
        print(prefix + ("└── " if is_left else "┌── ") + str(root.key) + f" (h={root.height}, bf={get_balance(root)})")
        print_tree(root.left, prefix + ("    " if is_left else "│   "), True)

def get_all_balances(root):
    """返回所有节点的平衡因子"""
    result = {}
    def dfs(node):
        if node:
            result[node.key] = get_balance(node)
            dfs(node.left)
            dfs(node.right)
    dfs(root)
    return result

def get_non_leaf_balances(root):
    """返回所有非叶子节点的平衡因子"""
    result = {}
    def dfs(node):
        if node:
            if node.left or node.right:  # 非叶子节点
                result[node.key] = get_balance(node)
            dfs(node.left)
            dfs(node.right)
    dfs(root)
    return result

# Build initial tree:
#         10
#        /  \
#       5    15
#      / \   / \
#     3   7 12  18

root = Node(10)
root.left = Node(5)
root.right = Node(15)
root.left.left = Node(3)
root.left.right = Node(7)
root.right.left = Node(12)
root.right.right = Node(18)

# Set heights manually for initial tree
for node in [root.left.left, root.left.right, root.right.left, root.right.right]:
    node.height = 1
for node in [root.left, root.right]:
    node.height = 2
root.height = 3

print("=" * 60)
print("初始AVL树:")
print("=" * 60)
print_tree(root)
print(f"所有节点平衡因子: {get_all_balances(root)}")
print(f"非叶子节点平衡因子: {get_non_leaf_balances(root)}")
print(f"树高: {get_height(root)}")

# Insert 2
print("\n" + "=" * 60)
print("插入关键字 2:")
print("=" * 60)
root = insert(root, 2)
print_tree(root)
print(f"所有节点平衡因子: {get_all_balances(root)}")
print(f"非叶子节点平衡因子: {get_non_leaf_balances(root)}")
print(f"树高: {get_height(root)}")
balances_after_2 = get_non_leaf_balances(root)
any_imbalanced = any(abs(b) > 1 for b in balances_after_2.values())
print(f"是否有失衡节点: {any_imbalanced}")

# Insert 1
print("\n" + "=" * 60)
print("插入关键字 1:")
print("=" * 60)
root = insert(root, 1)
print_tree(root)
print(f"所有节点平衡因子: {get_all_balances(root)}")
print(f"非叶子节点平衡因子: {get_non_leaf_balances(root)}")
print(f"树高: {get_height(root)}")

# Insert 14
print("\n" + "=" * 60)
print("插入关键字 14:")
print("=" * 60)
root = insert(root, 14)
print_tree(root)
print(f"所有节点平衡因子: {get_all_balances(root)}")
print(f"非叶子节点平衡因子: {get_non_leaf_balances(root)}")
print(f"树高: {get_height(root)}")

# Inorder traversal
print("\n" + "=" * 60)
print("最终AVL树的中序遍历:")
print("=" * 60)
inorder_result = inorder(root)
print(inorder_result)

# Verify BST property
print("\n" + "=" * 60)
print("验证BST性质:")
print("=" * 60)
is_sorted = inorder_result == sorted(inorder_result)
print(f"中序遍历是否有序: {is_sorted}")

# Verify AVL property
def is_avl(node):
    if not node:
        return True, 0
    left_ok, left_h = is_avl(node.left)
    right_ok, right_h = is_avl(node.right)
    balanced = abs(left_h - right_h) <= 1
    return left_ok and right_ok and balanced, 1 + max(left_h, right_h)

avl_ok, tree_h = is_avl(root)
print(f"是否为合法AVL树: {avl_ok}")
print(f"树高: {tree_h}")
