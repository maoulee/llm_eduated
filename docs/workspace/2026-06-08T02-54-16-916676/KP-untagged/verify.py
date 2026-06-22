# verify.py — 独立实现 AVL 树，逐插入追踪旋转，输出最终树形态
class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def h(n):
    return n.height if n else 0

def bf(n):
    return h(n.left) - h(n.right) if n else 0

def update_h(n):
    n.height = 1 + max(h(n.left), h(n.right))

rotations = []

def insert(root, key):
    global rotations
    if root is None:
        return Node(key)
    if key < root.key:
        root.left = insert(root.left, key)
    else:
        root.right = insert(root.right, key)
    update_h(root)
    b = bf(root)
    # LL
    if b > 1 and bf(root.left) >= 0:
        nr = root.left
        root.left = nr.right
        nr.right = root
        update_h(root); update_h(nr)
        rotations.append(("LL", nr.key))
        return nr
    # LR
    if b > 1 and bf(root.left) < 0:
        B = root.left
        C = B.right
        B.right = C.left
        root.left = C.right
        C.left = B
        C.right = root
        update_h(B); update_h(root); update_h(C)
        rotations.append(("LR", C.key))
        return C
    # RR
    if b < -1 and bf(root.right) <= 0:
        nr = root.right
        root.right = nr.left
        nr.left = root
        update_h(root); update_h(nr)
        rotations.append(("RR", nr.key))
        return nr
    # RL
    if b < -1 and bf(root.right) > 0:
        B = root.right
        C = B.left
        B.left = C.right
        root.right = C.left
        C.right = B
        C.left = root
        update_h(B); update_h(root); update_h(C)
        rotations.append(("RL", C.key))
        return C
    return root

def find_node(root, key):
    if root is None:
        return None
    if root.key == key:
        return root
    if key < root.key:
        return find_node(root.left, key)
    return find_node(root.right, key)

def print_tree(n, level=0, prefix="root"):
    if n is None:
        return
    print("  " * level + f"{prefix}: {n.key} (h={n.height}, bf={bf(n)})")
    print_tree(n.left, level + 1, "L")
    print_tree(n.right, level + 1, "R")

seq = [40, 20, 30, 10, 25, 5, 35, 15, 28, 32, 12]
root = None
for k in seq:
    root = insert(root, k)
    print(f"Inserted {k}, rotations so far: {rotations[-1] if rotations else 'none'}")

print("\n=== FINAL TREE ===")
print_tree(root)
print(f"\nRoot key: {root.key}")
print(f"Tree height: {root.height}")
print(f"\nRotations: {rotations}")
print(f"Rotation count: {len(rotations)}")

# Query P3 = 20
node20 = find_node(root, 20)
if node20:
    lc = node20.left.key if node20.left else "空"
    rc = node20.right.key if node20.right else "空"
    print(f"\nNode 20: left={lc}, right={rc}")
