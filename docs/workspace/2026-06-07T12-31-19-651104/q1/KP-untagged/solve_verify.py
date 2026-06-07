"""
AVL树插入模拟：带详细调试输出，用于验证每一步
"""

class AVLNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    if node is None:
        return 0
    return node.height

def get_balance(node):
    if node is None:
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

def insert(root, key, rotations_log, debug=False):
    if root is None:
        return AVLNode(key)
    
    if key < root.key:
        root.left = insert(root.left, key, rotations_log, debug)
    elif key > root.key:
        root.right = insert(root.right, key, rotations_log, debug)
    else:
        return root
    
    update_height(root)
    balance = get_balance(root)
    
    # LL型
    if balance > 1 and key < root.left.key:
        rotations_log.append((key, "LL", root.key))
        return right_rotate(root)
    
    # RR型
    if balance < -1 and key > root.right.key:
        rotations_log.append((key, "RR", root.key))
        return left_rotate(root)
    
    # LR型
    if balance > 1 and key > root.left.key:
        rotations_log.append((key, "LR", root.key))
        root.left = left_rotate(root.left)
        return right_rotate(root)
    
    # RL型
    if balance < -1 and key < root.right.key:
        rotations_log.append((key, "RL", root.key))
        root.right = right_rotate(root.right)
        return left_rotate(root)
    
    return root

def print_tree(node, prefix="", is_left=True):
    if node is None:
        return
    print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
    print(prefix + ("└── " if is_left else "┌── ") + f"{node.key}(bf={get_balance(node)},h={node.height})")
    print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

def get_all_nodes(node, result):
    if node is None:
        return
    get_all_nodes(node.left, result)
    result.append((node.key, get_balance(node)))
    get_all_nodes(node.right, result)

def verify_avl(node):
    """验证AVL树性质"""
    if node is None:
        return True, 0
    
    left_ok, left_h = verify_avl(node.left)
    right_ok, right_h = verify_avl(node.right)
    
    if not left_ok or not right_ok:
        return False, 0
    
    bf = get_balance(node)
    if abs(bf) > 1:
        print(f"  [ERROR] 结点 {node.key} 平衡因子={bf}，违反AVL性质！")
        return False, 0
    
    # 验证BST性质
    if node.left:
        if node.left.key >= node.key:
            print(f"  [ERROR] 结点 {node.key} 的左孩子 {node.left.key} >= {node.key}，违反BST性质！")
            return False, 0
    if node.right:
        if node.right.key <= node.key:
            print(f"  [ERROR] 结点 {node.key} 的右孩子 {node.right.key} <= {node.key}，违反BST性质！")
            return False, 0
    
    return True, node.height

# ===== 主程序 =====
elements = [10, 20, 25, 30, 32, 33, 15, 12, 35, 40, 38, 42, 45, 43, 44, 46, 47, 48, 49, 50]

rotations_log = []
root = None

print("=" * 60)
print("=== 子问题(1)：插入前6个元素 ===")
print("=" * 60)

for i, key in enumerate(elements[:6]):
    root = insert(root, key, rotations_log)
    if rotations_log and rotations_log[-1][0] == key:
        rot = rotations_log[-1]
        print(f"插入 {key}: 发生{rot[1]}型旋转，旋转中心结点值为 {rot[2]}")
    else:
        print(f"插入 {key}: 无旋转")

print("\n前6个元素插入后的AVL树:")
print_tree(root)
ok, _ = verify_avl(root)
print(f"AVL性质验证: {'通过' if ok else '失败'}")

print("\n" + "=" * 60)
print("=== 子问题(2)：插入剩余14个元素 ===")
print("=" * 60)

for key in elements[6:]:
    root = insert(root, key, rotations_log)
    if rotations_log and rotations_log[-1][0] == key:
        rot = rotations_log[-1]
        print(f"插入 {key}: 发生{rot[1]}型旋转，旋转中心结点值为 {rot[2]}")
    else:
        print(f"插入 {key}: 无旋转")

print("\n最终AVL树:")
print_tree(root)
ok, _ = verify_avl(root)
print(f"AVL性质验证: {'通过' if ok else '失败'}")

print("\n" + "=" * 60)
print("=== 子问题(3)：平衡因子绝对值为1的结点 ===")
print("=" * 60)

all_nodes = []
get_all_nodes(root, all_nodes)

print("所有结点的平衡因子:")
for k, bf in all_nodes:
    print(f"  结点 {k}: bf={bf}")

bf_abs1_nodes = [(k, bf) for k, bf in all_nodes if abs(bf) == 1]
print(f"\n平衡因子绝对值为1的结点: {bf_abs1_nodes}")

if bf_abs1_nodes:
    min_node = min(bf_abs1_nodes, key=lambda x: x[0])
    print(f"结点值最小的: 值={min_node[0]}, 平衡因子={min_node[1]}")

print("\n" + "=" * 60)
print("=== 所有旋转记录汇总 ===")
print("=" * 60)
for i, (key, rot_type, center) in enumerate(rotations_log):
    print(f"  [{i+1}] 插入 {key}: {rot_type}型旋转，旋转中心={center}")
