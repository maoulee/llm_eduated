"""
Q41 平衡二叉树（AVL）的构造与旋转过程分析
依次插入 {30, 15, 45, 8, 22, 40, 50, 18, 25, 10}，模拟标准 AVL 插入算法。
"""


class AVLNode:
    __slots__ = ('key', 'left', 'right', 'height')

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
    """BF = 左子树高度 − 右子树高度"""
    if node is None:
        return 0
    return get_height(node.left) - get_height(node.right)


def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))


def rotate_right(z):
    """LL 型：右单旋"""
    y = z.left
    T3 = y.right
    y.right = z
    z.left = T3
    update_height(z)
    update_height(y)
    return y


def rotate_left(z):
    """RR 型：左单旋"""
    y = z.right
    T2 = y.left
    y.left = z
    z.right = T2
    update_height(z)
    update_height(y)
    return y


# 记录每次旋转信息
rotation_log = []


def insert(node, key):
    if node is None:
        return AVLNode(key)

    if key < node.key:
        node.left = insert(node.left, key)
    elif key > node.key:
        node.right = insert(node.right, key)
    else:
        return node  # 不允许重复

    update_height(node)
    bf = get_bf(node)

    rotation_type = None

    # LL
    if bf > 1 and key < node.left.key:
        rotation_type = 'LL'
        node = rotate_right(node)
    # RR
    elif bf < -1 and key > node.right.key:
        rotation_type = 'RR'
        node = rotate_left(node)
    # LR
    elif bf > 1 and key > node.left.key:
        rotation_type = 'LR'
        node.left = rotate_left(node.left)
        node = rotate_right(node)
    # RL
    elif bf < -1 and key < node.right.key:
        rotation_type = 'RL'
        node.right = rotate_right(node.right)
        node = rotate_left(node)

    if rotation_type is not None:
        rotation_log.append((key, rotation_type))

    return node


def level_order(root):
    """层序遍历"""
    if root is None:
        return []
    result = []
    queue = [root]
    while queue:
        node = queue.pop(0)
        result.append(node.key)
        if node.left:
            queue.append(node.left)
        if node.right:
            queue.append(node.right)
    return result


def find_node(root, key):
    if root is None:
        return None
    if root.key == key:
        return root
    if key < root.key:
        return find_node(root.left, key)
    return find_node(root.right, key)


def is_balanced(node):
    """检查整棵树是否每个结点 |BF| <= 1"""
    if node is None:
        return True
    if abs(get_bf(node)) > 1:
        return False
    return is_balanced(node.left) and is_balanced(node.right)


def solve(keys):
    global rotation_log
    rotation_log = []
    root = None
    for k in keys:
        root = insert(root, k)
    return root


# ========== 主逻辑 ==========

KEYS = [30, 15, 45, 8, 22, 40, 50, 18, 25, 10]

root = solve(KEYS)

# ---- 第（1）题：旋转记录 ----
print("=== REASONING ===")
print("第（1）题：旋转记录")
for k, rt in rotation_log:
    print(f"  插入 {k} → {rt} 旋转")
print(f"  共触发 {len(rotation_log)} 次旋转")
rotation_types = set(rt for _, rt in rotation_log)
print(f"  旋转类型集合: {rotation_types}")

# ---- 第（2）题：层序遍历 ----
lo = level_order(root)
print("\n第（2）题：层序遍历序列")
print(f"  {lo}")

# ---- 第（3）题：平衡因子 ----
node_8 = find_node(root, 8)
node_22 = find_node(root, 22)
bf_8 = get_bf(node_8)
bf_22 = get_bf(node_22)
print("\n第（3）题：平衡因子")
print(f"  BF(8)  = {bf_8}")
print(f"  BF(22) = {bf_22}")

# ========== ANSWER ==========
print("\n=== ANSWER ===")
print("第（1）题：")
for k, rt in rotation_log:
    print(f"  插入 {k} → {rt} 旋转")
print(f"第（2）题：层序遍历 = {lo}")
print(f"第（3）题：BF(8) = {bf_8}，BF(22) = {bf_22}")

# ========== 通过条件 assert ==========

# 条件1: 至少触发 3 次旋转，且至少涵盖 2 种不同类型
assert len(rotation_log) >= 3, \
    f"旋转次数 {len(rotation_log)} < 3，不满足覆盖度要求"
assert len(rotation_types) >= 2, \
    f"旋转类型仅 {rotation_types}，不足 2 种，不满足覆盖度要求"

# 条件2: 不同旋转类型的处理逻辑互不相同（代码层面已保证四种旋转路径不同）
# 这里验证旋转类型记录确实存在且类型合法
valid_types = {'LL', 'RR', 'LR', 'RL'}
for _, rt in rotation_log:
    assert rt in valid_types, f"未知旋转类型: {rt}"

# 条件3: 最终树每个结点 |BF| <= 1
assert is_balanced(root), "最终树不满足 AVL 平衡性"

# 条件4: 层序序列长度 = 10，且 30 不在第 1 位
assert len(lo) == 10, f"层序序列长度 {len(lo)} != 10"
assert lo[0] != 30, "30 仍在根位置，旋转未改变树根"

# 条件5: BF(8) != BF(22)
assert bf_8 != bf_22, \
    f"BF(8)={bf_8} == BF(22)={bf_22}，无区分度"

print("\n=== 所有 assert 通过 ===")
