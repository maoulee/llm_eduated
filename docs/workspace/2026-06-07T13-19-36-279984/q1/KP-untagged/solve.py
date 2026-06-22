# ===== AVL树完整求解 =====

class AVLNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1  # 新节点高度为1
    
    def __repr__(self):
        return f"Node({self.key})"

def get_height(node):
    if node is None:
        return 0
    return node.height

def get_balance(node):
    """平衡因子 = 左子树高度 - 右子树高度"""
    if node is None:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(y):
    x = y.left
    T3 = x.right
    
    x.right = y
    y.left = T3
    
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

def avl_insert(node, key):
    """返回插入后的根节点，以及是否发生旋转、旋转类型、失衡节点"""
    rotation_info = None
    
    # 标准BST插入
    if node is None:
        return AVLNode(key), None
    
    if key < node.key:
        node.left, rotation_info = avl_insert(node.left, key)
    elif key > node.key:
        node.right, rotation_info = avl_insert(node.right, key)
    else:
        return node, None  # 重复关键字不插入
    
    # 更新高度
    update_height(node)
    
    # 获取平衡因子
    balance = get_balance(node)
    
    # LL型
    if balance > 1 and key < node.left.key:
        rotation_info = ("LL", node.key)
        return right_rotate(node), rotation_info
    
    # RR型
    if balance < -1 and key > node.right.key:
        rotation_info = ("RR", node.key)
        return left_rotate(node), rotation_info
    
    # LR型
    if balance > 1 and key > node.left.key:
        rotation_info = ("LR", node.key)
        node.left = left_rotate(node.left)
        result = right_rotate(node)
        return result, rotation_info
    
    # RL型
    if balance < -1 and key < node.right.key:
        rotation_info = ("RL", node.key)
        node.right = right_rotate(node.right)
        result = left_rotate(node)
        return result, rotation_info
    
    return node, None

def print_tree(node, prefix="", is_left=True, level=0):
    """打印树结构"""
    if node is None:
        return
    print_tree(node.right, prefix + ("│   " if is_left else "    "), False, level + 1)
    print(f"{prefix}{'├── ' if is_left else '└── '}{node.key} (h={node.height}, bf={get_balance(node)})")
    print_tree(node.left, prefix + ("│   " if is_left else "    "), True, level + 1)

def inorder(node, result=None):
    if result is None:
        result = []
    if node is None:
        return result
    inorder(node.left, result)
    result.append(node.key)
    inorder(node.right, result)
    return result

def get_all_nodes(node, result=None):
    """获取所有节点（层序）"""
    if result is None:
        result = []
    if node is None:
        return result
    from collections import deque
    queue = deque([node])
    while queue:
        curr = queue.popleft()
        result.append(curr)
        if curr.left:
            queue.append(curr.left)
        if curr.right:
            queue.append(curr.right)
    return result

def get_non_leaf_nodes(node):
    """获取所有非叶子节点"""
    result = []
    if node is None:
        return result
    if node.left is not None or node.right is not None:
        result.append(node)
        result.extend(get_non_leaf_nodes(node.left))
        result.extend(get_non_leaf_nodes(node.right))
    return result

# ===== 子问题(1)：插入10, 20, 30 =====
print("=" * 60)
print("子问题(1)：插入 10, 20, 30")
print("=" * 60)

root = None
for key in [10, 20, 30]:
    root, rot_info = avl_insert(root, key)
    if rot_info:
        print(f"  插入 {key} 后触发旋转: 类型={rot_info[0]}, 失衡节点={rot_info[1]}")
    else:
        print(f"  插入 {key} 后无需旋转")

print("\n插入10,20,30后的AVL树结构：")
print_tree(root)
print(f"\n根节点关键字: {root.key}")
print(f"根节点平衡因子: {get_balance(root)}")
print(f"根节点高度: {get_height(root)}")

# 保存状态用于子问题(2)
root_after_q1 = root

# ===== 子问题(2)：继续插入5, 15 =====
print("\n" + "=" * 60)
print("子问题(2)：继续插入 5, 15")
print("=" * 60)

for key in [5, 15]:
    root, rot_info = avl_insert(root, key)
    if rot_info:
        print(f"  插入 {key} 后触发旋转: 类型={rot_info[0]}, 失衡节点={rot_info[1]}")
    else:
        print(f"  插入 {key} 后无需旋转")

print("\n插入5,15后的AVL树结构：")
print_tree(root)

non_leaf = get_non_leaf_nodes(root)
print("\n所有非叶子节点及其平衡因子：")
for node in non_leaf:
    print(f"  节点 {node.key}: 平衡因子 = {get_balance(node)}")

# 保存状态用于子问题(3)
root_after_q2 = root

# ===== 子问题(3)：继续插入12, 25, 22 =====
print("\n" + "=" * 60)
print("子问题(3)：继续插入 12, 25, 22")
print("=" * 60)

for key in [12, 25, 22]:
    root, rot_info = avl_insert(root, key)
    if rot_info:
        print(f"  插入 {key} 后触发旋转: 类型={rot_info[0]}, 失衡节点={rot_info[1]}")
    else:
        print(f"  插入 {key} 后无需旋转")

print("\n插入12,25,22后的AVL树结构：")
print_tree(root)

# 检查插入22时的旋转
print(f"\n插入22后根节点关键字: {root.key}")

# ===== 子问题(4)：最终AVL树分析 =====
print("\n" + "=" * 60)
print("子问题(4)：最终AVL树分析")
print("=" * 60)

# 插入最后一个30（重复，不插入）
root, rot_info = avl_insert(root, 30)
print(f"  插入 30 (重复): 不插入")

print("\n最终AVL树结构：")
print_tree(root)

# 树的高度
tree_height = get_height(root)
print(f"\n树的高度（根节点为第1层）: {tree_height}")

# 中序遍历
inorder_result = inorder(root)
print(f"中序遍历序列: {inorder_result}")

# 所有节点的平衡因子
print("\n所有节点的平衡因子：")
all_nodes = get_all_nodes(root)
for node in all_nodes:
    print(f"  节点 {node.key}: 平衡因子 = {get_balance(node)}, 高度 = {node.height}")

# ===== 详细步骤追踪 =====
print("\n" + "=" * 60)
print("详细插入过程追踪")
print("=" * 60)

def avl_insert_detailed(node, key, depth=0):
    """详细追踪插入过程"""
    indent = "  " * depth
    
    # 标准BST插入
    if node is None:
        return AVLNode(key), None
    
    if key < node.key:
        node.left, rot_info = avl_insert_detailed(node.left, key, depth + 1)
    elif key > node.key:
        node.right, rot_info = avl_insert_detailed(node.right, key, depth + 1)
    else:
        return node, None
    
    update_height(node)
    balance = get_balance(node)
    
    # LL型
    if balance > 1 and key < node.left.key:
        print(f"{indent}  节点{node.key}失衡(bf={balance}), LL旋转")
        return right_rotate(node), ("LL", node.key)
    
    # RR型
    if balance < -1 and key > node.right.key:
        print(f"{indent}  节点{node.key}失衡(bf={balance}), RR旋转")
        return left_rotate(node), ("RR", node.key)
    
    # LR型
    if balance > 1 and key > node.left.key:
        print(f"{indent}  节点{node.key}失衡(bf={balance}), LR旋转")
        node.left = left_rotate(node.left)
        return right_rotate(node), ("LR", node.key)
    
    # RL型
    if balance < -1 and key < node.right.key:
        print(f"{indent}  节点{node.key}失衡(bf={balance}), RL旋转")
        node.right = right_rotate(node.right)
        return left_rotate(node), ("RL", node.key)
    
    return node, None

# 重新从头开始详细追踪
print("\n--- 插入10 ---")
root = None
root, _ = avl_insert_detailed(root, 10)
print_tree(root)

print("\n--- 插入20 ---")
root, _ = avl_insert_detailed(root, 20)
print_tree(root)

print("\n--- 插入30 ---")
root, _ = avl_insert_detailed(root, 30)
print_tree(root)

print("\n--- 插入5 ---")
root, _ = avl_insert_detailed(root, 5)
print_tree(root)

print("\n--- 插入15 ---")
root, _ = avl_insert_detailed(root, 15)
print_tree(root)

print("\n--- 插入12 ---")
root, _ = avl_insert_detailed(root, 12)
print_tree(root)

print("\n--- 插入25 ---")
root, _ = avl_insert_detailed(root, 25)
print_tree(root)

print("\n--- 插入22 ---")
root, _ = avl_insert_detailed(root, 22)
print_tree(root)

print("\n--- 插入30(重复) ---")
root, _ = avl_insert_detailed(root, 30)
print_tree(root)
