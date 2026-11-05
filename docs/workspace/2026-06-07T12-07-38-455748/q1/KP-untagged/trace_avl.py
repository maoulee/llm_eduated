"""
追踪AVL树插入过程，验证旋转类型和最终树结构。
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

def insert(root, key, path=None):
    if path is None:
        path = []
    
    if not root:
        return Node(key)
    
    if key < root.key:
        root.left = insert(root.left, key, path + ['L'])
    else:
        root.right = insert(root.right, key, path + ['R'])
    
    update_height(root)
    balance = get_balance(root)
    
    # LL case
    if balance > 1 and key < root.left.key:
        print(f"  LL rotation at node {root.key}")
        return right_rotate(root)
    
    # RR case
    if balance < -1 and key > root.right.key:
        print(f"  RR rotation at node {root.key}")
        return left_rotate(root)
    
    # LR case
    if balance > 1 and key > root.left.key:
        print(f"  LR rotation at node {root.key}")
        root.left = left_rotate(root.left)
        return right_rotate(root)
    
    # RL case
    if balance < -1 and key < root.right.key:
        print(f"  RL rotation at node {root.key}")
        root.right = right_rotate(root.right)
        return left_rotate(root)
    
    return root

def print_tree(node, prefix="", is_left=True):
    if node is not None:
        print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
        bf = get_balance(node)
        print(prefix + ("└── " if is_left else "┌── ") + f"{node.key}(BF={bf})")
        print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

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

# Test sequence 1: 10, 20, 30, 40, 50, 25, 5, 15, 35, 45
print("=" * 60)
print("Sequence: 10, 20, 30, 40, 50, 25, 5, 15, 35, 45")
print("=" * 60)
seq1 = [10, 20, 30, 40, 50, 25, 5, 15, 35, 45]
root = None
rotations = []
for key in seq1:
    print(f"\nInsert {key}:")
    root = insert(root, key)

print("\nFinal tree:")
print_tree(root)
print(f"\nTotal nodes: {count_nodes(root)}")
print(f"Balances: {get_all_bfs(root)}")

# Test sequence 2: 30, 20, 40, 10, 25, 35, 45, 5, 15, 3
print("\n" + "=" * 60)
print("Sequence: 30, 20, 40, 10, 25, 35, 45, 5, 15, 3")
print("=" * 60)
seq2 = [30, 20, 40, 10, 25, 35, 45, 5, 15, 3]
root = None
for key in seq2:
    print(f"\nInsert {key}:")
    root = insert(root, key)

print("\nFinal tree:")
print_tree(root)
print(f"\nTotal nodes: {count_nodes(root)}")
print(f"Balances: {get_all_bfs(root)}")

# Test sequence 3: 50, 30, 70, 20, 40, 60, 80, 25, 35, 15
print("\n" + "=" * 60)
print("Sequence: 50, 30, 70, 20, 40, 60, 80, 25, 35, 15")
print("=" * 60)
seq3 = [50, 30, 70, 20, 40, 60, 80, 25, 35, 15]
root = None
for key in seq3:
    print(f"\nInsert {key}:")
    root = insert(root, key)

print("\nFinal tree:")
print_tree(root)
print(f"\nTotal nodes: {count_nodes(root)}")
print(f"Balances: {get_all_bfs(root)}")

# Test sequence 4: 30, 20, 25, 40, 35, 45, 10, 5, 15, 2
print("\n" + "=" * 60)
print("Sequence: 30, 20, 25, 40, 35, 45, 10, 5, 15, 2")
print("=" * 60)
seq4 = [30, 20, 25, 40, 35, 45, 10, 5, 15, 2]
root = None
for key in seq4:
    print(f"\nInsert {key}:")
    root = insert(root, key)

print("\nFinal tree:")
print_tree(root)
print(f"\nTotal nodes: {count_nodes(root)}")
print(f"Balances: {get_all_bfs(root)}")

# Test sequence 5: 10, 20, 30, 15, 25, 5, 35, 40, 45, 50
print("\n" + "=" * 60)
print("Sequence: 10, 20, 30, 15, 25, 5, 35, 40, 45, 50")
print("=" * 60)
seq5 = [10, 20, 30, 15, 25, 5, 35, 40, 45, 50]
root = None
for key in seq5:
    print(f"\nInsert {key}:")
    root = insert(root, key)

print("\nFinal tree:")
print_tree(root)
print(f"\nTotal nodes: {count_nodes(root)}")
print(f"Balances: {get_all_bfs(root)}")

# Test sequence 6: 40, 20, 60, 10, 30, 50, 70, 25, 35, 55
print("\n" + "=" * 60)
print("Sequence: 40, 20, 60, 10, 30, 50, 70, 25, 35, 55")
print("=" * 60)
seq6 = [40, 20, 60, 10, 30, 50, 70, 25, 35, 55]
root = None
for key in seq6:
    print(f"\nInsert {key}:")
    root = insert(root, key)

print("\nFinal tree:")
print_tree(root)
print(f"\nTotal nodes: {count_nodes(root)}")
print(f"Balances: {get_all_bfs(root)}")

# Test sequence 7: 20, 40, 10, 30, 50, 25, 35, 45, 55, 60
print("\n" + "=" * 60)
print("Sequence: 20, 40, 10, 30, 50, 25, 35, 45, 55, 60")
print("=" * 60)
seq7 = [20, 40, 10, 30, 50, 25, 35, 45, 55, 60]
root = None
for key in seq7:
    print(f"\nInsert {key}:")
    root = insert(root, key)

print("\nFinal tree:")
print_tree(root)
print(f"\nTotal nodes: {count_nodes(root)}")
print(f"Balances: {get_all_bfs(root)}")

# Test sequence 8: 50, 25, 75, 12, 37, 62, 87, 6, 19, 31
print("\n" + "=" * 60)
print("Sequence: 50, 25, 75, 12, 37, 62, 87, 6, 19, 31")
print("=" * 60)
seq8 = [50, 25, 75, 12, 37, 62, 87, 6, 19, 31]
root = None
for key in seq8:
    print(f"\nInsert {key}:")
    root = insert(root, key)

print("\nFinal tree:")
print_tree(root)
print(f"\nTotal nodes: {count_nodes(root)}")
print(f"Balances: {get_all_bfs(root)}")
