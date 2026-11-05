# ===== AVL树实现 =====

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    return node.height if node else 0

def get_balance(node):
    return get_height(node.left) - get_height(node.right) if node else 0

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
    # 标准BST插入
    if not root:
        return Node(key)
    if key < root.key:
        root.left = insert(root.left, key)
    else:
        root.right = insert(root.right, key)
    
    update_height(root)
    balance = get_balance(root)
    
    # LL型：左旋？不，LL型右旋
    if balance > 1 and key < root.left.key:
        return right_rotate(root)
    
    # RR型：左旋
    if balance < -1 and key > root.right.key:
        return left_rotate(root)
    
    # LR型：先左旋左子，再右旋根
    if balance > 1 and key > root.left.key:
        root.left = left_rotate(root.left)
        return right_rotate(root)
    
    # RL型：先右旋右子，再左旋根
    if balance < -1 and key < root.right.key:
        root.right = right_rotate(root.right)
        return left_rotate(root)
    
    return root

def print_tree(node, prefix="", is_left=True):
    if node:
        print(f"{prefix}{'├── ' if is_left else '└── '}{node.key} (BF={get_balance(node)})")
        if node.left or node.right:
            new_prefix = prefix + ("│   " if is_left else "    ")
            print_tree(node.left, new_prefix, True)
            print_tree(node.right, new_prefix, False)

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def print_tree_structure(node, level=0, direction=""):
    """打印树结构"""
    if node:
        indent = "    " * level
        if level == 0:
            print(f"{indent}[{node.key}] BF={get_balance(node)}")
        else:
            print(f"{indent}{direction} [{node.key}] BF={get_balance(node)}")
        print_tree_structure(node.left, level+1, "左")
        print_tree_structure(node.right, level+1, "右")

# ===== 子问题(1): 插入10, 15, 5, 12 =====
print("=" * 50)
print("子问题(1): 依次插入 10, 15, 5, 12")
print("=" * 50)

root = None
keys_1 = [10, 15, 5, 12]
for k in keys_1:
    root = insert(root, k)
    print(f"\n插入 {k} 后:")
    print_tree_structure(root)

print("\n--- 子问题(1) 最终树结构 ---")
print_tree_structure(root)
print("\n各节点平衡因子:")
# 遍历所有节点打印BF
def collect_nodes(node, nodes=None):
    if nodes is None:
        nodes = []
    if node:
        nodes.append(node)
        collect_nodes(node.left, nodes)
        collect_nodes(node.right, nodes)
    return nodes

nodes = collect_nodes(root)
for n in nodes:
    print(f"  节点 {n.key}: 平衡因子 = {get_balance(n)}")

# ===== 子问题(2): 插入13 =====
print("\n" + "=" * 50)
print("子问题(2): 插入 13")
print("=" * 50)

# 先手动分析插入13前的树
print("\n插入13前的树:")
print_tree_structure(root)

# 插入13
root = insert(root, 13)
print("\n插入13后的树:")
print_tree_structure(root)
print("\n各节点平衡因子:")
nodes = collect_nodes(root)
for n in nodes:
    print(f"  节点 {n.key}: 平衡因子 = {get_balance(n)}")

# ===== 子问题(3): 插入18和3 =====
print("\n" + "=" * 50)
print("子问题(3): 依次插入 18 和 3")
print("=" * 50)

print("\n插入18前的树:")
print_tree_structure(root)

root = insert(root, 18)
print("\n插入18后的树:")
print_tree_structure(root)
print("各节点平衡因子:")
nodes = collect_nodes(root)
for n in nodes:
    print(f"  节点 {n.key}: 平衡因子 = {get_balance(n)}")

print("\n插入3前的树:")
print_tree_structure(root)

root = insert(root, 3)
print("\n插入3后的树:")
print_tree_structure(root)
print("各节点平衡因子:")
nodes = collect_nodes(root)
for n in nodes:
    print(f"  节点 {n.key}: 平衡因子 = {get_balance(n)}")

print("\n最终AVL树的中序遍历:")
inorder_result = inorder(root)
print(f"  {inorder_result}")
