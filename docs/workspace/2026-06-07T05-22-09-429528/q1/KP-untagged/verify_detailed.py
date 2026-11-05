"""
详细验证方案2：初始树(20,10)，插入序列(15,30,40,5,3,25,22)
追踪每一步插入后的树结构和旋转
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

def tree_to_dict(node):
    """将树转为字典表示"""
    if not node:
        return None
    return {
        'key': node.key,
        'bf': get_balance(node),
        'left': tree_to_dict(node.left),
        'right': tree_to_dict(node.right)
    }

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def level_order(node):
    """层序遍历"""
    if not node:
        return []
    result = []
    queue = [node]
    while queue:
        current = queue.pop(0)
        if current:
            result.append(current.key)
            queue.append(current.left)
            queue.append(current.right)
        else:
            result.append(None)
    # 移除尾部None
    while result and result[-1] is None:
        result.pop()
    return result

def print_tree(node, prefix="", is_left=True):
    """打印树结构"""
    if node:
        if node.right:
            print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
        print(prefix + ("└── " if is_left else "├── ") + str(node.key) + f" (bf={get_balance(node)}, h={node.height})")
        if node.left:
            print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

# 构建初始树: 20为根, 10为左孩子
root = AVLNode(20)
root.left = AVLNode(10)
root.left.height = 1
root.height = 2

insert_keys = [15, 30, 40, 5, 3, 25, 22]

print("=" * 70)
print("初始树: 20为根, 10为左孩子")
print("=" * 70)
print("树结构:")
print("    20 (bf=1, h=2)")
print("   /")
print(" 10 (bf=0, h=1)")
print(f"层序: {level_order(root)}")
print(f"中序: {inorder(root)}")

rotations = []

for i, key in enumerate(insert_keys, 1):
    print(f"\n{'='*70}")
    print(f"第{i}步: 插入 {key}")
    print(f"{'='*70}")
    
    # BST插入
    def bst_insert(node, key):
        if not node:
            return AVLNode(key)
        if key < node.key:
            node.left = bst_insert(node.left, key)
        else:
            node.right = bst_insert(node.right, key)
        return node
    
    root = bst_insert(root, key)
    
    # 更新高度并检查平衡
    def rebalance(node):
        nonlocal rotations
        if not node:
            return node
        
        update_height(node)
        balance = get_balance(node)
        
        # LL
        if balance > 1 and key < node.left.key:
            rotations.append((i, "LL", node.key, key))
            print(f"  → 失衡节点: {node.key} (bf={balance}), 插入{key}在左子树的左子树 → LL旋转")
            return right_rotate(node)
        
        # RR
        if balance < -1 and key > node.right.key:
            rotations.append((i, "RR", node.key, key))
            print(f"  → 失衡节点: {node.key} (bf={balance}), 插入{key}在右子树的右子树 → RR旋转")
            return left_rotate(node)
        
        # LR
        if balance > 1 and key > node.left.key:
            node.left = left_rotate(node.left)
            rotations.append((i, "LR", node.key, key))
            print(f"  → 失衡节点: {node.key} (bf={balance}), 插入{key}在左子树的右子树 → LR旋转")
            return right_rotate(node)
        
        # RL
        if balance < -1 and key < node.right.key:
            node.right = right_rotate(node.right)
            rotations.append((i, "RL", node.key, key))
            print(f"  → 失衡节点: {node.key} (bf={balance}), 插入{key}在右子树的左子树 → RL旋转")
            return left_rotate(node)
        
        return node
    
    root = rebalance(root)
    
    print(f"  插入后树结构:")
    print(f"  层序: {level_order(root)}")
    print(f"  中序: {inorder(root)}")
    print(f"  树形:")
    print_tree(root)

print(f"\n{'='*70}")
print("旋转汇总")
print(f"{'='*70}")
for step, rtype, center, inserted in rotations:
    print(f"  第{step}步插入{inserted}: {rtype}旋转, 中心节点={center}")

rotation_types = set(r[1] for r in rotations)
print(f"\n旋转类型集合: {rotation_types}")
print(f"LL: {'✓' if 'LL' in rotation_types else '✗'}")
print(f"RR: {'✓' if 'RR' in rotation_types else '✗'}")
print(f"LR: {'✓' if 'LR' in rotation_types else '✗'}")
print(f"RL: {'✓' if 'RL' in rotation_types else '✗'}")
print(f"总旋转次数: {len(rotations)}")

# 最终树
print(f"\n{'='*70}")
print("最终树")
print(f"{'='*70}")
print(f"层序: {level_order(root)}")
print(f"中序: {inorder(root)}")
print(f"树形:")
print_tree(root)

# 计算最终树中每个节点的平衡因子
print(f"\n各节点平衡因子:")
def print_bf(node, depth=0):
    if node:
        print_bf(node.right, depth+1)
        print(f"  {'  '*depth}{node.key}: bf={get_balance(node)}, h={node.height}")
        print_bf(node.left, depth+1)
print_bf(root)

# 验证最终树是AVL树
def is_avl(node):
    if not node:
        return True, 0
    left_ok, left_h = is_avl(node.left)
    right_ok, right_h = is_avl(node.right)
    if not left_ok or not right_ok:
        return False, 0
    if abs(left_h - right_h) > 1:
        return False, 0
    return True, 1 + max(left_h, right_h)

avl_ok, tree_h = is_avl(root)
print(f"\n最终树是否为AVL树: {'✓' if avl_ok else '✗'}")
print(f"树高度: {tree_h}")
