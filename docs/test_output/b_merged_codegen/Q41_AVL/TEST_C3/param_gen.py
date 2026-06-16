"""
AVL树插入与旋转参数生成器
目标：生成一个初始AVL树 + 插入序列，触发至少2种不同类型的旋转
"""

class AVLNode:
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

def insert(root, key):
    rotations = []
    if not root:
        return AVLNode(key), rotations
    
    if key < root.key:
        root.left, r = insert(root.left, key)
        rotations.extend(r)
    elif key > root.key:
        root.right, r = insert(root.right, key)
        rotations.extend(r)
    else:
        return root, rotations
    
    root.height = 1 + max(get_height(root.left), get_height(root.right))
    balance = get_balance(root)
    
    # LL
    if balance > 1 and key < root.left.key:
        rotations.append(f"LL旋转(节点{root.key})")
        return right_rotate(root), rotations
    # RR
    if balance < -1 and key > root.right.key:
        rotations.append(f"RR旋转(节点{root.key})")
        return left_rotate(root), rotations
    # LR
    if balance > 1 and key > root.left.key:
        rotations.append(f"LR旋转(节点{root.key})")
        root.left = left_rotate(root.left)
        rotations.append(f"  先L旋转(节点{root.left.key})")
        return right_rotate(root), rotations
    # RL
    if balance < -1 and key < root.right.key:
        rotations.append(f"RL旋转(节点{root.key})")
        root.right = right_rotate(root.right)
        rotations.append(f"  先R旋转(节点{root.right.key})")
        return left_rotate(root), rotations
    
    return root, rotations

def is_avl(root):
    if not root:
        return True
    balance = get_balance(root)
    if abs(balance) > 1:
        return False
    return is_avl(root.left) and is_avl(root.right)

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def level_order(root):
    if not root:
        return []
    result = []
    queue = [root]
    while queue:
        node = queue.pop(0)
        if node:
            result.append(node.key)
            queue.append(node.left)
            queue.append(node.right)
        else:
            result.append(None)
    # Remove trailing None
    while result and result[-1] is None:
        result.pop()
    return result

def print_tree(node, prefix="", is_left=True):
    if node is not None:
        print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
        print(prefix + ("└── " if is_left else "┌── ") + str(node.key))
        print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

# ========== 构造方案 ==========
# 方案：先构建一个初始AVL树，然后插入序列触发多种旋转

# 初始插入序列（构建初始树）
initial_keys = [30, 20, 40, 10, 25, 35, 50]
root = None
all_rotations = []
for k in initial_keys:
    root, r = insert(root, k)
    all_rotations.extend(r)

print("=" * 60)
print("初始AVL树构建完成")
print(f"初始插入序列: {initial_keys}")
print(f"构建过程中的旋转: {all_rotations}")
print(f"中序遍历: {inorder(root)}")
print(f"层序遍历: {level_order(root)}")
print(f"是否为AVL树: {is_avl(root)}")
print("\n初始树结构:")
print_tree(root)

# 直接指定插入序列，确保触发多种旋转
# 基于初始树 [30, 20, 40, 10, 25, 35, 50]
# 结构:
#        30
#      /    \
#    20      40
#   /  \    /  \
# 10   25  35  50
#
# 插入 5:  10.left=5, 无旋转
# 插入 2:  5.left=2, 10.balance=2 → LL旋转(10)
# 插入 60: 50.right=60, 无旋转
# 插入 65: 60.right=65, 50.balance=-2 → RR旋转(50)

final_insertions = [5, 2, 60, 65]

print("\n" + "=" * 60)
print("最终参数:")
print("=" * 60)
print(f"初始树节点: {initial_keys}")
print(f"初始树层序: {level_order(root)}")
print(f"插入序列: {final_insertions}")

# 验证最终插入序列
verify_root = None
for k in initial_keys:
    verify_root, _ = insert(verify_root, k)

print("\n验证插入过程:")
all_rot_types = set()
for k in final_insertions:
    verify_root, r = insert(verify_root, k)
    for rot in r:
        if "LL" in rot:
            all_rot_types.add("LL")
        elif "RR" in rot:
            all_rot_types.add("RR")
        elif "LR" in rot:
            all_rot_types.add("LR")
        elif "RL" in rot:
            all_rot_types.add("RL")
    print(f"  插入 {k}: {r}")
    print(f"    当前树层序: {level_order(verify_root)}")
    print(f"    AVL检查: {is_avl(verify_root)}")

print(f"\n触发的旋转类型: {all_rot_types}")
print(f"旋转类型数量: {len(all_rot_types)}")

print(f"\n最终树结构:")
print_tree(verify_root)
print(f"最终中序: {inorder(verify_root)}")
print(f"最终层序: {level_order(verify_root)}")
