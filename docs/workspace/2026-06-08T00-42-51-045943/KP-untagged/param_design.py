import itertools

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def height(n):
    return n.height if n else 0

def balance_factor(n):
    if not n:
        return 0
    return height(n.left) - height(n.right)

def update_height(n):
    n.height = 1 + max(height(n.left), height(n.right))

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

rotation_log = []

def insert(node, key):
    global rotation_log
    if not node:
        return Node(key)
    if key < node.key:
        node.left = insert(node.left, key)
    elif key > node.key:
        node.right = insert(node.right, key)
    else:
        return node
    update_height(node)
    bf = balance_factor(node)
    if bf > 1 and balance_factor(node.left) >= 0:
        rotation_log.append((key, node.key, "LL"))
        return right_rotate(node)
    if bf > 1 and balance_factor(node.left) < 0:
        rotation_log.append((key, node.key, "LR"))
        node.left = left_rotate(node.left)
        return right_rotate(node)
    if bf < -1 and balance_factor(node.right) <= 0:
        rotation_log.append((key, node.key, "RR"))
        return left_rotate(node)
    if bf < -1 and balance_factor(node.right) > 0:
        rotation_log.append((key, node.key, "RL"))
        node.right = right_rotate(node.right)
        return left_rotate(node)
    return node

def get_info(root):
    rk = root.key
    lc = root.left.key if root.left else None
    rc = root.right.key if root.right else None
    return rk, lc, rc

def tree_to_str(node, level=0):
    """Print tree horizontally for visualization"""
    if not node:
        return ""
    result = ""
    result += tree_to_str(node.right, level + 1)
    result += "  " * level + f"[{node.key}](h={node.height})\n"
    result += tree_to_str(node.left, level + 1)
    return result

# ===== Find sequences where LL comes FIRST, then a double rotation =====
# Also look for: RR first, then double
# Want "clean" sequences with nice spacing

print("=== LL first, then LR or RL ===")
count = 0
for perm in itertools.permutations(range(1, 11), 7):
    rotation_log = []
    root = None
    for k in perm:
        root = insert(root, k)
    if len(rotation_log) != 2:
        continue
    types = [r[2] for r in rotation_log]
    if types[0] != "LL":
        continue
    if types[1] not in ("LR", "RL"):
        continue
    # Non-monotonic
    is_inc = all(perm[i] < perm[i+1] for i in range(len(perm)-1))
    is_dec = all(perm[i] > perm[i+1] for i in range(len(perm)-1))
    if is_inc or is_dec:
        continue
    rk, lc, rc = get_info(root)
    print(f"  Seq: {perm}, Rotations: {rotation_log}, Root: {rk}, L: {lc}, R: {rc}")
    count += 1
    if count >= 5:
        break

print()
print("=== RR first, then LR or RL ===")
count = 0
for perm in itertools.permutations(range(1, 11), 7):
    rotation_log = []
    root = None
    for k in perm:
        root = insert(root, k)
    if len(rotation_log) != 2:
        continue
    types = [r[2] for r in rotation_log]
    if types[0] != "RR":
        continue
    if types[1] not in ("LR", "RL"):
        continue
    is_inc = all(perm[i] < perm[i+1] for i in range(len(perm)-1))
    is_dec = all(perm[i] > perm[i+1] for i in range(len(perm)-1))
    if is_inc or is_dec:
        continue
    rk, lc, rc = get_info(root)
    print(f"  Seq: {perm}, Rotations: {rotation_log}, Root: {rk}, L: {lc}, R: {rc}")
    count += 1
    if count >= 5:
        break

# ===== Let's also look for LL + LR (both on left side) for clean pedagogy =====
print()
print("=== LL + LR (both left-side rotations) ===")
count = 0
for perm in itertools.permutations(range(1, 11), 7):
    rotation_log = []
    root = None
    for k in perm:
        root = insert(root, k)
    if len(rotation_log) != 2:
        continue
    types = set(r[2] for r in rotation_log)
    if types != {"LL", "LR"}:
        continue
    is_inc = all(perm[i] < perm[i+1] for i in range(len(perm)-1))
    is_dec = all(perm[i] > perm[i+1] for i in range(len(perm)-1))
    if is_inc or is_dec:
        continue
    rk, lc, rc = get_info(root)
    print(f"  Seq: {perm}, Rotations: {rotation_log}, Root: {rk}, L: {lc}, R: {rc}")
    count += 1
    if count >= 8:
        break

# ===== Verify chosen sequence in detail =====
print()
print("=" * 60)
# Let's try (10, 5, 2, 1, 7, 3, 8) - descending then ascending, should trigger LL then LR
test_seqs = [
    (10, 5, 2, 1, 7, 3, 8),
    (8, 5, 2, 1, 6, 3, 7),
    (9, 5, 2, 1, 7, 3, 8),
    (7, 4, 2, 1, 6, 3, 5),
    (6, 3, 1, 2, 5, 4, 7),
]
for seq in test_seqs:
    rotation_log = []
    root = None
    for k in seq:
        root = insert(root, k)
    rk, lc, rc = get_info(root)
    print(f"Seq: {seq}")
    print(f"  Rotations: {rotation_log}")
    print(f"  Root: {rk}, L: {lc}, R: {rc}")
    print(f"  Tree:\n{tree_to_str(root)}")
    print()
