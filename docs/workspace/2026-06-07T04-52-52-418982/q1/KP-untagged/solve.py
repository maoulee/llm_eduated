# ===== AVL树求解（修正版）=====

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

def avl_insert(root, key):
    """正确的AVL插入：递归逐层检查平衡"""
    if not root:
        return Node(key), None
    
    rotation_type = None
    
    if key < root.key:
        root.left, rotation_type = avl_insert(root.left, key)
    else:
        root.right, rotation_type = avl_insert(root.right, key)
    
    update_height(root)
    balance = get_balance(root)
    
    # Left Left Case
    if balance > 1 and key < root.left.key:
        rotation_type = f"LL型(节点{root.key}右旋)"
        root = right_rotate(root)
    
    # Right Right Case
    elif balance < -1 and key > root.right.key:
        rotation_type = f"RR型(节点{root.key}左旋)"
        root = left_rotate(root)
    
    # Left Right Case
    elif balance > 1 and key > root.left.key:
        rotation_type = f"LR型(节点{root.left.key}左旋, 节点{root.key}右旋)"
        root.left = left_rotate(root.left)
        root = right_rotate(root)
    
    # Right Left Case
    elif balance < -1 and key < root.right.key:
        rotation_type = f"RL型(节点{root.right.key}右旋, 节点{root.key}左旋)"
        root.right = right_rotate(root.right)
        root = left_rotate(root)
    
    return root, rotation_type

def print_tree_structure(node, level=0, direction=""):
    if not node:
        return
    bf = get_balance(node)
    indent = "    " * level
    if direction == "":
        print(f"{indent}[{node.key}] BF={bf}")
    else:
        print(f"{indent}--{direction}-- [{node.key}] BF={bf}")
    if node.left:
        print_tree_structure(node.left, level + 1, "L")
    if node.right:
        print_tree_structure(node.right, level + 1, "R")

def level_order(root):
    if not root:
        return []
    result = []
    queue = [root]
    while queue:
        node = queue.pop(0)
        result.append(node.key)
        if node.left:
            queue.append(node.left)
        if node.right:
            queue.append(node.right)
    return result

def insert_bst(root, key):
    """普通BST插入（不调整平衡）"""
    if not root:
        return Node(key)
    if key < root.key:
        root.left = insert_bst(root.left, key)
    else:
        root.right = insert_bst(root.right, key)
    update_height(root)
    return root

def build_tree_from_level_order(keys):
    if not keys:
        return None
    root = Node(keys[0])
    for key in keys[1:]:
        root = insert_bst(root, key)
    return root

def print_bf(node):
    if not node:
        return
    bf = get_balance(node)
    left_h = get_height(node.left)
    right_h = get_height(node.right)
    print(f"  节点{node.key}: 左高={left_h}, 右高={right_h}, BF={bf}")
    print_bf(node.left)
    print_bf(node.right)

def get_max_abs_bf(node):
    """获取树中最大|BF|"""
    if not node:
        return 0
    bf = abs(get_balance(node))
    left_max = get_max_abs_bf(node.left)
    right_max = get_max_abs_bf(node.right)
    return max(bf, left_max, right_max)

# ===== 题目参数 =====
initial_level_order = [10, 5, 15, 3, 7]

print("=" * 60)
print("(1) 初始AVL树（层序遍历: 10, 5, 15, 3, 7）")
print("=" * 60)

root = build_tree_from_level_order(initial_level_order)
print("\n初始AVL树结构:")
print_tree_structure(root)
print(f"\n层序遍历验证: {level_order(root)}")
print("\n各节点平衡因子:")
print_bf(root)

# ===== 插入节点6 =====
print("\n" + "=" * 60)
print("(2) 插入节点6")
print("=" * 60)

print("\n--- 插入过程分析 ---")
print("6 > 5, 6 < 7, 所以6插入为7的左子节点")

# 用普通BST插入看看插入后的状态
temp_root = build_tree_from_level_order(initial_level_order)
temp_root = insert_bst(temp_root, 6)
print("\n插入6后（未调整平衡）:")
print_tree_structure(temp_root)
print("\n各节点平衡因子:")
print_bf(temp_root)

max_bf = get_max_abs_bf(temp_root)
print(f"\n最大|BF|={max_bf}")
if max_bf <= 1:
    print("→ 无需旋转")
else:
    print("→ 需要旋转")

# 用正确的AVL插入
root, rotation = avl_insert(root, 6)
print(f"\n插入6后（AVL调整后）:")
print_tree_structure(root)
print(f"\n层序遍历: {level_order(root)}")
print(f"\n各节点平衡因子:")
print_bf(root)
print(f"\n旋转类型: {rotation if rotation else '无需旋转'}")

# ===== 插入节点12 =====
print("\n" + "=" * 60)
print("(3) 插入节点12")
print("=" * 60)

print("\n--- 插入过程分析 ---")
print("12 > 10, 12 < 15, 所以12插入为15的左子节点")

# 用普通BST插入看看插入后的状态
temp_root2 = build_tree_from_level_order(initial_level_order)
temp_root2 = insert_bst(temp_root2, 6)
temp_root2 = insert_bst(temp_root2, 12)
print("\n插入12后（未调整平衡）:")
print_tree_structure(temp_root2)
print("\n各节点平衡因子:")
print_bf(temp_root2)

max_bf = get_max_abs_bf(temp_root2)
print(f"\n最大|BF|={max_bf}")
if max_bf <= 1:
    print("→ 无需旋转")
else:
    print("→ 需要旋转")

root, rotation = avl_insert(root, 12)
print(f"\n插入12后（AVL调整后）:")
print_tree_structure(root)
print(f"\n层序遍历: {level_order(root)}")
print(f"\n各节点平衡因子:")
print_bf(root)
print(f"\n旋转类型: {rotation if rotation else '无需旋转'}")

# ===== 插入节点13 =====
print("\n" + "=" * 60)
print("(4) 插入节点13")
print("=" * 60)

print("\n--- 插入过程分析 ---")
print("13 > 10, 13 < 15, 13 > 12, 所以13插入为12的右子节点")

# 用普通BST插入看看插入后的状态
temp_root3 = build_tree_from_level_order(initial_level_order)
temp_root3 = insert_bst(temp_root3, 6)
temp_root3 = insert_bst(temp_root3, 12)
temp_root3 = insert_bst(temp_root3, 13)
print("\n插入13后（未调整平衡）:")
print_tree_structure(temp_root3)
print("\n各节点平衡因子:")
print_bf(temp_root3)

max_bf = get_max_abs_bf(temp_root3)
print(f"\n最大|BF|={max_bf}")
if max_bf <= 1:
    print("→ 无需旋转")
else:
    print("→ 需要旋转")

root, rotation = avl_insert(root, 13)
print(f"\n插入13后（AVL调整后）:")
print_tree_structure(root)
print(f"\n层序遍历: {level_order(root)}")
print(f"\n各节点平衡因子:")
print_bf(root)
print(f"\n旋转类型: {rotation if rotation else '无需旋转'}")
