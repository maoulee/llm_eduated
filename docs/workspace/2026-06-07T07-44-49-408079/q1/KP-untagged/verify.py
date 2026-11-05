"""验证AVL树插入序列参数设计 - 完整模拟"""

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    return node.height if node else 0

def get_balance(node):
    return get_height(node.left) - get_height(node.right) if node else 0

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

def insert(root, key):
    rotations = []
    
    # Standard BST insert
    if not root:
        return Node(key), rotations
    
    if key < root.key:
        root.left, r = insert(root.left, key)
        rotations.extend(r)
    else:
        root.right, r = insert(root.right, key)
        rotations.extend(r)
    
    update_height(root)
    balance = get_balance(root)
    
    # LL case
    if balance > 1 and key < root.left.key:
        rotations.append(("LL", root.key))
        return right_rotate(root), rotations
    
    # RR case
    if balance < -1 and key > root.right.key:
        rotations.append(("RR", root.key))
        return left_rotate(root), rotations
    
    # LR case
    if balance > 1 and key > root.left.key:
        rotations.append(("LR", root.key))
        root.left = left_rotate(root.left)
        return right_rotate(root), rotations
    
    # RL case
    if balance < -1 and key < root.right.key:
        rotations.append(("RL", root.key))
        root.right = right_rotate(root.right)
        return left_rotate(root), rotations
    
    return root, rotations

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def verify():
    errors = []
    
    # 插入序列
    seq = [10, 20, 30, 5, 1, 2, 15, 12, 18, 25, 28, 22]
    
    root = None
    all_rotations = []
    
    for val in seq:
        root, rots = insert(root, val)
        for rot_type, rot_node in rots:
            all_rotations.append((val, rot_type, rot_node))
    
    # 检查旋转类型
    rotation_types = set(r[1] for r in all_rotations)
    print(f"插入序列: {seq}")
    print(f"旋转记录: {all_rotations}")
    print(f"旋转类型: {rotation_types}")
    
    # 检查是否包含四种旋转
    expected = {"LL", "RR", "LR", "RL"}
    missing = expected - rotation_types
    if missing:
        print(f"缺失旋转类型: {missing}")
    else:
        print("✓ 包含全部四种旋转类型")
    
    # 检查最终树的中序遍历
    inorder_result = inorder(root)
    print(f"中序遍历: {inorder_result}")
    print(f"排序后:   {sorted(seq)}")
    
    if inorder_result != sorted(seq):
        errors.append("中序遍历不等于排序后的序列")
    
    # 检查所有节点平衡因子
    def check_balance(node):
        if not node:
            return True
        bf = get_balance(node)
        if abs(bf) > 1:
            print(f"节点{node.key}平衡因子为{bf}，不平衡！")
            return False
        return check_balance(node.left) and check_balance(node.right)
    
    if not check_balance(root):
        errors.append("最终树不平衡")
    else:
        print("✓ 最终树平衡")
    
    # 检查序列长度
    if len(seq) < 8 or len(seq) > 15:
        errors.append(f"序列长度{len(seq)}不在合理范围[8,15]")
    
    # 检查值互不相同
    if len(set(seq)) != len(seq):
        errors.append("序列中存在重复值")
    
    # 检查值范围
    if max(seq) > 100 or min(seq) < 0:
        errors.append(f"值范围[{min(seq)},{max(seq)}]不够友好")
    
    if errors:
        print("\n验证失败:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n验证通过!")
    
    return len(errors) == 0

verify()
