# ===== 1. 经验种子（你只填这里，大胆给值）=====
CANDIDATES = [
    {"P1": [30, 15, 25, 40, 35, 10, 20, 5, 38, 22]},
    {"P1": [40, 20, 30, 10, 25, 5, 35, 15, 28, 32, 12]},
    {"P1": [50, 30, 40, 20, 35, 10, 45, 25, 15, 38, 42, 28]},
]

# ===== 2. AVL 树模拟 =====
class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def height(n):
    return n.height if n else 0

def bf(n):
    return height(n.left) - height(n.right) if n else 0

def update_h(n):
    n.height = 1 + max(height(n.left), height(n.right))

rotations = []  # list of (type, new_root_key)

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
        new_root = root.left
        root.left = new_root.right
        new_root.right = root
        update_h(root)
        update_h(new_root)
        rotations.append(("LL", new_root.key))
        return new_root
    # LR
    if b > 1 and bf(root.left) < 0:
        B = root.left
        C = B.right
        B.right = C.left
        root.left = C.right
        C.left = B
        C.right = root
        update_h(B)
        update_h(root)
        update_h(C)
        rotations.append(("LR", C.key))
        return C
    # RR
    if b < -1 and bf(root.right) <= 0:
        new_root = root.right
        root.right = new_root.left
        new_root.left = root
        update_h(root)
        update_h(new_root)
        rotations.append(("RR", new_root.key))
        return new_root
    # RL
    if b < -1 and bf(root.right) > 0:
        B = root.right
        C = B.left
        B.left = C.right
        root.right = C.left
        C.right = B
        C.left = root
        update_h(B)
        update_h(root)
        update_h(C)
        rotations.append(("RL", C.key))
        return C
    return root

def build_avl(seq):
    global rotations
    rotations = []
    root = None
    for k in seq:
        root = insert(root, k)
    return root

def find_node(root, key):
    if root is None:
        return None
    if root.key == key:
        return root
    if key < root.key:
        return find_node(root.left, key)
    return find_node(root.right, key)

def nodes_with_both_children(root, acc):
    if root is None:
        return
    if root.left and root.right:
        acc.append(root.key)
    nodes_with_both_children(root.left, acc)
    nodes_with_both_children(root.right, acc)

# ===== 2b. 派生参数（代码计算，不要手写）=====
def derive(seeds):
    params = dict(seeds)
    root = build_avl(params["P1"])
    # P3: 选最终树中有两个孩子的内部结点（取第一个）
    candidates_p3 = []
    nodes_with_both_children(root, candidates_p3)
    if candidates_p3:
        params["P3"] = candidates_p3[0]
    else:
        params["P3"] = params["P1"][0]
    return params

# ===== 3. 约束检查（代码验证）=====
def validate(params):
    checks = []
    seq = params["P1"]
    # unique
    checks.append(("unique", len(set(seq)) == len(seq)))
    # length_range_7_to_12
    checks.append(("length_7_to_12", 7 <= len(seq) <= 12))
    # all positive
    checks.append(("all_positive", all(x > 0 for x in seq)))
    # rebuild to get rotations
    root = build_avl(seq)
    rot_types = set(r[0] for r in rotations)
    # triggers_at_least_one_LR_rotation
    checks.append(("has_LR", "LR" in rot_types))
    # triggers_multiple_rotation_types (>= 2 distinct types)
    checks.append(("multiple_rotation_types", len(rot_types) >= 2))
    # total rotations >= 3 (enough for hard difficulty)
    checks.append(("enough_rotations", len(rotations) >= 3))
    # P3 in P1
    checks.append(("P3_in_P1", params["P3"] in seq))
    # P3 has both children in final tree
    node = find_node(root, params["P3"])
    has_both = node is not None and node.left is not None and node.right is not None
    checks.append(("P3_has_both_children", has_both))
    return checks

# ===== 4. 自动选择通过验证的候选 =====
result = None
for seeds in CANDIDATES:
    params = derive(seeds)
    checks = validate(params)
    all_ok = all(ok for _, ok in checks)
    print(f"Candidate P1={seeds['P1']}")
    for name, ok in checks:
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    if all_ok:
        result = params
        break

if result is None:
    result = derive(CANDIDATES[0])
    print("WARNING: no candidate passed all checks, using first")

# ===== 5. 输出 =====
print("\n=== FINAL PARAMS ===")
print(f"P1={result['P1']}")
print(f"P3={result['P3']}")
# extra info for reference
root = build_avl(result["P1"])
print(f"root_key={root.key}")
print(f"tree_height={root.height}")
print(f"rotations={rotations}")
