"""
Q41 平衡二叉树（AVL）的插入与旋转调整
建模：AVL树插入 + 平衡检查 + 旋转调整
"""

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None

def height(node):
    if node is None:
        return 0
    return 1 + max(height(node.left), height(node.right))

def bf(node):
    """BF = 左子树高度 - 右子树高度"""
    if node is None:
        return 0
    return height(node.left) - height(node.right)

def find_node(root, key):
    """BST查找，返回路径上的节点列表（从根到插入点的父节点）"""
    path = []
    cur = root
    while cur is not None:
        path.append(cur)
        if key < cur.key:
            cur = cur.left
        elif key > cur.key:
            cur = cur.right
        else:
            return path  # 已存在
    return path

def bst_insert(root, key):
    """普通BST插入，返回根和插入路径（从根到新节点）"""
    path = []
    cur = root
    while True:
        path.append(cur)
        if key < cur.key:
            if cur.left is None:
                cur.left = Node(key)
                path.append(cur.left)
                break
            cur = cur.left
        elif key > cur.key:
            if cur.right is None:
                cur.right = Node(key)
                path.append(cur.right)
                break
            cur = cur.right
        else:
            break  # 已存在，不插入
    return path

def find_min_unbalanced(path):
    """从插入路径向上找第一个BF绝对值为2的节点（最小不平衡子树的根）"""
    for node in reversed(path[:-1]):  # 排除新插入的叶子节点本身
        if abs(bf(node)) > 1:
            return node
    return None

def right_rotate(z):
    """右单旋（LL型）：z的左孩子上提"""
    y = z.left
    T2 = y.right
    y.right = z
    z.left = T2
    return y

def left_rotate(z):
    """左单旋（RR型）：z的右孩子上提"""
    y = z.right
    T2 = y.left
    y.left = z
    z.right = T2
    return y

def get_rotation_type(node):
    """判断旋转类型：LL/RR/LR/RL"""
    if bf(node) > 1:  # 左子树高
        if bf(node.left) >= 0:
            return "LL"
        else:
            return "LR"
    elif bf(node) < -1:  # 右子树高
        if bf(node.right) <= 0:
            return "RR"
        else:
            return "RL"
    return "无"

def replace_in_parent(root, target, new_subtree):
    """在树中找到target节点并用new_subtree替换它，返回新的root"""
    if root is target:
        return new_subtree
    # 遍历找到target的父节点
    def _find_parent(node, tgt):
        if node is None:
            return None
        if node.left is tgt or node.right is tgt:
            return node
        if node.key > tgt.key:
            return _find_parent(node.left, tgt)
        else:
            return _find_parent(node.right, tgt)
    parent = _find_parent(root, target)
    if parent.left is target:
        parent.left = new_subtree
    else:
        parent.right = new_subtree
    return root

def rebalance_subtree(root, unbalanced_node):
    """对最小不平衡子树执行旋转，返回新的根"""
    rot_type = get_rotation_type(unbalanced_node)
    if rot_type == "LL":
        new_subtree_root = right_rotate(unbalanced_node)
    elif rot_type == "RR":
        new_subtree_root = left_rotate(unbalanced_node)
    elif rot_type == "LR":
        unbalanced_node.left = left_rotate(unbalanced_node.left)
        new_subtree_root = right_rotate(unbalanced_node)
    elif rot_type == "RL":
        unbalanced_node.right = right_rotate(unbalanced_node.right)
        new_subtree_root = left_rotate(unbalanced_node)
    else:
        return root, "无", None

    root = replace_in_parent(root, unbalanced_node, new_subtree_root)
    return root, rot_type, new_subtree_root

def is_balanced(root):
    """检查整棵树是否平衡"""
    if root is None:
        return True
    if abs(bf(root)) > 1:
        return False
    return is_balanced(root.left) and is_balanced(root.right)

def print_tree(node, prefix="", is_left=True, is_root=True):
    """打印树结构"""
    if is_root and node is not None:
        print_tree_str = []
        _collect_tree(node, "", True, True, print_tree_str)
        return "\n".join(print_tree_str)
    return ""

def _collect_tree(node, prefix, is_left, is_root, lines):
    if node is None:
        return
    if is_root:
        lines.append(f"{node.key}")
        if node.left or node.right:
            new_prefix = "  "
            if node.left:
                lines.append(f"{new_prefix}├─L: {node.left.key}")
                _collect_tree(node.left, new_prefix + "│  ", True, False, lines)
            if node.right:
                lines.append(f"{new_prefix}├─R: {node.right.key}")
                _collect_tree(node.right, new_prefix + "│  ", False, False, lines)
    else:
        pass  # 简化版本

def tree_to_detail(node, indent=0):
    """递归打印树的详细信息"""
    result = []
    def _dfs(n, d):
        if n is None:
            return
        left_k = n.left.key if n.left else "None"
        right_k = n.right.key if n.right else "None"
        result.append(f"{'  '*d}[{n.key}] L={left_k} R={right_k} h={height(n)} BF={bf(n)}")
        _dfs(n.left, d+1)
        _dfs(n.right, d+1)
    _dfs(node, indent)
    return "\n".join(result)

def inorder(node):
    """中序遍历"""
    if node is None:
        return []
    return inorder(node.left) + [node.key] + inorder(node.right)

def all_bf(node, result=None):
    """收集所有节点的BF"""
    if result is None:
        result = {}
    if node is None:
        return result
    result[node.key] = bf(node)
    all_bf(node.left, result)
    all_bf(node.right, result)
    return result

# ============================================================
# 构建初始AVL树
# ============================================================
def build_initial_tree():
    """
            50
           /  \
         30    66
        /  \     \
      18   40    80
    """
    root = Node(50)
    root.left = Node(30)
    root.right = Node(66)
    root.left.left = Node(18)
    root.left.right = Node(40)
    root.right.right = Node(80)
    return root

# ============================================================
# 第（1）题：计算初始树各节点BF，验证平衡性
# ============================================================
def solve_part1(root):
    print("=" * 60)
    print("PARAMS: 初始AVL树 T")
    print("  50 / \\ 30 66 / \\ \\ 18 40 80")
    print("=" * 60)

    print("\nREASONING: 第（1）题 - 计算各节点BF")
    bfs = all_bf(root)
    for k in sorted(bfs.keys()):
        print(f"  节点 {k}: BF = {bfs[k]}")

    balanced = is_balanced(root)
    print(f"\n  是否平衡: {'是' if balanced else '否'}")
    print(f"  所有节点 |BF| ≤ 1: {'是' if balanced else '否'}")

    print("\nANSWER:")
    print(f"  节点18: BF=0  节点40: BF=0  节点80: BF=0")
    print(f"  节点30: BF={bfs[30]}  节点66: BF={bfs[66]}  节点50: BF={bfs[50]}")
    print(f"  当前T满足平衡条件：{'是' if balanced else '否'}")
    return balanced

# ============================================================
# 第（2）题：依次插入25, 10, 55，每次插入后检查并调整
# ============================================================
def solve_part2(root):
    print("\n" + "=" * 60)
    print("REASONING: 第（2）题 - 依次插入 25, 10, 55")
    print("=" * 60)

    insert_keys = [25, 10, 55]
    table_rows = []

    for key in insert_keys:
        print(f"\n--- 插入 {key} ---")

        # BST插入
        path = bst_insert(root, key)
        inserted_node = path[-1]
        print(f"  插入路径: {' -> '.join(str(n.key) for n in path)}")

        # 计算插入后各节点BF，判断是否失衡
        bfs = all_bf(root)
        unbalanced = [k for k, v in bfs.items() if abs(v) > 1]
        is_imbalanced = len(unbalanced) > 0

        if is_imbalanced:
            # 找最小不平衡子树的根
            min_unbal = find_min_unbalanced(path)
            print(f"  失衡节点: {unbalanced}")
            print(f"  最小不平衡子树的根: {min_unbal.key}")

            # 判断旋转类型
            rot_type = get_rotation_type(min_unbal)
            print(f"  旋转类型: {rot_type}")

            # 执行旋转
            root, rot_type, new_root = rebalance_subtree(root, min_unbal)
            print(f"  调整后子树新根: {new_root.key}")

            # 验证调整后平衡
            bfs_after = all_bf(root)
            unbal_after = [k for k, v in bfs_after.items() if abs(v) > 1]
            assert len(unbal_after) == 0, f"调整后仍不平衡: {unbal_after}"

            table_rows.append((key, "是", str(min_unbal.key), rot_type, str(new_root.key)))
        else:
            print(f"  未失衡")
            table_rows.append((key, "否", "—", "无", "—"))

        # 打印当前树状态
        print(f"  当前树详细结构:")
        detail = tree_to_detail(root)
        for line in detail.split("\n"):
            print(f"    {line}")

    # 打印表格
    print("\n" + "-" * 40)
    print("ANSWER: 第（2）题表格")
    print("-" * 40)
    print(f"| 插入关键字 | 是否失衡 | 最小不平衡子树根 | 旋转类型 | 调整后新根 |")
    for row in table_rows:
        print(f"|    {row[0]:>3}    |   {row[1]}   |       {row[2]:>5}       |   {row[3]:>2}    |    {row[4]:>3}    |")

    return root

# ============================================================
# 第（3）题：最终AVL树形态
# ============================================================
def solve_part3(root):
    print("\n" + "=" * 60)
    print("REASONING: 第（3）题 - 最终AVL树形态")
    print("=" * 60)
    print("\nANSWER: 最终树结构（关键字 [左孩子, 右孩子] 高度 BF）:")
    detail = tree_to_detail(root)
    print(detail)

    print("\n  树形可视化:")
    _print_visual(root, 0, "Root")

def _print_visual(node, depth, label):
    if node is None:
        return
    print(f"{'    '*depth}{label}: {node.key}")
    left_label = f"L({node.key})"
    right_label = f"R({node.key})"
    _print_visual(node.left, depth+1, left_label)
    _print_visual(node.right, depth+1, right_label)

# ============================================================
# 第（4）题：中序遍历
# ============================================================
def solve_part4(root):
    print("\n" + "=" * 60)
    print("REASONING: 第（4）题 - 中序遍历")
    print("=" * 60)

    seq = inorder(root)
    seq_str = " -> ".join(str(x) for x in seq)
    print(f"\nANSWER: 中序遍历序列 = {seq_str}")

    # 验证BST性质（中序遍历应递增）
    is_sorted = all(seq[i] < seq[i+1] for i in range(len(seq)-1))
    print(f"  BST性质验证（中序递增）: {'通过' if is_sorted else '失败'}")
    assert is_sorted, "中序遍历不是递增序列，BST性质被破坏！"

    # 验证最终树平衡
    assert is_balanced(root), "最终树不平衡！"
    print(f"  最终树平衡验证: 通过")

# ============================================================
# 主流程
# ============================================================
if __name__ == "__main__":
    root = build_initial_tree()

    # 验证初始树是BST
    init_seq = inorder(root)
    assert all(init_seq[i] < init_seq[i+1] for i in range(len(init_seq)-1)), "初始树不是BST！"
    assert is_balanced(root), "初始树不平衡！"

    # 第（1）题
    solve_part1(root)

    # 第（2）题
    root = solve_part2(root)

    # 第（3）题
    solve_part3(root)

    # 第（4）题
    solve_part4(root)

    print("\n" + "=" * 60)
    print("所有验证通过（初始BST+平衡、每次调整后平衡、最终BST性质、最终平衡）")
    print("=" * 60)
