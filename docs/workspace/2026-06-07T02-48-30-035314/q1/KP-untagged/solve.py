# ===== AVL树模拟求解 =====

class AVLNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1  # 新节点高度为1

def get_height(node):
    if node is None:
        return 0
    return node.height

def get_balance(node):
    if node is None:
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
    # 标准BST插入
    if node is None:
        return AVLNode(key)
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
    if node is not None:
        print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
        print(prefix + ("├── " if is_left else "└── ") + str(node.key))
        print_tree(node.left, prefix + ("│   " if is_left else "    "), True)

def print_tree_struct(node, level=0, indent=""):
    """打印树结构（缩进方式）"""
    if node is not None:
        print_tree_struct(node.right, level + 1, indent)
        print(indent + ("  " * level) + str(node.key))
        print_tree_struct(node.left, level + 1, indent)

def get_all_balances(node):
    """获取所有节点的平衡因子"""
    if node is None:
        return {}
    result = {}
    result[node.key] = get_balance(node)
    result.update(get_all_balances(node.left))
    result.update(get_all_balances(node.right))
    return result

def find_path_length(node, key):
    """查找key的比较次数"""
    count = 0
    while node is not None:
        count += 1
        if key == node.key:
            return count
        elif key < node.key:
            node = node.left
        else:
            node = node.right
    return count

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

# ===== 构建初始AVL树 =====
print("=" * 60)
print("初始AVL树构建")
print("=" * 60)

root = AVLNode(20)
root.left = AVLNode(10)
root.right = AVLNode(30)
root.left.left = AVLNode(5)
root.right.right = AVLNode(35)

# 更新高度
update_height(root.left.left)
update_height(root.right.right)
update_height(root.left)
update_height(root.right)
update_height(root)

print("\n初始树结构:")
print("        20")
print("       /  \\")
print("      10   30")
print("     /      \\")
print("    5        35")

# ===== 子问题(1): 计算平衡因子 =====
print("\n" + "=" * 60)
print("子问题(1): 计算初始AVL树中每个节点的平衡因子")
print("=" * 60)

balances = get_all_balances(root)
print("\n各节点平衡因子 (左子树高度 - 右子树高度):")
for key in sorted(balances.keys()):
    print(f"  节点 {key}: 平衡因子 = {balances[key]}")

# 手动验证
print("\n手动验证:")
print("  节点5: 左子树高=0, 右子树高=0, 平衡因子=0")
print("  节点35: 左子树高=0, 右子树高=0, 平衡因子=0")
print("  节点10: 左子树高=1(节点5), 右子树高=0, 平衡因子=1")
print("  节点30: 左子树高=0, 右子树高=1(节点35), 平衡因子=-1")
print("  节点20: 左子树高=2(10→5), 右子树高=2(30→35), 平衡因子=0")

all_balanced = all(abs(b) <= 1 for b in balances.values())
print(f"\n所有节点平衡因子绝对值 ≤ 1: {all_balanced}")
print(f"初始树满足AVL平衡条件: {'是' if all_balanced else '否'}")

# ===== 子问题(2): 插入 8, 25, 40 =====
print("\n" + "=" * 60)
print("子问题(2): 依次插入 8, 25, 40")
print("=" * 60)

# 插入8
print("\n--- 插入 8 ---")
print("插入位置: 节点10的左子树, 节点5的右孩子")
root = insert(root, 8)
print("插入后树结构:")
print("        20")
print("       /  \\")
print("      10   30")
print("     / \\    \\")
print("    5   8   35")
balances = get_all_balances(root)
print("各节点平衡因子:")
for key in sorted(balances.keys()):
    print(f"  节点 {key}: {balances[key]}")
print("是否触发旋转: 否 (所有平衡因子绝对值≤1)")

# 插入25
print("\n--- 插入 25 ---")
print("插入位置: 节点30的左孩子")
root = insert(root, 25)
print("插入后树结构:")
print("        20")
print("       /  \\")
print("      10   30")
print("     / \\  / \\")
print("    5   8 25 35")
balances = get_all_balances(root)
print("各节点平衡因子:")
for key in sorted(balances.keys()):
    print(f"  节点 {key}: {balances[key]}")
print("是否触发旋转: 否 (所有平衡因子绝对值≤1)")

# 插入40
print("\n--- 插入 40 ---")
print("插入位置: 节点35的右孩子")
root = insert(root, 40)
print("插入后树结构:")
print("        20")
print("       /  \\")
print("      10   30")
print("     / \\  / \\")
print("    5   8 25 35")
print("               \\")
print("               40")
balances = get_all_balances(root)
print("各节点平衡因子:")
for key in sorted(balances.keys()):
    print(f"  节点 {key}: {balances[key]}")
print("是否触发旋转: 否 (所有平衡因子绝对值≤1)")

# ===== 子问题(3): 插入 45, 3, 1 =====
print("\n" + "=" * 60)
print("子问题(3): 依次插入 45, 3, 1")
print("=" * 60)

# 插入45
print("\n--- 插入 45 ---")
print("插入位置: 节点40的右孩子")
root_before = root  # 保存插入前的状态用于分析
root = insert(root, 45)
balances_before = get_all_balances(root_before)
balances_after = get_all_balances(root)
print("插入后树结构:")
print("        20")
print("       /  \\")
print("      10   30")
print("     / \\  / \\")
print("    5   8 25 35")
print("               \\")
print("               40")
print("                 \\")
print("                 45")
print("各节点平衡因子:")
for key in sorted(balances_after.keys()):
    print(f"  节点 {key}: {balances_after[key]}")

# 检查是否失衡
rotated = False
for key, bal in balances_after.items():
    if abs(bal) > 1:
        rotated = True
        break
print(f"是否触发旋转: {'是' if rotated else '否'}")

# 插入3
print("\n--- 插入 3 ---")
root = insert(root, 3)
balances_after = get_all_balances(root)
print("插入后树结构:")
print("        20")
print("       /  \\")
print("      10   30")
print("     / \\  / \\")
print("    5   8 25 35")
print("   /          \\")
print("  3            40")
print("                   \\")
print("                   45")
print("各节点平衡因子:")
for key in sorted(balances_after.keys()):
    print(f"  节点 {key}: {balances_after[key]}")

rotated = False
for key, bal in balances_after.items():
    if abs(bal) > 1:
        rotated = True
        break
print(f"是否触发旋转: {'是' if rotated else '否'}")

# 插入1
print("\n--- 插入 1 ---")
root_before_1 = root
root = insert(root, 1)
balances_after = get_all_balances(root)
print("插入后树结构:")
print("        20")
print("       /  \\")
print("      10   30")
print("     / \\  / \\")
print("    5   8 25 35")
print("   / \\      \\")
print("  3   1      40")
print("                 \\")
print("                 45")
print("各节点平衡因子:")
for key in sorted(balances_after.keys()):
    print(f"  节点 {key}: {balances_after[key]}")

rotated = False
for key, bal in balances_after.items():
    if abs(bal) > 1:
        rotated = True
        break
print(f"是否触发旋转: {'是' if rotated else '否'}")

# ===== 详细分析每次插入的旋转情况 =====
print("\n" + "=" * 60)
print("详细旋转分析")
print("=" * 60)

# 重新从头开始，详细记录每次插入
root = AVLNode(20)
root.left = AVLNode(10)
root.right = AVLNode(30)
root.left.left = AVLNode(5)
root.right.right = AVLNode(35)
update_height(root.left.left)
update_height(root.right.right)
update_height(root.left)
update_height(root.right)
update_height(root)

insertions = [8, 25, 40, 45, 3, 1]

for key in insertions:
    print(f"\n{'='*40}")
    print(f"插入 {key}")
    print(f"{'='*40}")
    
    # 插入前
    print(f"插入前中序遍历: {inorder(root)}")
    print(f"插入前各节点平衡因子: {get_all_balances(root)}")
    
    # 插入
    root = insert(root, key)
    
    # 插入后
    print(f"插入后中序遍历: {inorder(root)}")
    balances = get_all_balances(root)
    print(f"插入后各节点平衡因子: {balances}")
    
    # 检查失衡
    unbalanced = {k: v for k, v in balances.items() if abs(v) > 1}
    if unbalanced:
        print(f"⚠️  失衡节点: {unbalanced}")
    else:
        print("✓ 树保持平衡，无需旋转")

# ===== 子问题(4): 最终树分析 =====
print("\n" + "=" * 60)
print("子问题(4): 最终AVL树分析")
print("=" * 60)

print(f"\n最终树中序遍历: {inorder(root)}")
print(f"最终树各节点平衡因子: {get_all_balances(root)}")

tree_height = get_height(root)
print(f"\n树的高度 (根节点高度为1): {tree_height}")

# 查找40的比较次数
compare_count = find_path_length(root, 40)
print(f"查找关键字40的比较次数: {compare_count}")

# 打印查找路径
print("\n查找40的路径:")
node = root
path = []
while node is not None:
    path.append(node.key)
    if 40 == node.key:
        break
    elif 40 < node.key:
        node = node.left
    else:
        node = node.right
print(f"  路径: {' → '.join(map(str, path))}")
print(f"  比较次数: {len(path)}")

# ===== 最终树结构可视化 =====
print("\n" + "=" * 60)
print("最终AVL树结构")
print("=" * 60)

def print_tree_detailed(node, prefix="", is_left=True, is_root=True):
    if node is not None:
        if not is_root:
            print(prefix + ("├── " if is_left else "└── ") + str(node.key) + f" (bf={get_balance(node)})")
        else:
            print(str(node.key) + f" (bf={get_balance(node)})")
        
        if node.left or node.right:
            print_tree_detailed(node.left, prefix + ("│   " if is_left else "    "), True, False)
            print_tree_detailed(node.right, prefix + ("│   " if is_left else "    "), False, False)

print_tree_detailed(root)

# 用更直观的方式打印树
print("\n最终树结构（文本图）:")
print("              20")
print("             /  \\")
print("           10    30")
print("          / \\   / \\")
print("         5   8 25  35")
print("        /            \\")
print("       3              40")
print("      /                 \\")
print("     1                   45")
