"""验证插入序列 S = [10, 5, 20, 3, 2, 18] 的 AVL 插入过程"""

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def height(node):
    return node.height if node else 0

def bf(node):
    return height(node.left) - height(node.right) if node else 0

def update_height(node):
    node.height = 1 + max(height(node.left), height(node.right))

def right_rotate(z):
    """右旋（用于 LL 型）：z 是失衡节点"""
    y = z.left
    T3 = y.right
    y.right = z
    z.left = T3
    update_height(z)
    update_height(y)
    return y

def left_rotate(z):
    """左旋（用于 RR 型）：z 是失衡节点"""
    y = z.right
    T2 = y.left
    y.left = z
    z.right = T2
    update_height(z)
    update_height(y)
    return y

def insert(root, key):
    # 标准 BST 插入
    if not root:
        return Node(key)
    if key < root.key:
        root.left = insert(root.left, key)
    else:
        root.right = insert(root.right, key)
    
    update_height(root)
    
    # 获取平衡因子
    balance = bf(root)
    
    # LL 型
    if balance > 1 and key < root.left.key:
        return right_rotate(root)
    
    # RR 型
    if balance < -1 and key > root.right.key:
        return left_rotate(root)
    
    # LR 型
    if balance > 1 and key > root.left.key:
        root.left = left_rotate(root.left)
        return right_rotate(root)
    
    # RL 型
    if balance < -1 and key < root.right.key:
        root.right = right_rotate(root.right)
        return left_rotate(root)
    
    return root

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def print_tree(node, prefix="", is_left=True):
    if node:
        print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
        print(prefix + ("└── " if is_left else "┌── ") + str(node.key) + f" (h={node.height}, bf={bf(node)})")
        print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

def check_balanced(node):
    """检查树是否平衡"""
    if not node:
        return True
    balance = bf(node)
    if abs(balance) > 1:
        return False
    return check_balanced(node.left) and check_balanced(node.right)

# 主流程
sequence = [10, 5, 20, 3, 2, 18]
root = None

print("=" * 60)
print("AVL 插入过程验证：S =", sequence)
print("=" * 60)

rotations = []

for i, key in enumerate(sequence, 1):
    old_root = root
    root = insert(root, key)
    
    rotated = (root != old_root) or (old_root and (root.key != old_root.key))
    
    # 检测旋转类型
    rotation_type = None
    rotation_center = None
    
    if i >= 2:  # 至少插入2个节点才可能旋转
        # 通过比较插入前后的结构来判断
        pass
    
    print(f"\n--- 插入第 {i} 个元素: {key} ---")
    print_tree(root)
    print(f"中序遍历: {inorder(root)}")
    print(f"树是否平衡: {check_balanced(root)}")
    
    # 检查根节点是否变化（粗略判断是否旋转）
    if old_root and root.key != old_root.key:
        print(f"⚠️  根节点从 {old_root.key} 变为 {root.key}，发生了旋转")

print("\n" + "=" * 60)
print("最终树结构:")
print("=" * 60)
print_tree(root)
print(f"中序遍历: {inorder(root)}")
print(f"树是否平衡: {check_balanced(root)}")
