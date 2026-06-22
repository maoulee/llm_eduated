"""
独立验证AVL树插入序列 [10, 15, 5, 12, 13, 18, 3] 的每一步
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

def insert(node, key):
    if not node:
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

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def print_tree(node, prefix="", is_left=True, file=None):
    if node:
        print_tree(node.right, prefix + ("│   " if is_left else "    "), False, file)
        print(f"{prefix}{'└── ' if is_left else '┌── '}{node.key} (BF={get_balance(node)})", file=file)
        print_tree(node.left, prefix + ("    " if is_left else "│   "), True, file)

def get_all_bfs(node):
    """Get all nodes with their BF"""
    result = {}
    def dfs(n):
        if n:
            result[n.key] = get_balance(n)
            dfs(n.left)
            dfs(n.right)
    dfs(node)
    return result

def get_tree_structure(node):
    """Get tree structure as dict for comparison"""
    if not node:
        return None
    return {
        'key': node.key,
        'left': get_tree_structure(node.left),
        'right': get_tree_structure(node.right),
        'bf': get_balance(node)
    }

# 验证序列
sequence = [10, 15, 5, 12, 13, 18, 3]
root = None

print("=" * 60)
print("逐步插入验证")
print("=" * 60)

for i, key in enumerate(sequence):
    root = insert(root, key)
    bfs = get_all_bfs(root)
    print(f"\n插入 {key} 后:")
    print(f"树结构:")
    print_tree(root)
    print(f"各节点BF: {bfs}")
    
    # 检查是否平衡
    all_balanced = all(abs(bf) <= 1 for bf in bfs.values())
    print(f"是否平衡: {all_balanced}")
    
    if i == 3:
        print("\n>>> 子问题(1) 答案验证:")
        print(f"树结构: {get_tree_structure(root)}")
        print(f"各节点BF: {bfs}")
    
    if i == 4:
        print("\n>>> 子问题(2) 答案验证:")
        print(f"树结构: {get_tree_structure(root)}")
        print(f"各节点BF: {bfs}")
    
    if i == 5:
        print("\n>>> 子问题(3) 插入18后验证:")
        print(f"树结构: {get_tree_structure(root)}")
        print(f"各节点BF: {bfs}")
    
    if i == 6:
        print("\n>>> 子问题(3) 插入3后验证:")
        print(f"树结构: {get_tree_structure(root)}")
        print(f"各节点BF: {bfs}")

print("\n" + "=" * 60)
print("最终树的中序遍历:", inorder(root))
print("=" * 60)

# 验证solution中的关键断言
print("\n\n=== 关键断言验证 ===")

# (1) 插入10,15,5,12后
root1 = None
for key in [10, 15, 5, 12]:
    root1 = insert(root1, key)
bfs1 = get_all_bfs(root1)
print(f"\n(1) 插入10,15,5,12后:")
print(f"  根节点: {root1.key} (期望: 10)")
print(f"  10的BF: {bfs1[10]} (期望: -1)")
print(f"  5的BF: {bfs1[5]} (期望: 0)")
print(f"  15的BF: {bfs1[15]} (期望: 1)")
print(f"  12的BF: {bfs1[12]} (期望: 0)")
print(f"  15的左子: {root1.right.left.key if root1.right and root1.right.left else None} (期望: 12)")
assert root1.key == 10
assert bfs1[10] == -1
assert bfs1[5] == 0
assert bfs1[15] == 1
assert bfs1[12] == 0
print("  ✅ 全部匹配")

# (2) 插入13后
root2 = insert(root1, 13)
bfs2 = get_all_bfs(root2)
print(f"\n(2) 插入13后:")
print(f"  根节点: {root2.key} (期望: 10)")
print(f"  10的BF: {bfs2[10]} (期望: -1)")
print(f"  5的BF: {bfs2[5]} (期望: 0)")
print(f"  13的BF: {bfs2[13]} (期望: 0)")
print(f"  12的BF: {bfs2[12]} (期望: 0)")
print(f"  15的BF: {bfs2[15]} (期望: 0)")
print(f"  10的右子: {root2.right.key} (期望: 13)")
print(f"  13的左子: {root2.right.left.key} (期望: 12)")
print(f"  13的右子: {root2.right.right.key} (期望: 15)")
assert root2.key == 10
assert bfs2[10] == -1
assert bfs2[5] == 0
assert bfs2[13] == 0
assert bfs2[12] == 0
assert bfs2[15] == 0
assert root2.right.key == 13
assert root2.right.left.key == 12
assert root2.right.right.key == 15
print("  ✅ 全部匹配")

# (3) 插入18后
root3 = insert(root2, 18)
bfs3 = get_all_bfs(root3)
print(f"\n(3) 插入18后:")
print(f"  根节点: {root3.key} (期望: 13)")
print(f"  13的BF: {bfs3[13]} (期望: 0)")
print(f"  10的BF: {bfs3[10]} (期望: 0)")
print(f"  5的BF: {bfs3[5]} (期望: 0)")
print(f"  12的BF: {bfs3[12]} (期望: 0)")
print(f"  15的BF: {bfs3[15]} (期望: -1)")
print(f"  18的BF: {bfs3[18]} (期望: 0)")
assert root3.key == 13
assert bfs3[13] == 0
assert bfs3[10] == 0
assert bfs3[5] == 0
assert bfs3[12] == 0
assert bfs3[15] == -1
assert bfs3[18] == 0
print("  ✅ 全部匹配")

# (3) 插入3后
root4 = insert(root3, 3)
bfs4 = get_all_bfs(root4)
print(f"\n(3) 插入3后:")
print(f"  根节点: {root4.key} (期望: 13)")
print(f"  13的BF: {bfs4[13]} (期望: 1)")
print(f"  10的BF: {bfs4[10]} (期望: 1)")
print(f"  5的BF: {bfs4[5]} (期望: 1)")
print(f"  3的BF: {bfs4[3]} (期望: 0)")
print(f"  12的BF: {bfs4[12]} (期望: 0)")
print(f"  15的BF: {bfs4[15]} (期望: -1)")
print(f"  18的BF: {bfs4[18]} (期望: 0)")
assert root4.key == 13
assert bfs4[13] == 1
assert bfs4[10] == 1
assert bfs4[5] == 1
assert bfs4[3] == 0
assert bfs4[12] == 0
assert bfs4[15] == -1
assert bfs4[18] == 0
print("  ✅ 全部匹配")

# 中序遍历
inorder_result = inorder(root4)
print(f"\n中序遍历: {inorder_result}")
print(f"期望: [3, 5, 10, 12, 13, 15, 18]")
assert inorder_result == [3, 5, 10, 12, 13, 15, 18]
print("  ✅ 匹配")

print("\n\n=== 所有断言通过 ===")
