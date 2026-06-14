# solve.py - Q41 平衡二叉树（AVL）插入与旋转模拟
# 正确算法 DAG：初始参数（插入序列）→ 逐步插入 → 高度/BF计算 → 失衡检测 → 旋转 → 最终树
# 平衡因子定义：BF = 左子树高度 - 右子树高度（空子树高度=0，叶节点高度=1）
# 只算正确答案，不编码错误算法/干扰值

INSERT_SEQUENCE = [16, 8, 24, 4, 12, 10, 14, 13]


class AVLNode:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None
        self.height = 1


def get_height(node):
    return node.height if node else 0


def get_bf(node):
    if not node:
        return 0
    return get_height(node.left) - get_height(node.right)


def update_height(node):
    if node:
        node.height = 1 + max(get_height(node.left), get_height(node.right))


def right_rotate(y):
    """右单旋（用于 LL 型调整）"""
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    update_height(y)
    update_height(x)
    return x


def left_rotate(x):
    """左单旋（用于 RR 型调整）"""
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    update_height(x)
    update_height(y)
    return y


def insert(node, val, rotation_log):
    """AVL 插入：BST 插入 + 回溯时检测失衡并旋转"""
    if not node:
        return AVLNode(val)

    if val < node.val:
        node.left = insert(node.left, val, rotation_log)
    elif val > node.val:
        node.right = insert(node.right, val, rotation_log)
    else:
        return node  # 重复关键码（本题不存在）

    update_height(node)
    bf = get_bf(node)

    if bf > 1 or bf < -1:
        child = node.left if bf > 1 else node.right
        child_bf = get_bf(child)

        if bf > 1:
            if child_bf >= 0:
                rtype = "LL（右单旋）"
            else:
                rtype = "LR（先左后右双旋）"
        else:
            if child_bf <= 0:
                rtype = "RR（左单旋）"
            else:
                rtype = "RL（先右后左双旋）"

        rotation_log.append({
            'node': node.val,
            'bf': bf,
            'child': child.val,
            'child_bf': child_bf,
            'type': rtype
        })

        if bf > 1:
            if child_bf >= 0:  # LL
                return right_rotate(node)
            else:  # LR
                node.left = left_rotate(node.left)
                return right_rotate(node)
        else:
            if child_bf <= 0:  # RR
                return left_rotate(node)
            else:  # RL
                node.right = right_rotate(node.right)
                return left_rotate(node)

    return node


def print_tree(node, indent=0, label=""):
    """缩进式打印树结构，标注平衡因子"""
    if node:
        bf = get_bf(node)
        print(f"{'    ' * indent}{label}{node.val} (BF={bf})")
        if node.left or node.right:
            if node.left:
                print_tree(node.left, indent + 1, "L--- ")
            if node.right:
                print_tree(node.right, indent + 1, "R--- ")


def get_all_bf(node, result=None):
    """获取所有节点的平衡因子（按中序排序）"""
    if result is None:
        result = {}
    if node:
        get_all_bf(node.left, result)
        result[node.val] = get_bf(node)
        get_all_bf(node.right, result)
    return result


def find_node(root, val):
    """在树中查找指定关键码的节点"""
    if not root:
        return None
    if val == root.val:
        return root
    elif val < root.val:
        return find_node(root.left, val)
    else:
        return find_node(root.right, val)


def clone_tree(root):
    """深拷贝树（用于保存中间状态）"""
    if not root:
        return None
    new = AVLNode(root.val)
    new.height = root.height
    new.left = clone_tree(root.left)
    new.right = clone_tree(root.right)
    return new


# ===================== 主模拟 =====================

print("=" * 60)
print("AVL 树插入模拟（正确算法）")
print(f"插入序列: {INSERT_SEQUENCE}")
print(f"平衡因子定义: BF = 左子树高度 - 右子树高度")
print("=" * 60)

# 完整逐步模拟（输出每一步）
root = None
step_trees = {}  # 保存每步结束后的树（深拷贝）
step_rotations = {}  # 保存每步的旋转记录

for i, key in enumerate(INSERT_SEQUENCE):
    rotation_log = []
    root = insert(root, key, rotation_log)
    step = i + 1
    step_trees[step] = clone_tree(root)
    step_rotations[step] = rotation_log

    print(f"\n--- 第 {step} 步: 插入关键码 {key} ---")
    if rotation_log:
        for r in rotation_log:
            print(f"  ⚡ 触发旋转!")
            print(f"  失衡节点: {r['node']}, BF = {r['bf']}")
            side = '左' if r['bf'] > 1 else '右'
            print(f"  {side}子节点: {r['child']}, BF = {r['child_bf']}")
            print(f"  旋转类型: {r['type']}")
    print(f"  当前树:")
    print_tree(root)

# ===================== 各子问题答案 =====================

print("\n" + "=" * 60)
print("各子问题答案")
print("=" * 60)

# ---- 子问题 (1): 插入前 5 个关键码后的树结构和平衡因子 ----
print("\n### (1) 插入前 5 个关键码后的树结构和平衡因子")
print(f"插入序列（前5个）: {INSERT_SEQUENCE[:5]}")
print("正确: 树结构:")
print_tree(step_trees[5])
bf5 = get_all_bf(step_trees[5])
print("正确: 各节点平衡因子:")
for val in sorted(bf5.keys()):
    print(f"  节点 {val}: BF = {bf5[val]}")

# ---- 子问题 (2): 插入第 6 个关键码时的旋转分析 ----
print(f"\n### (2) 插入第 6 个关键码 {INSERT_SEQUENCE[5]} 时的旋转分析")
r6 = step_rotations[6]
if r6:
    r = r6[0]
    print(f"正确: 最小不平衡子树的根节点: {r['node']}")
    print(f"正确: 该节点的平衡因子: {r['bf']}")
    side = '左' if r['bf'] > 1 else '右'
    print(f"正确: {side}子节点: {r['child']} (BF={r['child_bf']})")
    print(f"正确: 旋转类型: {r['type']}")
else:
    print("（本步未触发旋转）")
print("正确: 旋转后的树结构:")
print_tree(step_trees[6])
bf6 = get_all_bf(step_trees[6])
print("正确: 旋转后各节点平衡因子:")
for val in sorted(bf6.keys()):
    print(f"  节点 {val}: BF = {bf6[val]}")

# ---- 子问题 (3): 最终 AVL 树 + 查询节点属性 ----
print(f"\n### (3) 全部插入完成后的最终 AVL 树")
print("正确: 最终树结构:")
print_tree(step_trees[8])
bf8 = get_all_bf(step_trees[8])
print("正确: 最终各节点平衡因子:")
for val in sorted(bf8.keys()):
    print(f"  节点 {val}: BF = {bf8[val]}")

query_val = 16
query_node = find_node(step_trees[8], query_val)
if query_node:
    print(f"\n正确: 节点 {query_val} 的属性:")
    print(f"正确: 平衡因子 = {get_bf(query_node)}")
    left_child = query_node.left.val if query_node.left else "无"
    right_child = query_node.right.val if query_node.right else "无"
    print(f"正确: 左子节点 = {left_child}")
    print(f"正确: 右子节点 = {right_child}")

# ---- 合法性验证 ----
print("\n--- 验证 ---")
is_valid = all(abs(bf) <= 1 for bf in bf8.values())
print(f"所有节点 |BF| <= 1: {'是' if is_valid else '否'}")
print(f"最终树是否合法 AVL 树: {'是' if is_valid else '否'}")
print(f"插入过程中触发旋转的步骤: {[s for s, r in step_rotations.items() if r]}")
