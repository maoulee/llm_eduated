"""
AVL树插入模拟：完整实现并记录每次旋转
"""

class AVLNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1  # 新插入结点高度为1

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

def right_rotate(z):
    """右旋：以z为旋转中心"""
    y = z.left
    T3 = y.right
    
    y.right = z
    z.left = T3
    
    update_height(z)
    update_height(y)
    return y

def left_rotate(z):
    """左旋：以z为旋转中心"""
    y = z.right
    T2 = y.left
    
    y.left = z
    z.right = T2
    
    update_height(z)
    update_height(y)
    return y

def insert(root, key, rotations_log):
    """
    插入key到AVL树，记录旋转信息
    rotations_log: 列表，记录 (插入值, 旋转类型, 旋转中心值)
    """
    # 标准BST插入
    if root is None:
        return AVLNode(key)
    
    if key < root.key:
        root.left = insert(root.left, key, rotations_log)
    elif key > root.key:
        root.right = insert(root.right, key, rotations_log)
    else:
        return root  # 不允许重复
    
    # 更新高度
    update_height(root)
    
    # 获取平衡因子
    balance = get_balance(root)
    
    # LL型：左孩子的左子树插入导致失衡
    if balance > 1 and key < root.left.key:
        rotations_log.append((key, "LL", root.key))
        return right_rotate(root)
    
    # RR型：右孩子的右子树插入导致失衡
    if balance < -1 and key > root.right.key:
        rotations_log.append((key, "RR", root.key))
        return left_rotate(root)
    
    # LR型：左孩子的右子树插入导致失衡
    if balance > 1 and key > root.left.key:
        rotations_log.append((key, "LR", root.key))
        root.left = left_rotate(root.left)
        return right_rotate(root)
    
    # RL型：右孩子的左子树插入导致失衡
    if balance < -1 and key < root.right.key:
        rotations_log.append((key, "RL", root.key))
        root.right = right_rotate(root.right)
        return left_rotate(root)
    
    return root

def print_tree(node, prefix="", is_left=True):
    """打印树结构"""
    if node is None:
        return
    print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
    print(prefix + ("└── " if is_left else "┌── ") + f"{node.key}(bf={get_balance(node)})")
    print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

def get_all_nodes(node, result):
    """中序遍历获取所有结点"""
    if node is None:
        return
    get_all_nodes(node.left, result)
    result.append((node.key, get_balance(node)))
    get_all_nodes(node.right, result)

# ===== 主程序 =====
elements = [10, 20, 25, 30, 32, 33, 15, 12, 35, 40, 38, 42, 45, 43, 44, 46, 47, 48, 49, 50]

rotations_log = []
root = None

print("=" * 60)
print("=== 子问题(1)：插入前6个元素 ===")
print("=" * 60)

for i, key in enumerate(elements[:6]):
    root = insert(root, key, rotations_log)
    bf = get_balance(root)
    if rotations_log and rotations_log[-1][0] == key:
        rot = rotations_log[-1]
        print(f"插入 {key}: 发生{rot[1]}型旋转，旋转中心结点值为 {rot[2]}")
    else:
        print(f"插入 {key}: 无旋转")
    print(f"  当前根结点: {root.key}, 平衡因子: {bf}")

print()
print("前6个元素插入后的AVL树结构:")
print_tree(root)

print()
print("=" * 60)
print("=== 子问题(2)：插入剩余14个元素 ===")
print("=" * 60)

for key in elements[6:]:
    root = insert(root, key, rotations_log)
    if rotations_log and rotations_log[-1][0] == key:
        rot = rotations_log[-1]
        print(f"插入 {key}: 发生{rot[1]}型旋转，旋转中心结点值为 {rot[2]}")
    else:
        print(f"插入 {key}: 无旋转")

print()
print("最终AVL树结构:")
print_tree(root)

print()
print("=" * 60)
print("=== 子问题(3)：平衡因子绝对值为1的结点 ===")
print("=" * 60)

all_nodes = []
get_all_nodes(root, all_nodes)

bf_abs1_nodes = [(k, bf) for k, bf in all_nodes if abs(bf) == 1]
print(f"平衡因子绝对值为1的结点: {bf_abs1_nodes}")

if bf_abs1_nodes:
    min_node = min(bf_abs1_nodes, key=lambda x: x[0])
    print(f"结点值最小的: 值={min_node[0]}, 平衡因子={min_node[1]}")

print()
print("=" * 60)
print("=== 所有旋转记录汇总 ===")
print("=" * 60)
for i, (key, rot_type, center) in enumerate(rotations_log):
    print(f"  [{i+1}] 插入 {key}: {rot_type}型旋转，旋转中心={center}")
