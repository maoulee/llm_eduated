"""
AVL 题目设计验证脚本
验证初始树合法性 + 插入序列触发的旋转类型
"""

class AVLNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def height(node):
    if node is None:
        return 0
    return node.height

def balance_factor(node):
    if node is None:
        return 0
    return height(node.left) - height(node.right)

def update_height(node):
    node.height = 1 + max(height(node.left), height(node.right))

def rotate_right(y):
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    update_height(y)
    update_height(x)
    return x

def rotate_left(x):
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    update_height(x)
    update_height(y)
    return y

rotation_log = []

def insert(node, key):
    if node is None:
        return AVLNode(key)
    
    if key < node.key:
        node.left = insert(node.left, key)
    else:
        node.right = insert(node.right, key)
    
    update_height(node)
    
    bf = balance_factor(node)
    
    # LL
    if bf > 1 and key < node.left.key:
        rotation_log.append(f"LL at {node.key} (insert {key})")
        return rotate_right(node)
    # RR
    if bf < -1 and key > node.right.key:
        rotation_log.append(f"RR at {node.key} (insert {key})")
        return rotate_left(node)
    # LR
    if bf > 1 and key > node.left.key:
        rotation_log.append(f"LR at {node.key} (insert {key})")
        node.left = rotate_left(node.left)
        return rotate_right(node)
    # RL
    if bf < -1 and key < node.right.key:
        rotation_log.append(f"RL at {node.key} (insert {key})")
        node.right = rotate_right(node.right)
        return rotate_left(node)
    
    return node

def print_tree(node, level=0, prefix="Root: "):
    if node is not None:
        bf = balance_factor(node)
        print("  " * level + f"{prefix}{node.key} (BF={bf})")
        if node.left or node.right:
            if node.left:
                print_tree(node.left, level + 1, "L--- ")
            else:
                print("  " * (level + 1) + "L--- NULL")
            if node.right:
                print_tree(node.right, level + 1, "R--- ")
            else:
                print("  " * (level + 1) + "R--- NULL")

def is_avl(node):
    """验证是否为合法AVL树"""
    if node is None:
        return True, 0
    left_ok, lh = is_avl(node.left)
    right_ok, rh = is_avl(node.right)
    bf = lh - rh
    ok = left_ok and right_ok and abs(bf) <= 1
    if not ok:
        print(f"  NOT AVL at {node.key}: bf={bf}")
    return ok, 1 + max(lh, rh)

def inorder(node):
    if node is None:
        return []
    return inorder(node.left) + [node.key] + inorder(node.right)

# ===== 构建初始AVL树 =====
# 手动构建: 30, 20, 40, 10, 50, 25, 5
print("="*60)
print("逐步构建初始AVL树")
print("="*60)

root = None
init_keys = [30, 20, 40, 10, 50, 25, 5]
for k in init_keys:
    rotation_log.clear()
    root = insert(root, k)
    if rotation_log:
        print(f"  插入 {k}: {'; '.join(rotation_log)}")
    else:
        print(f"  插入 {k}: 无旋转")

print("\n初始AVL树结构:")
print_tree(root)
ok, _ = is_avl(root)
print(f"AVL合法: {ok}")
print(f"中序遍历: {inorder(root)}")

# ===== 第一次插入: 8 (触发LR旋转) =====
print("\n" + "="*60)
print("插入 8")
print("="*60)
rotation_log.clear()
root = insert(root, 8)
print(f"旋转日志: {rotation_log}")
print("\n插入8后的树结构:")
print_tree(root)
ok, _ = is_avl(root)
print(f"AVL合法: {ok}")
print(f"中序遍历: {inorder(root)}")

# ===== 第二次插入: 35 (触发RL旋转) =====
# 先检查当前树结构，设计能触发RL的插入
print("\n" + "="*60)
print("插入 35")
print("="*60)
rotation_log.clear()
root = insert(root, 35)
print(f"旋转日志: {rotation_log}")
print("\n插入35后的树结构:")
print_tree(root)
ok, _ = is_avl(root)
print(f"AVL合法: {ok}")
print(f"中序遍历: {inorder(root)}")

# ===== 尝试更多插入 =====
for test_key in [45, 28, 12, 33]:
    print(f"\n尝试插入 {test_key}:")
    rotation_log.clear()
    import copy
    # 创建树的深拷贝进行测试
    test_root = None
    rebuild_keys = [30, 20, 40, 10, 50, 25, 5, 8, 35]
    for k in rebuild_keys:
        test_root = insert(test_root, k)
    rotation_log.clear()
    test_root = insert(test_root, test_key)
    if rotation_log:
        print(f"  旋转日志: {rotation_log}")
        print("  树结构:")
        print_tree(test_root)
    else:
        print(f"  无旋转")
