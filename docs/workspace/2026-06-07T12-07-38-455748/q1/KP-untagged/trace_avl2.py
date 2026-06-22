"""
详细追踪AVL树插入过程，验证旋转类型和最终树结构。
"""

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

def insert(root, key):
    if not root:
        return Node(key)
    
    if key < root.key:
        root.left = insert(root.left, key)
    else:
        root.right = insert(root.right, key)
    
    update_height(root)
    balance = get_balance(root)
    
    # LL case
    if balance > 1 and key < root.left.key:
        print(f"  -> LL rotation at node {root.key}")
        return right_rotate(root)
    
    # RR case
    if balance < -1 and key > root.right.key:
        print(f"  -> RR rotation at node {root.key}")
        return left_rotate(root)
    
    # LR case
    if balance > 1 and key > root.left.key:
        print(f"  -> LR rotation at node {root.key}")
        root.left = left_rotate(root.left)
        return right_rotate(root)
    
    # RL case
    if balance < -1 and key < root.right.key:
        print(f"  -> RL rotation at node {root.key}")
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

def level_order(node):
    if not node:
        return []
    result = []
    queue = [node]
    while queue:
        current = queue.pop(0)
        if current:
            bf = get_balance(current)
            result.append(f"{current.key}(BF={bf},H={current.height})")
            queue.append(current.left)
            queue.append(current.right)
        else:
            result.append("None")
    return result

def print_tree_ascii(node, prefix="", is_left=True):
    if node is not None:
        print_tree_ascii(node.right, prefix + ("│   " if is_left else "    "), False)
        bf = get_balance(node)
        print(prefix + ("└── " if is_left else "┌── ") + f"{node.key}(BF={bf})")
        print_tree_ascii(node.left, prefix + ("    " if is_left else "│   "), True)

def count_nodes(node):
    if not node:
        return 0
    return 1 + count_nodes(node.left) + count_nodes(node.right)

def get_all_bfs(node):
    if not node:
        return {}
    bfs = {node.key: get_balance(node)}
    bfs.update(get_all_bfs(node.left))
    bfs.update(get_all_bfs(node.right))
    return bfs

def get_depths(node, depth=1):
    if not node:
        return {}
    depths = {node.key: depth}
    depths.update(get_depths(node.left, depth + 1))
    depths.update(get_depths(node.right, depth + 1))
    return depths

# 使用序列: 30, 20, 25, 40, 35, 45, 10, 5, 15, 2
print("=" * 60)
print("Sequence: 30, 20, 25, 40, 35, 45, 10, 5, 15, 2")
print("=" * 60)
seq = [30, 20, 25, 40, 35, 45, 10, 5, 15, 2]
root = None
rotations = []
for key in seq:
    print(f"\nInsert {key}:")
    root = insert(root, key)

print("\n" + "=" * 60)
print("Final Analysis")
print("=" * 60)
print(f"\nInorder traversal: {inorder(root)}")
print(f"Level order: {level_order(root)}")
print(f"\nTotal nodes: {count_nodes(root)}")
print(f"Balances: {get_all_bfs(root)}")
print(f"Depths: {get_depths(root)}")

depths = get_depths(root)
total_depth = sum(depths.values())
n = len(depths)
asl = total_depth / n
print(f"\nASL (successful) = {total_depth}/{n} = {asl:.4f}")

print("\nFinal tree (ASCII):")
print_tree_ascii(root)

# 统计旋转类型
print("\n" + "=" * 60)
print("Rotation Summary")
print("=" * 60)
print("Rotations occurred during insertion:")
print("1. Insert 25: LR rotation at node 30")
print("2. Insert 35: RL rotation at node 30")
print("3. Insert 45: RR rotation at node 25")
print("4. Insert 5:  LL rotation at node 20")
print("5. Insert 15: LR rotation at node 25")
print("6. Insert 2:  LL rotation at node 35")
print("\nRotation types: LL(2), RR(1), LR(2), RL(1)")
print("All four rotation types are covered!")
