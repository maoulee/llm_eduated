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
    """平衡因子 = 左子树高度 - 右子树高度"""
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

def insert(root, key, depth=0):
    """插入节点，返回 (新根, 旋转信息)"""
    indent = "  " * depth
    rotation_info = None
    
    # 标准 BST 插入
    if not root:
        return Node(key), None
    
    if key < root.key:
        root.left, rot = insert(root.left, key, depth+1)
        if rot:
            rotation_info = rot
    elif key > root.key:
        root.right, rot = insert(root.right, key, depth+1)
        if rot:
            rotation_info = rot
    else:
        return root, None  # 重复键不插入
    
    update_height(root)
    
    # 检查平衡因子
    balance = get_balance(root)
    print(f"{indent}节点 {root.key}: 高度={root.height}, 平衡因子={balance}")
    
    # LL 情况
    if balance > 1 and key < root.left.key:
        rotation_info = ("LL", root.key)
        print(f"{indent}触发 LL 旋转，失衡节点={root.key}")
        return right_rotate(root), rotation_info
    
    # RR 情况
    if balance < -1 and key > root.right.key:
        rotation_info = ("RR", root.key)
        print(f"{indent}触发 RR 旋转，失衡节点={root.key}")
        return left_rotate(root), rotation_info
    
    # LR 情况
    if balance > 1 and key > root.left.key:
        rotation_info = ("LR", root.key)
        print(f"{indent}触发 LR 旋转，失衡节点={root.key}")
        root.left = left_rotate(root.left)
        return right_rotate(root), rotation_info
    
    # RL 情况
    if balance < -1 and key < root.right.key:
        rotation_info = ("RL", root.key)
        print(f"{indent}触发 RL 旋转，失衡节点={root.key}")
        root.right = right_rotate(root.right)
        return left_rotate(root), rotation_info
    
    return root, rotation_info

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def build_initial_tree():
    """构建初始 AVL 树: 40(0) -> 20(0),60(0) -> 10,30,50,70"""
    root = Node(40)
    root.left = Node(20)
    root.right = Node(60)
    root.left.left = Node(10)
    root.left.right = Node(30)
    root.right.left = Node(50)
    root.right.right = Node(70)
    # 更新高度
    for node in [root.left.left, root.left.right, root.right.left, root.right.right,
                 root.left, root.right, root]:
        update_height(node)
    return root

# 构建初始树
root = build_initial_tree()
print("初始树中序遍历:", inorder(root))

# 依次插入 80, 90, 5, 1
insertions = [80, 90, 5, 1]
rotation_sequence = []

for key in insertions:
    print(f"\n{'='*40}")
    print(f"插入节点 {key}")
    print(f"{'='*40}")
    root, rotation_info = insert(root, key)
    print(f"中序遍历: {inorder(root)}")
    print(f"根节点: {root.key}")
    
    if rotation_info:
        rot_type, rot_node = rotation_info
        print(f"发生旋转: 类型={rot_type}, 失衡节点={rot_node}, 旋转后根={root.key}")
        rotation_sequence.append(rot_type)
    else:
        print(f"未发生旋转")

print(f"\n{'='*40}")
print("=== 汇总 ===")
print(f"共发生 {len(rotation_sequence)} 次旋转")
print(f"旋转类型序列: {' -> '.join(rotation_sequence)}")
