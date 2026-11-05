# ===== AVL树求解验证 =====

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    return node.height if node else 0

def get_balance(node):
    if not node:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    if node:
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

def insert(node, key):
    if not node:
        return Node(key)
    if key < node.key:
        node.left = insert(node.left, key)
    else:
        node.right = insert(node.right, key)
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

def print_tree(node, prefix="", is_left=True):
    if node is None:
        return
    print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
    print(prefix + ("└── " if is_left else "┌── ") + str(node.key))
    print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

def print_tree_info(node):
    """打印树的所有节点信息"""
    if not node:
        return
    print_tree_info(node.left)
    print(f"  节点{node.key}: 左={node.left.key if node.left else None}, 右={node.right.key if node.right else None}, H={node.height}, BF={get_balance(node)}")
    print_tree_info(node.right)

def build_initial_tree():
    """构建初始树"""
    root = Node(20)
    root.left = Node(10)
    root.right = Node(30)
    root.left.left = Node(5)
    root.right.left = Node(25)
    root.right.right = Node(35)
    for n in [root.left.left, root.right.left, root.right.right, root.left, root.right, root]:
        update_height(n)
    return root

# ===== 初始树 =====
print("=" * 60)
print("初始AVL树:")
print("=" * 60)
root = build_initial_tree()
print_tree(root)
print_tree_info(root)

# ===== 子问题(1): 插入1 =====
print("\n" + "=" * 60)
print("子问题(1): 插入关键字1")
print("=" * 60)

# 手动插入1不旋转，找到失衡节点
def insert_raw(node, key):
    if not node:
        return Node(key)
    if key < node.key:
        node.left = insert_raw(node.left, key)
    else:
        node.right = insert_raw(node.right, key)
    update_height(node)
    return node

root_temp = build_initial_tree()
root_temp = insert_raw(root_temp, 1)
print("插入1后（未旋转）:")
print_tree(root_temp)
print_tree_info(root_temp)

# 从插入点回溯找失衡节点
# 1插入到5的左子树
# 回溯: 5(BF=1,H=2) -> 10(BF=2,H=3) 失衡!
print("\n回溯分析:")
n5 = root_temp.left.left  # 节点5
n10 = root_temp.left  # 节点10
n20 = root_temp  # 节点20
print(f"  节点5: BF={get_balance(n5)}, H={get_height(n5)}")
print(f"  节点10: BF={get_balance(n10)}, H={get_height(n10)}")
print(f"  节点20: BF={get_balance(n20)}, H={get_height(n20)}")
print(f"\n  失衡节点: 10")
print(f"  失衡节点BF: {get_balance(n10)}")
print(f"  10的左孩子: 5, 1插入在5的左子树 -> LL型")
print(f"  旋转类型: LL (右旋)")

# 正式插入1（带旋转）
root = insert(root, 1)
print(f"\n插入1并LL旋转后:")
print_tree(root)
print_tree_info(root)

# ===== 子问题(2): 旋转后的树 =====
print("\n" + "=" * 60)
print("子问题(2): 插入1并旋转后的树结构")
print("=" * 60)
print("树形图:")
print("        20")
print("       /  \\")
print("      5    30")
print("     / \\   / \\")
print("    1  10 25  35")

# 验证
print("\n验证各节点BF:")
print(f"  节点1: BF={get_balance(root.left.left.left)}")
print(f"  节点10: BF={get_balance(root.left.right)}")
print(f"  节点5: BF={get_balance(root.left)}")
print(f"  节点25: BF={get_balance(root.right.left)}")
print(f"  节点35: BF={get_balance(root.right.right)}")
print(f"  节点30: BF={get_balance(root.right)}")
print(f"  节点20: BF={get_balance(root)}")

# ===== 子问题(3): 插入2, 40, 45 =====
print("\n" + "=" * 60)
print("子问题(3): 依次插入2, 40, 45")
print("=" * 60)

# 插入2
print("\n--- 插入2 ---")
root = insert(root, 2)
print("插入2后:")
print_tree(root)
print_tree_info(root)
# 检查是否失衡
def check_balance(node):
    if not node:
        return True, None, 0
    lb, ln, lbf = check_balance(node.left)
    rb, rn, rbf = check_balance(node.right)
    bf = get_balance(node)
    if abs(bf) > 1:
        return False, node, bf
    return lb and rb, None, 0

balanced, imbal_node, imbal_bf = check_balance(root)
print(f"  平衡: {balanced}")
if not balanced:
    print(f"  失衡节点: {imbal_node.key}, BF={imbal_bf}")

# 插入40
print("\n--- 插入40 ---")
root = insert(root, 40)
print("插入40后:")
print_tree(root)
print_tree_info(root)
balanced, imbal_node, imbal_bf = check_balance(root)
print(f"  平衡: {balanced}")
if not balanced:
    print(f"  失衡节点: {imbal_node.key}, BF={imbal_bf}")

# 插入45 - 先手动插入不旋转
print("\n--- 插入45（分析失衡）---")
root_before_45 = build_initial_tree()
root_before_45 = insert(root_before_45, 1)
root_before_45 = insert(root_before_45, 2)
root_before_45 = insert(root_before_45, 40)

print("插入45前的树:")
print_tree(root_before_45)
print_tree_info(root_before_45)

# 手动插入45不旋转
root_temp_45 = insert_raw(root_before_45, 45)
print("\n插入45后（未旋转）:")
print_tree(root_temp_45)
print_tree_info(root_temp_45)

# 从插入点回溯找失衡节点
# 45插入到40的右子树
# 回溯: 40(BF=-1,H=2) -> 35(BF=-2,H=3) 失衡!
print("\n回溯分析:")
# 找到35节点
n35 = root_temp_45.right.right  # 30的右孩子
n40 = n35.right  # 35的右孩子
n45 = n40.right  # 40的右孩子
n30 = root_temp_45.right  # 30
print(f"  节点45: BF={get_balance(n45)}, H={get_height(n45)}")
print(f"  节点40: BF={get_balance(n40)}, H={get_height(n40)}")
print(f"  节点35: BF={get_balance(n35)}, H={get_height(n35)}")
print(f"  节点30: BF={get_balance(n30)}, H={get_height(n30)}")
print(f"\n  从插入点45回溯:")
print(f"  40: BF={get_balance(n40)} (ok)")
print(f"  35: BF={get_balance(n35)} (失衡!)")
print(f"\n  失衡节点: 35")
print(f"  失衡节点BF: {get_balance(n35)}")
print(f"  35的右孩子: 40, 45插入在40的右子树 -> RR型")
print(f"  旋转类型: RR (左旋)")

# 正式插入45（带旋转）
root = insert(root, 45)
print(f"\n插入45并RR旋转后:")
print_tree(root)
print_tree_info(root)

# ===== 最终树结构 =====
print("\n" + "=" * 60)
print("最终AVL树结构:")
print("=" * 60)
print("        20")
print("       /  \\")
print("      5    30")
print("     / \\   / \\")
print("    1  10 25  40")
print("             /  \\")
print("            35   45")

print("\n最终验证各节点BF:")
print(f"  节点1: BF={get_balance(root.left.left.left)}")
print(f"  节点10: BF={get_balance(root.left.right)}")
print(f"  节点5: BF={get_balance(root.left)}")
print(f"  节点25: BF={get_balance(root.right.left)}")
print(f"  节点35: BF={get_balance(root.right.right.left)}")
print(f"  节点45: BF={get_balance(root.right.right.right)}")
print(f"  节点40: BF={get_balance(root.right.right)}")
print(f"  节点30: BF={get_balance(root.right)}")
print(f"  节点20: BF={get_balance(root)}")

balanced, _, _ = check_balance(root)
print(f"\n  最终树平衡: {balanced}")
