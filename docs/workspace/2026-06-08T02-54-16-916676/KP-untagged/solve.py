# solve.py — 独立求解验证
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
    if b > 1 and bf(root.left) >= 0:
        nr = root.left
        root.left = nr.right
        nr.right = root
        update_h(root); update_h(nr)
        rotations.append(("LL", nr.key))
        return nr
    if b > 1 and bf(root.left) < 0:
        B = root.left; C = B.right
        B.right = C.left; root.left = C.right
        C.left = B; C.right = root
        update_h(B); update_h(root); update_h(C)
        rotations.append(("LR", C.key))
        return C
    if b < -1 and bf(root.right) <= 0:
        nr = root.right
        root.right = nr.left
        nr.left = root
        update_h(root); update_h(nr)
        rotations.append(("RR", nr.key))
        return nr
    if b < -1 and bf(root.right) > 0:
        B = root.right; C = B.left
        B.left = C.right; root.right = C.left
        C.right = B; C.left = root
        update_h(B); update_h(root); update_h(C)
        rotations.append(("RL", C.key))
        return C
    return root

seq = [40, 20, 30, 10, 25, 5, 35, 15, 28, 32, 12]
root = None
for k in seq:
    root = insert(root, k)

# (1) root key & height
print(f"ANSWER (1): root={root.key}, height={root.height}")

# (2) rotations
print(f"ANSWER (2): count={len(rotations)}, rotations={rotations}")

# (3) P3=20 children
n = root  # 20 is root
lc = n.left.key if n.left else "空"
rc = n.right.key if n.right else "空"
print(f"ANSWER (3): left={lc}, right={rc}")
