# ===== 1. 经验种子（你只填这里，大胆给值）=====
CANDIDATES = [
    {"P1": [30, 15, 50, 10, 20, 40, 60, 5, 12, 8]},
    {"P1": [16, 3, 7, 11, 9, 26, 18, 14, 15, 20]},
    {"P1": [40, 20, 60, 10, 30, 50, 70, 5, 15, 25, 8]},
]

# ===== 2. AVL树模拟器 =====
class AVLNode:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    return node.height if node else 0

def get_balance(node):
    if not node:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))

def rotate_right(y):
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    update_height(y)
    update_height(x)
    return x

def rotate_left(x):
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    update_height(x)
    update_height(y)
    return y

def insert(root, val, events):
    """插入并记录旋转事件。events 列表收集 (关键字, 旋转类型) 元组。"""
    # 标准BST插入
    if not root:
        return AVLNode(val)
    if val < root.val:
        root.left = insert(root.left, val, events)
    elif val > root.val:
        root.right = insert(root.right, val, events)
    else:
        return root  # 重复值不插入

    update_height(root)
    balance = get_balance(root)

    # 检测失衡并执行旋转
    if balance > 1:
        # 左子树高
        child = root.left
        child_balance = get_balance(child)
        if child_balance >= 0:
            # LL型
            events.append((val, "LL"))
        else:
            # LR型
            events.append((val, "LR"))
    elif balance < -1:
        # 右子树高
        child = root.right
        child_balance = get_balance(child)
        if child_balance <= 0:
            # RR型
            events.append((val, "RR"))
        else:
            # RL型
            events.append((val, "RL"))

    # 执行旋转调整
    if balance > 1:
        child = root.left
        child_balance = get_balance(child)
        if child_balance >= 0:
            return rotate_right(root)
        else:
            root.left = rotate_left(root.left)
            return rotate_right(root)
    elif balance < -1:
        child = root.right
        child_balance = get_balance(child)
        if child_balance <= 0:
            return rotate_left(root)
        else:
            root.right = rotate_right(root.right)
            return rotate_left(root)

    return root

def level_order(root):
    """层序遍历"""
    if not root:
        return []
    from collections import deque
    result = []
    queue = deque([root])
    while queue:
        node = queue.popleft()
        result.append(node.val)
        if node.left:
            queue.append(node.left)
        if node.right:
            queue.append(node.right)
    return result

def simulate_avl(seq):
    """完整模拟AVL构建过程"""
    root = None
    events = []
    for val in seq:
        root = insert(root, val, events)
    lo = level_order(root)
    return events, lo

# ===== 2. 派生参数 =====
def derive(seeds):
    params = dict(seeds)
    seq = params["P1"]
    events, level_order_seq = simulate_avl(seq)
    params["P2"] = len(events)
    params["_events"] = events
    params["_level_order"] = level_order_seq
    params["_rotation_types"] = set(e[1] for e in events)
    return params

# ===== 3. 约束检查 =====
def validate(params):
    checks = []
    seq = params["P1"]

    # unique
    checks.append(("unique", len(seq) == len(set(seq))))

    # length 8-12
    checks.append(("length_8_to_12", 8 <= len(seq) <= 12))

    # at least 3 rotation types
    n_types = len(params["_rotation_types"])
    checks.append(("at_least_3_rotation_types", n_types >= 3))

    return checks

# ===== 4. 自动选择通过验证的候选 =====
result = None
for seeds in CANDIDATES:
    params = derive(seeds)
    checks = validate(params)
    ok = all(ok for _, ok in checks)
    if ok:
        result = params
        break

if result is None:
    result = derive(CANDIDATES[0])
    print("WARNING: no candidate passed all checks, using first")

# ===== 5. 输出 =====
for k, v in result.items():
    if not k.startswith("_"):
        print(f"{k}={v}")
# 额外信息用于替换和调试
print(f"events={result['_events']}")
print(f"level_order={result['_level_order']}")
print(f"rotation_types={result['_rotation_types']}")
