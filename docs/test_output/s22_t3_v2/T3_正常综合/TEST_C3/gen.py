"""
Q41 AVL树插入与旋转 - 参数构造与验证
"""

class AVLNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1
    
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
    if node:
        node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(z):
    """右旋（用于LL情况）"""
    x = z.left
    T2 = x.right
    x.right = z
    z.left = T2
    update_height(z)
    update_height(x)
    return x

def left_rotate(z):
    """左旋（用于RR情况）"""
    y = z.right
    T2 = y.left
    y.left = z
    z.right = T2
    update_height(z)
    update_height(y)
    return y

def insert_node(root, key):
    """标准AVL插入，返回(新根, 旋转类型, 失衡节点)"""
    if root is None:
        return AVLNode(key), None, None
    
    if key < root.key:
        root.left, rotation, imbalance = insert_node(root.left, key)
    else:
        root.right, rotation, imbalance = insert_node(root.right, key)
    
    update_height(root)
    balance = get_balance(root)
    
    # LL
    if balance > 1 and key < root.left.key:
        return right_rotate(root), "LL", root.key
    # RR
    if balance < -1 and key > root.right.key:
        return left_rotate(root), "RR", root.key
    # LR
    if balance > 1 and key > root.left.key:
        root.left = left_rotate(root.left)
        return right_rotate(root), "LR", root.key
    # RL
    if balance < -1 and key < root.right.key:
        root.right = right_rotate(root.right)
        return left_rotate(root), "RL", root.key
    
    return root, None, None

def print_tree(node, prefix="", is_left=True):
    """打印树结构"""
    if node is None:
        return
    print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
    print(prefix + ("└── " if is_left else "┌── ") + str(node.key))
    print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

def get_all_keys(node):
    if node is None:
        return []
    return get_all_keys(node.left) + [node.key] + get_all_keys(node.right)

def print_balances(node):
    if node is None:
        return
    print_balances(node.left)
    print(f"节点 {node.key}: BF = {get_balance(node)}")
    print_balances(node.right)

# ===== 初始树 + 插入序列 =====
# 初始树：
#       20
#      /  \
#     10   30
#    /
#   5
# 
# 插入 35 → 不触发旋转
# 插入 7  → 触发LR旋转（以10为根的最小不平衡子树）
# 插入 40 → 触发RR旋转（以30为根的最小不平衡子树）

def build_initial_tree():
    """
          20
         /  \
       10    30
      /
     5
    """
    root = AVLNode(20)
    root.left = AVLNode(10)
    root.right = AVLNode(30)
    root.left.left = AVLNode(5)
    
    update_height(root.left.left)
    update_height(root.left)
    update_height(root.right)
    update_height(root)
    
    return root

print("===== 初始AVL树 =====")
root = build_initial_tree()
print_tree(root)
print(f"节点集合: {get_all_keys(root)}")
print("各节点平衡因子:")
print_balances(root)

insert_sequence = [35, 7, 40]

print("\n===== 插入过程 =====")
rotations = []
for key in insert_sequence:
    print(f"\n--- 插入节点 {key} ---")
    root, rotation, imbalance = insert_node(root, key)
    if rotation:
        print(f"失衡节点: {imbalance}")
        print(f"旋转类型: {rotation}")
        rotations.append(rotation)
    else:
        print("未触发旋转")
    print("当前树形态:")
    print_tree(root)
    print("各节点平衡因子:")
    print_balances(root)
    print(f"当前节点集合: {get_all_keys(root)}")

print("\n===== 最终树形态 =====")
print_tree(root)
print(f"最终节点集合: {get_all_keys(root)}")

print("\n===== 旋转类型统计 =====")
print(f"触发的旋转类型: {rotations}")
print(f"共 {len(set(rotations))} 种旋转类型")

# ===== 题干描述 =====
print("\n===== 题干描述 =====")
print("""已知一棵 AVL 树（平衡二叉排序树），其初始形态如下：

        20
       /  \\
     10    30
    /
   5

其中每个节点的平衡因子定义为：左子树高度 − 右子树高度。

现按顺序向该 AVL 树中插入节点 35、7 和 40。请完成以下问题：

(1) 插入节点 35 后，判断是否触发旋转。若触发，指出失衡节点（最小不平衡子树的根），计算其平衡因子，并说明应执行何种旋转（LL/RR/LR/RL）；若未触发，说明理由。

(2) 在(1)得到的 AVL 树基础上，插入节点 7。指出此时失衡的节点（最小不平衡子树的根），计算其平衡因子，判断应执行的旋转类型，并画出旋转后的 AVL 树形态（标出各节点平衡因子）。

(3) 在(2)得到的 AVL 树基础上，继续插入节点 40。指出此时失衡的节点，判断应执行的旋转类型，并画出最终的 AVL 树形态（标出各节点平衡因子）。""")
