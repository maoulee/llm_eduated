# ===== 1. 经验种子（只填这里）=====
CANDIDATES = [
    {"P1": [3, 2, 1, 4, 5, 6, 7, 16, 15, 14, 13, 12]},
    {"P1": [10, 5, 15, 3, 7, 1, 12, 17, 13, 2, 8]},
    {"P1": [30, 20, 40, 10, 25, 5, 15, 23, 28, 35, 50]},
]

# ===== 2. 派生参数 =====
def derive(seeds):
    params = dict(seeds)
    params["P2"] = len(params["P1"])
    return params

# ===== 3. AVL 树模拟 + 约束检查 =====

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    if node is None:
        return 0
    return node.height

def get_bf(node):
    if node is None:
        return 0
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

def insert(root, key, rotations):
    """插入并记录所有旋转事件"""
    if root is None:
        return Node(key)
    if key < root.key:
        root.left = insert(root.left, key, rotations)
    else:
        root.right = insert(root.right, key, rotations)

    update_height(root)
    bf = get_bf(root)

    # LL
    if bf > 1 and key < root.left.key:
        rotations.append((root.key, "LL"))
        return right_rotate(root)
    # RR
    if bf < -1 and key > root.right.key:
        rotations.append((root.key, "RR"))
        return left_rotate(root)
    # LR
    if bf > 1 and key > root.left.key:
        rotations.append((root.key, "LR"))
        root.left = left_rotate(root.left)
        return right_rotate(root)
    # RL
    if bf < -1 and key < root.right.key:
        rotations.append((root.key, "RL"))
        root.right = right_rotate(root.right)
        return left_rotate(root)

    return root

def level_order(root):
    """层序遍历"""
    if root is None:
        return []
    from collections import deque
    q = deque([root])
    result = []
    while q:
        node = q.popleft()
        result.append(node.key)
        if node.left:
            q.append(node.left)
        if node.right:
            q.append(node.right)
    return result

def count_bf_zero(root):
    if root is None:
        return 0
    c = 1 if get_bf(root) == 0 else 0
    return c + count_bf_zero(root.left) + count_bf_zero(root.right)

def validate(params):
    checks = []
    seq = params["P1"]

    # unique
    checks.append(("unique", len(seq) == len(set(seq))))

    # length 8-12
    checks.append(("length_8_to_12", 8 <= len(seq) <= 12))

    # all positive
    checks.append(("all_positive", all(x > 0 for x in seq)))

    # AVL simulation
    root = None
    rotations = []
    for k in seq:
        root = insert(root, k, rotations)

    # at least 3 rotations
    checks.append(("at_least_3_rotations", len(rotations) >= 3))

    # at least 2 rotation types
    types = set(r[1] for r in rotations)
    checks.append(("at_least_2_rotation_types", len(types) >= 2))

    # extra info for verification
    lo = level_order(root)
    h = get_height(root)
    bf0 = count_bf_zero(root)
    params["_rotations"] = rotations
    params["_level_order"] = lo
    params["_height"] = h
    params["_bf_zero_count"] = bf0

    return checks

# ===== 4. 自动选择 =====
result = None
for seeds in CANDIDATES:
    params = derive(seeds)
    checks = validate(params)
    all_ok = all(ok for _, ok in checks)
    if all_ok:
        result = params
        break
    else:
        failed = [name for name, ok in checks if not ok]
        print(f"Candidate {seeds['P1'][:5]}... failed: {failed}")

if result is None:
    result = derive(CANDIDATES[0])
    print("WARNING: no candidate passed all checks, using first")

# ===== 5. 输出 =====
print(f"\n=== SELECTED SEQUENCE ===")
print(f"P1={result['P1']}")
print(f"P2={result['P2']}")
print(f"\n=== VERIFICATION INFO ===")
print(f"Rotations: {result['_rotations']}")
print(f"Rotation count: {len(result['_rotations'])}")
print(f"Rotation types: {set(r[1] for r in result['_rotations'])}")
print(f"Level order: {result['_level_order']}")
print(f"Height: {result['_height']}")
print(f"BF=0 count: {result['_bf_zero_count']}")
