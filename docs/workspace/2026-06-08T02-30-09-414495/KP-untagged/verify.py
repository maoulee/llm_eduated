from collections import deque

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    return node.height if node else 0

def get_bf(node):
    if not node: return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(y):
    x = y.left
    T = x.right
    x.right = y
    y.left = T
    update_height(y)
    update_height(x)
    return x

def left_rotate(x):
    y = x.right
    T = y.left
    y.left = x
    x.right = T
    update_height(x)
    update_height(y)
    return y

def insert(root, key, rotations, step):
    if root is None:
        return Node(key)
    if key < root.key:
        root.left = insert(root.left, key, rotations, step)
    else:
        root.right = insert(root.right, key, rotations, step)
    update_height(root)
    bf = get_bf(root)

    if bf > 1 and key < root.left.key:
        rotations.append((step, root.key, "LL"))
        new_root = right_rotate(root)
        print(f"  Insert {key}: LL at {root.key} -> new root {new_root.key}")
        return new_root
    if bf < -1 and key > root.right.key:
        rotations.append((step, root.key, "RR"))
        new_root = left_rotate(root)
        print(f"  Insert {key}: RR at {root.key} -> new root {new_root.key}")
        return new_root
    if bf > 1 and key > root.left.key:
        rotations.append((step, root.key, "LR"))
        root.left = left_rotate(root.left)
        new_root = right_rotate(root)
        print(f"  Insert {key}: LR at {root.key} -> new root {new_root.key}")
        return new_root
    if bf < -1 and key < root.right.key:
        rotations.append((step, root.key, "RL"))
        root.right = right_rotate(root.right)
        new_root = left_rotate(root)
        print(f"  Insert {key}: RL at {root.key} -> new root {new_root.key}")
        return new_root
    return root

def level_order(root):
    if not root: return []
    q = deque([root])
    res = []
    while q:
        n = q.popleft()
        res.append(n.key)
        if n.left: q.append(n.left)
        if n.right: q.append(n.right)
    return res

def count_bf_zero(root):
    if not root: return 0
    c = 1 if get_bf(root) == 0 else 0
    return c + count_bf_zero(root.left) + count_bf_zero(root.right)

def print_tree(root, prefix=""):
    """Pretty print tree structure"""
    if not root: return
    print(f"{prefix}[{root.key}] bf={get_bf(root)} h={root.height}")
    if root.left:
        print_tree(root.left, prefix + "  L-")
    if root.right:
        print_tree(root.right, prefix + "  R-")

# ===== Main =====
seq = [3, 2, 1, 4, 5, 6, 7, 16, 15, 14, 13, 12]
root = None
rotations = []

print("=== INSERTION TRACE ===")
for i, k in enumerate(seq):
    print(f"\n--- Inserting {k} (step {i+1}) ---")
    root = insert(root, k, rotations, i+1)

print("\n=== FINAL TREE ===")
print_tree(root)

print(f"\n=== ROTATIONS SUMMARY ===")
print(f"Total rotations: {len(rotations)}")
for r in rotations:
    print(f"  Step {r[0]}: root={r[1]}, type={r[2]}")

types = set(r[2] for r in rotations)
print(f"Rotation types: {types}")

print(f"\n=== FINAL ANSWERS ===")
lo = level_order(root)
print(f"Level order: {lo}")
print(f"Height: {get_height(root)}")
print(f"BF=0 count: {count_bf_zero(root)}")
