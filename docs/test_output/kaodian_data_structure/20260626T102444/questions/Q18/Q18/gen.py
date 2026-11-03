"""
gen.py: 求二叉树中所有叶子结点到根的路径

题干翻译：
- 二叉链表存储，data 域整型
- 递归遍历时路径数组按「根→叶」方向积累
- 叶子→根方向输出，需要逆序
- 叶子判定：左右孩子均为空
- 回溯：递归返回时必须弹出路径数组末尾元素

通过条件（question.md 声明的 4 条）→ assert：
1. 路径方向正确性：path[0]=叶子值, path[-1]=根值
2. 路径完整性：路径长度 == 该叶子到根的真实深度+1
3. 叶子覆盖完备性：路径条数 == 叶子总数
4. 回溯正确性：每条路径恰好是该叶子到根的真实祖先链
"""

# ---- 二叉树表示 ----
class Node:
    def __init__(self, data, left=None, right=None):
        self.data = data
        self.left = left
        self.right = right

def build_example_tree():
    """题干示例树:
              1
             / \
            2   3
           / \   \
          4   5   6
    叶子: 4,5,6
    """
    n4 = Node(4); n5 = Node(5); n6 = Node(6)
    n2 = Node(2, n4, n5)
    n3 = Node(3, None, n6)
    n1 = Node(1, n2, n3)
    return n1

def build_irregular_tree():
    """不规则树，考验回溯正确性（含只有左子树的分支、只有右子树的分支）:
                10
               /  \
              20   30
             /      \
            40      50
           /  \
          60  70
    叶子: 60,70,50
    """
    n60 = Node(60); n70 = Node(70); n50 = Node(50)
    n40 = Node(40, n60, n70)
    n20 = Node(20, n40, None)
    n30 = Node(30, None, n50)
    n10 = Node(10, n20, n30)
    return n10

# ---- 算法实现（递归回溯 + 路径逆序） ----
def collect_paths(root):
    """
    递归遍历，维护 path 数组（根→叶方向积累）。
    遇叶子时，将 path 逆序得到「叶子→根」方向，记录。
    递归返回时弹出 path 末尾（回溯）。
    """
    results = []
    path = []
    _dfs(root, path, results)
    return results

def _dfs(node, path, results):
    if node is None:
        return
    # 进入结点：加入路径（根→叶方向积累）
    path.append(node.data)

    # 叶子判定：左右均为空
    if node.left is None and node.right is None:
        # path 当前是 [根,...,叶子]，逆序得到 [叶子,...,根]
        leaf_to_root = list(reversed(path))
        results.append(leaf_to_root)
    else:
        _dfs(node.left, path, results)
        _dfs(node.right, path, results)

    # 回溯：弹出当前结点
    path.pop()

# ---- 辅助函数：独立计算期望值（不依赖 collect_paths） ----
def get_depths(root):
    """返回 {结点值: 深度}，根深度=0。用 BFS。"""
    depths = {}
    from collections import deque
    q = deque([(root, 0)])
    while q:
        node, d = q.popleft()
        depths[id(node)] = d
        if node.left:
            q.append((node.left, d + 1))
        if node.right:
            q.append((node.right, d + 1))
    return depths

def get_ancestor_chain(root, target_node):
    """独立算某叶子到根的真实祖先链（叶子→根方向）。用 parent map。"""
    parent_map = {}
    from collections import deque
    q = deque([root])
    parent_map[id(root)] = None
    while q:
        node = q.popleft()
        if node.left:
            parent_map[id(node.left)] = node
            q.append(node.left)
        if node.right:
            parent_map[id(node.right)] = node
            q.append(node.right)

    chain = []
    cur = target_node
    while cur is not None:
        chain.append(cur.data)
        cur = parent_map[id(cur)]
    # chain 已经是 [叶子, ..., 根]
    return chain

def get_all_leaves(root):
    """返回所有叶子结点列表。"""
    leaves = []
    from collections import deque
    q = deque([root])
    while q:
        node = q.popleft()
        if node.left is None and node.right is None:
            leaves.append(node)
        if node.left:
            q.append(node.left)
        if node.right:
            q.append(node.right)
    return leaves

# ---- 验证通过条件（4 条 assert，逐条翻译 question.md 声明） ----
def verify(root, tree_name):
    print(f"\n{'='*60}")
    print(f"验证树: {tree_name}")
    print(f"{'='*60}")

    paths = collect_paths(root)
    root_val = root.data
    leaves = get_all_leaves(root)
    depths = get_depths(root)

    # ---- PARAMS ----
    print(f"\n[PARAMS]")
    print(f"  根值 = {root_val}")
    print(f"  叶子数 = {len(leaves)} (叶子值: {[l.data for l in leaves]})")

    # ---- REASONING: 逐条路径详情 ----
    print(f"\n[REASONING] 路径详情:")
    leaf_set = {id(l): l for l in leaves}
    for i, path in enumerate(paths):
        print(f"  路径{i+1}: {' '.join(map(str, path))}")

    # ---- 条件1: 路径方向正确性 ----
    # path[0]=叶子值, path[-1]=根值
    for i, path in enumerate(paths):
        assert path[-1] == root_val, f"FAIL 条件1[方向]: 路径{i+1} 末尾={path[-1]} ≠ 根值={root_val}"
        # path[0] 必须是某个叶子的值
        leaf_vals = [l.data for l in leaves]
        assert path[0] in leaf_vals, f"FAIL 条件1[方向]: 路径{i+1} 开头={path[0]} 不在叶子值集合中"

    # ---- 条件2: 路径完整性 ----
    # 路径长度 == 该叶子到根的深度+1
    leaf_by_val = {}
    for l in leaves:
        leaf_by_val[id(l)] = l
    # 建 value->node 映射（值唯一时）
    val_to_node = {}
    for l in leaves:
        val_to_node.setdefault(l.data, []).append(l)

    # 找每条路径对应的叶子结点
    leaf_node_by_data = {}
    for l in leaves:
        leaf_node_by_data[l.data] = l  # 假设叶子值唯一

    for i, path in enumerate(paths):
        leaf_node = leaf_node_by_data.get(path[0])
        if leaf_node is not None:
            expected_len = depths[id(leaf_node)] + 1
            assert len(path) == expected_len, f"FAIL 条件2[完整性]: 路径{i+1} 长度={len(path)} ≠ 期望={expected_len} (深度={depths[id(leaf_node)]}+1)"

    # ---- 条件3: 叶子覆盖完备性 ----
    assert len(paths) == len(leaves), f"FAIL 条件3[覆盖]: 路径数={len(paths)} ≠ 叶子数={len(leaves)}"

    # ---- 条件4: 回溯正确性 ----
    # 每条路径恰好是该叶子到根的真实祖先链（用独立方法验证）
    for i, path in enumerate(paths):
        leaf_node = leaf_node_by_data.get(path[0])
        if leaf_node is not None:
            true_chain = get_ancestor_chain(root, leaf_node)
            assert path == true_chain, f"FAIL 条件4[回溯]: 路径{i+1} {path} ≠ 真实祖先链 {true_chain}"

    print(f"\n[ASSERT] 全部 4 条通过条件已验证通过:")
    print(f"  ✓ 条件1: 路径方向正确（叶子→根）")
    print(f"  ✓ 条件2: 路径完整（长度=深度+1）")
    print(f"  ✓ 条件3: 叶子覆盖完备（{len(paths)} 条路径 = {len(leaves)} 个叶子）")
    print(f"  ✓ 条件4: 回溯正确（每条路径=真实祖先链）")

    # ---- ANSWER ----
    print(f"\n[ANSWER] 所有叶子→根路径:")
    for path in paths:
        print("  " + " ".join(map(str, path)))

    return paths

# ---- 主函数 ----
if __name__ == "__main__":
    # 树1：题干示例树
    tree1 = build_example_tree()
    p1 = verify(tree1, "题干示例树 (叶子: 4,5,6)")

    # 树2：不规则树（考验回溯）
    tree2 = build_irregular_tree()
    p2 = verify(tree2, "不规则树 (叶子: 60,70,50)")

    # ---- 题干示例的明确期望 ----
    expected_paths = {(4, 2, 1), (5, 2, 1), (6, 3, 1)}
    actual_set = {tuple(p) for p in p1}
    assert actual_set == expected_paths, f"题干示例期望不符: {actual_set} ≠ {expected_paths}"
    print(f"\n✓ 题干示例树输出与题干给出的期望完全一致: {expected_paths}")

    print("\n" + "="*60)
    print("ALL ASSERTS PASSED")
    print("="*60)
