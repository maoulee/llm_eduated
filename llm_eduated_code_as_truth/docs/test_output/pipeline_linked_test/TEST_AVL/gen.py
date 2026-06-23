# gen.py - AVL插入与旋转题目参数构造

# ===== 参数定义 =====
# 初始状态：空AVL树
initial_tree = "空树"

# 插入序列（经验值：设计为触发LR双旋的场景）
insert_sequence = [30, 20, 40, 10, 25, 5, 15]

# 题目参数
num_insertions = len(insert_sequence)

# ===== 打印参数 =====
print("===== 参数 =====")
print(f"初始状态: {initial_tree}")
print(f"插入序列: {insert_sequence}")
print(f"插入次数: {num_insertions}")

# ===== 题干描述 =====
print()
print("===== 题干描述 =====")
print(f"""设有一棵初始为空的平衡二叉树（AVL树），现按以下顺序依次插入关键字：

    {', '.join(map(str, insert_sequence))}

**（1）（6分）** 依次插入上述关键字，画出每次插入后AVL树的形态，并标注每个结点的平衡因子。

**（2）（3分）** 指出插入过程中**首次**出现平衡因子绝对值为 2 的结点（即最小不平衡子树的根），并说明此时应执行何种旋转操作（LL/RR/LR/RL），简述判定依据。

**（3）（4分）** 完成第（2）问所指出的旋转调整后，画出最终AVL树的形态，并标注各结点的平衡因子。""")


# ===== 求解段 =====

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

def insert_avl(root, key):
    if root is None:
        return AVLNode(key)
    if key < root.key:
        root.left = insert_avl(root.left, key)
    else:
        root.right = insert_avl(root.right, key)
    update_height(root)
    balance = get_balance(root)
    # LL
    if balance > 1 and key < root.left.key:
        return right_rotate(root)
    # RR
    if balance < -1 and key > root.right.key:
        return left_rotate(root)
    # LR
    if balance > 1 and key > root.left.key:
        root.left = left_rotate(root.left)
        return right_rotate(root)
    # RL
    if balance < -1 and key < root.right.key:
        root.right = right_rotate(root.right)
        return left_rotate(root)
    return root

def tree_to_dict(node):
    if node is None:
        return None
    return {
        'key': node.key,
        'bf': get_balance(node),
        'left': tree_to_dict(node.left),
        'right': tree_to_dict(node.right)
    }

def format_tree(node, prefix="", is_left=True):
    lines = []
    if node is None:
        return lines
    if node is not None:
        lines.append(f"{prefix}{'├── ' if is_left else '└── '}[{node.key}] BF={get_balance(node)}")
    if node.left:
        extension = "│   " if is_left else "    "
        lines.extend(format_tree(node.left, prefix + extension, True))
    if node.right:
        extension = "│   " if is_left else "    "
        lines.extend(format_tree(node.right, prefix + extension, False))
    return lines

def print_tree(node):
    if node is None:
        print("  (空)")
        return
    print(f"  根: [{node.key}] BF={get_balance(node)}")
    lines = format_tree(node)
    for line in lines:
        print(f"  {line}")

# 模拟插入过程
print()
print("===== 求解路径 =====")

root = None
imbalance_detected = False
first_imbalance_node = None
first_imbalance_key = None
first_rotation_type = None
tree_states = []

for i, key in enumerate(insert_sequence):
    print(f"\n--- 插入第 {i+1} 个关键字: {key} ---")
    root = insert_avl(root, key)
    tree_dict = tree_to_dict(root)
    tree_states.append(tree_dict)
    print(f"插入后树形态:")
    print_tree(root)

# 重新模拟，但这次在插入后、旋转前检测失衡
print("\n===== 失衡检测（插入后、旋转前）=====")

class AVLNodeRaw:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def insert_raw(root, key):
    """插入但不旋转，用于检测失衡"""
    if root is None:
        return AVLNodeRaw(key)
    if key < root.key:
        root.left = insert_raw(root.left, key)
    else:
        root.right = insert_raw(root.right, key)
    # 更新高度
    root.height = 1 + max(get_height(root.left), get_height(root.right))
    return root

def find_first_imbalance(node):
    """找到首次失衡节点（自底向上，返回最深层的失衡节点）"""
    if node is None:
        return None
    balance = get_balance(node)
    if abs(balance) == 2:
        return node
    # 先查右子树（后插入的在右边更可能失衡），再查左子树
    right_imbalance = find_first_imbalance(node.right)
    if right_imbalance:
        return right_imbalance
    left_imbalance = find_first_imbalance(node.left)
    if left_imbalance:
        return left_imbalance
    return None

# 重新模拟：插入但不旋转，检测失衡
root_raw = None
for i, key in enumerate(insert_sequence):
    root_raw = insert_raw(root_raw, key)
    imbalance_node = find_first_imbalance(root_raw)
    if imbalance_node:
        first_imbalance_node = imbalance_node.key
        first_imbalance_key = key
        balance = get_balance(imbalance_node)
        child = imbalance_node.left if balance > 1 else imbalance_node.right
        child_balance = get_balance(child)
        if balance > 1 and child_balance >= 0:
            first_rotation_type = "LL"
        elif balance > 1 and child_balance < 0:
            first_rotation_type = "LR"
        elif balance < -1 and child_balance <= 0:
            first_rotation_type = "RR"
        elif balance < -1 and child_balance > 0:
            first_rotation_type = "RL"
        print(f"\n插入 {key} 后，结点 [{imbalance_node.key}] 首次失衡，BF={balance}")
        print(f"其{'左' if balance > 1 else '右'}孩子为 [{child.key}]，BF={child_balance}")
        print(f"应执行旋转: {first_rotation_type}")
        break

print(f"\n===== 答案 =====")
print(f"\n（1）每次插入后的AVL树形态与平衡因子见上方求解路径。")
print(f"\n（2）首次出现平衡因子绝对值为2的结点: {first_imbalance_node}")
print(f"    应执行旋转操作: {first_rotation_type}")
print(f"    判定依据: 结点 {first_imbalance_node} 的BF为{get_balance(AVLNode(first_imbalance_node)) if first_imbalance_node else ''}，其{'左' if first_rotation_type in ['LL','LR'] else '右'}孩子的BF为{'正/零' if first_rotation_type in ['LL','RR'] else '负/正'}，符合{first_rotation_type}旋转触发条件。")

# 最终树形态（已旋转后）
print(f"\n（3）旋转调整后的最终AVL树形态:")
print_tree(root)
