# ===== AVL树实现 =====

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
    if node is None:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(z):
    """RR旋转的逆：右旋"""
    y = z.left
    T3 = y.right
    y.right = z
    z.left = T3
    update_height(z)
    update_height(y)
    return y

def left_rotate(z):
    """LL旋转的逆：左旋"""
    y = z.right
    T2 = y.left
    y.left = z
    z.right = T2
    update_height(z)
    update_height(y)
    return y

def insert(node, key, log):
    """插入节点并记录旋转信息"""
    # 标准BST插入
    if node is None:
        return AVLNode(key)
    
    if key < node.key:
        node.left = insert(node.left, key, log)
    else:
        node.right = insert(node.right, key, log)
    
    update_height(node)
    balance = get_balance(node)
    
    # LL情况
    if balance > 1 and key < node.left.key:
        log.append((key, "LL", node.key))
        return right_rotate(node)
    
    # RR情况
    if balance < -1 and key > node.right.key:
        log.append((key, "RR", node.key))
        return left_rotate(node)
    
    # LR情况
    if balance > 1 and key > node.left.key:
        log.append((key, "LR", node.key))
        node.left = left_rotate(node.left)
        return right_rotate(node)
    
    # RL情况
    if balance < -1 and key < node.right.key:
        log.append((key, "RL", node.key))
        node.right = right_rotate(node.right)
        return left_rotate(node)
    
    return node

def print_tree(node, prefix="", is_left=True, level=0):
    """打印树结构"""
    if node is None:
        return
    print_tree(node.right, prefix + ("│   " if is_left else "    "), False, level+1)
    print(prefix + ("└── " if is_left else "┌── ") + str(node.key))
    print_tree(node.left, prefix + ("│   " if is_left else "    "), True, level+1)

def inorder(node, result):
    if node is None:
        return
    inorder(node.left, result)
    result.append(node.key)
    inorder(node.right, result)

def count_leaves(node):
    if node is None:
        return 0
    if node.left is None and node.right is None:
        return 1
    return count_leaves(node.left) + count_leaves(node.right)

def get_tree_height(node):
    if node is None:
        return 0
    return node.height

# ===== 子问题(1) =====
print("=" * 60)
print("子问题(1): 插入前三个关键字 10, 20, 30")
print("=" * 60)

# 先插入10, 20
root1 = None
root1 = insert(root1, 10, [])
root1 = insert(root1, 20, [])

print("插入10, 20后的BST:")
print_tree(root1)

# 插入30，记录旋转
log1 = []
root1 = insert(root1, 30, log1)

print(f"\n插入30后触发的旋转: {log1}")
if log1:
    key, rot_type, center = log1[0]
    print(f"  旋转类型: {rot_type}")
    print(f"  旋转中心节点: {center}")

print("\n旋转调整前的BST结构（插入30后）:")
print("    10")
print("     \\")
print("      20")
print("       \\")
print("        30")
print("  此时节点10的平衡因子 = 左高0 - 右高2 = -2，绝对值>1")
print("  需要进行RR旋转，旋转中心节点为10")

print("\n旋转调整后的AVL树:")
print_tree(root1)

# ===== 子问题(2) =====
print("\n" + "=" * 60)
print("子问题(2): 继续插入剩余关键字")
print("=" * 60)

remaining = [5, 1, 2, 15, 12, 18, 25, 28, 22]
log2 = []

for key in remaining:
    log_before = len(log2)
    root1 = insert(root1, key, log2)
    if len(log2) > log_before:
        # 可能有多个旋转（LR/RL涉及两次旋转但算一次操作）
        rotations = log2[log_before:]
        # 合并LR/RL的两次旋转
        if len(rotations) == 2:
            # LR或RL情况，取第一个作为主要旋转类型
            key_ins, rot_type, center = rotations[0]
            print(f"  插入 {key_ins}: {rot_type}旋转，中心节点={center}")
        else:
            key_ins, rot_type, center = rotations[0]
            print(f"  插入 {key_ins}: {rot_type}旋转，中心节点={center}")
    else:
        print(f"  插入 {key}: 无旋转")

print("\n最终AVL树结构:")
print_tree(root1)

# ===== 子问题(3) =====
print("\n" + "=" * 60)
print("子问题(3): 最终AVL树统计")
print("=" * 60)

height = get_tree_height(root1)
leaves = count_leaves(root1)
inorder_list = []
inorder(root1, inorder_list)

print(f"树的高度（根节点高度为1）: {height}")
print(f"叶子节点个数: {leaves}")
print(f"中序遍历序列: {inorder_list}")

# 验证叶子节点
print("\n叶子节点验证:")
def find_leaves(node, path=""):
    if node is None:
        return []
    if node.left is None and node.right is None:
        return [(node.key, path)]
    result = []
    result.extend(find_leaves(node.left, path + "L"))
    result.extend(find_leaves(node.right, path + "R"))
    return result

leaf_nodes = find_leaves(root1)
for key, path in leaf_nodes:
    print(f"  叶子节点: {key} (路径: {path})")

# 验证高度
print("\n高度验证:")
def verify_height(node, level=1):
    if node is None:
        return 0
    left_h = verify_height(node.left, level + 1)
    right_h = verify_height(node.right, level + 1)
    return max(left_h, right_h)

h = verify_height(root1)
print(f"  递归验证高度: {h}")

# 最终答案汇总
print("\n" + "=" * 60)
print("最终答案汇总")
print("=" * 60)
print(f"(1) 插入30后需RR旋转，中心节点=10")
print(f"(2) 旋转记录见上方输出")
print(f"(3) 高度={height}, 叶子节点数={leaves}, 中序遍历={inorder_list}")
