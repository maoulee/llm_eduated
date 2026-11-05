"""
AVL树插入旋转验证脚本
目标：找到能触发LL、RR、LR、RL四种旋转的插入序列
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

def update_height(node):
    if node:
        node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(z):
    """右旋（LL型）"""
    y = z.left
    T3 = y.right
    y.right = z
    z.left = T3
    update_height(z)
    update_height(y)
    return y

def left_rotate(z):
    """左旋（RR型）"""
    y = z.right
    T2 = y.left
    y.left = z
    z.right = T2
    update_height(z)
    update_height(y)
    return y

rotations_log = []

def insert_avl(root, key):
    """插入节点并平衡，记录旋转"""
    # 标准BST插入
    if not root:
        return AVLNode(key)
    if key < root.key:
        root.left = insert_avl(root.left, key)
    else:
        root.right = insert_avl(root.right, key)
    
    update_height(root)
    balance = get_balance(root)
    
    # LL型：左旋的左子树插入 → 右旋
    if balance > 1 and key < root.left.key:
        rotations_log.append(("LL", root.key, key))
        return right_rotate(root)
    
    # RR型：右子树的右子树插入 → 左旋
    if balance < -1 and key > root.right.key:
        rotations_log.append(("RR", root.key, key))
        return left_rotate(root)
    
    # LR型：左子树的右子树插入 → 先左旋后右旋
    if balance > 1 and key > root.left.key:
        root.left = left_rotate(root.left)
        rotations_log.append(("LR", root.key, key))
        return right_rotate(root)
    
    # RL型：右子树的左子树插入 → 先右旋后左旋
    if balance < -1 and key < root.right.key:
        root.right = right_rotate(root.right)
        rotations_log.append(("RL", root.key, key))
        return left_rotate(root)
    
    return root

def build_initial_tree(keys):
    """从键列表构建初始树（不触发旋转，假设已平衡）"""
    if not keys:
        return None
    root = AVLNode(keys[0])
    for key in keys[1:]:
        # 直接插入，不记录旋转（初始树假设已平衡）
        if key < root.key:
            root.left = AVLNode(key)
        else:
            root.right = AVLNode(key)
    # 更新高度
    def update_all(node):
        if not node:
            return 0
        h = 1 + max(update_all(node.left), update_all(node.right))
        node.height = h
        return h
    update_all(root)
    return root

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def test_sequence(initial_keys, insert_keys, name):
    """测试一个插入序列"""
    global rotations_log
    rotations_log = []
    
    root = build_initial_tree(initial_keys)
    
    for key in insert_keys:
        root = insert_avl(root, key)
    
    rotation_types = set(r[0] for r in rotations_log)
    
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"初始树: {initial_keys}")
    print(f"插入序列: {insert_keys}")
    print(f"旋转记录: {rotations_log}")
    print(f"旋转类型: {rotation_types}")
    print(f"覆盖LL: {'✓' if 'LL' in rotation_types else '✗'}")
    print(f"覆盖RR: {'✓' if 'RR' in rotation_types else '✗'}")
    print(f"覆盖LR: {'✓' if 'LR' in rotation_types else '✗'}")
    print(f"覆盖RL: {'✓' if 'RL' in rotation_types else '✗'}")
    print(f"中序遍历: {inorder(root)}")
    print(f"旋转次数: {len(rotations_log)}")
    
    return rotation_types

# 测试多个序列
print("=" * 60)
print("AVL树插入旋转验证")
print("=" * 60)

# 方案1: 初始树(20,10,30)，插入(15,5,3,35,40,25)
test_sequence([20, 10, 30], [15, 5, 3, 35, 40, 25], "方案1")

# 方案2: 初始树(20,10)，插入(15,30,40,5,3,25,22)
test_sequence([20, 10], [15, 30, 40, 5, 3, 25, 22], "方案2")

# 方案3: 初始树(20)，插入(10,15,30,40,5,3,25,22)
test_sequence([20], [10, 15, 30, 40, 5, 3, 25, 22], "方案3")

# 方案4: 初始树(20,10,30)，插入(25,35,40,5,3,15,12)
test_sequence([20, 10, 30], [25, 35, 40, 5, 3, 15, 12], "方案4")

# 方案5: 初始树(20,10,30)，插入(5,3,35,40,15,12)
test_sequence([20, 10, 30], [5, 3, 35, 40, 15, 12], "方案5")

# 方案6: 初始树(20,10,30)，插入(25,15,5,3,35,40)
test_sequence([20, 10, 30], [25, 15, 5, 3, 35, 40], "方案6")

# 方案7: 初始树(20,10,30)，插入(5,7,35,33,15,12)
test_sequence([20, 10, 30], [5, 7, 35, 33, 15, 12], "方案7")

# 方案8: 初始树(20,10,30)，插入(35,40,5,3,15,12)
test_sequence([20, 10, 30], [35, 40, 5, 3, 15, 12], "方案8")

# 方案9: 初始树(20,10,30)，插入(5,3,35,40,12,15)
test_sequence([20, 10, 30], [5, 3, 35, 40, 12, 15], "方案9")

# 方案10: 初始树(20,10,30)，插入(35,40,5,3,12,15)
test_sequence([20, 10, 30], [35, 40, 5, 3, 12, 15], "方案10")

# 方案11: 初始树(20,10,30)，插入(5,7,35,33,12,15)
test_sequence([20, 10, 30], [5, 7, 35, 33, 12, 15], "方案11")

# 方案12: 初始树(20,10,30)，插入(3,5,35,40,12,15)
test_sequence([20, 10, 30], [3, 5, 35, 40, 12, 15], "方案12")

# 方案13: 初始树(20,10,30)，插入(35,40,3,5,12,15)
test_sequence([20, 10, 30], [35, 40, 3, 5, 12, 15], "方案13")

# 方案14: 初始树(20,10,30)，插入(5,3,35,40,15,12)
test_sequence([20, 10, 30], [5, 3, 35, 40, 15, 12], "方案14")

# 方案15: 初始树(20,10,30)，插入(35,40,5,3,15,12)
test_sequence([20, 10, 30], [35, 40, 5, 3, 15, 12], "方案15")

# 方案16: 初始树(20,10,30)，插入(5,3,35,40,12,8)
test_sequence([20, 10, 30], [5, 3, 35, 40, 12, 8], "方案16")

# 方案17: 初始树(20,10,30)，插入(35,40,5,3,12,8)
test_sequence([20, 10, 30], [35, 40, 5, 3, 12, 8], "方案17")

# 方案18: 初始树(20,10,30)，插入(5,7,35,33,12,8)
test_sequence([20, 10, 30], [5, 7, 35, 33, 12, 8], "方案18")

# 方案19: 初始树(20,10,30)，插入(35,33,5,7,12,8)
test_sequence([20, 10, 30], [35, 33, 5, 7, 12, 8], "方案19")

# 方案20: 初始树(20,10,30)，插入(5,3,35,40,12,18)
test_sequence([20, 10, 30], [5, 3, 35, 40, 12, 18], "方案20")

# 方案21: 初始树(20,10,30)，插入(35,40,5,3,12,18)
test_sequence([20, 10, 30], [35, 40, 5, 3, 12, 18], "方案21")

# 方案22: 初始树(20,10,30)，插入(5,7,35,33,12,18)
test_sequence([20, 10, 30], [5, 7, 35, 33, 12, 18], "方案22")

# 方案23: 初始树(20,10,30)，插入(35,33,5,7,12,18)
test_sequence([20, 10, 30], [35, 33, 5, 7, 12, 18], "方案23")
