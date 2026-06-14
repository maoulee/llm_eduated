# solve.py - 二叉树带权路径长度(WPL) 正确算法 DAG
# 只算正确答案，不编码错误算法/干扰值

# ===== 初始参数（2^n 友好值预设）=====
# 树结构：节点编号 → (左子, 右子, 权值)
# 权值为 None 表示该节点不标注权值（如根①、内部②③）
# 权值非 None 的节点中，有子节点的是内部节点（如⑤），无子节点的是叶子

tree = {
    1: (2, 3, None),      # ① 根，内部，无权值标注
    2: (4, 5, None),      # ② 内部
    3: (6, 7, None),      # ③ 内部
    4: (None, None, 4),   # ④ 叶子
    5: (8, 9, 8),         # ⑤ 内部（有权值标注但非叶子——干扰锚点）
    6: (None, None, 2),   # ⑥ 叶子
    7: (None, None, 6),   # ⑦ 叶子
    8: (None, None, 5),   # ⑧ 叶子
    9: (None, None, 3),   # ⑨ 叶子
}

root = 1

# ===== DAG Step 1: BFS 计算各节点路径长度（边数，根为 0）=====
from collections import deque

depths = {}
queue = deque([(root, 0)])
while queue:
    node, depth = queue.popleft()
    depths[node] = depth
    left, right, _ = tree[node]
    if left is not None:
        queue.append((left, depth + 1))
    if right is not None:
        queue.append((right, depth + 1))

# ===== DAG Step 2: 识别叶子节点（左右子均为 None）=====
leaves = sorted([n for n in tree if tree[n][0] is None and tree[n][1] is None])

# ===== DAG Step 3: 逐叶加权求和 → 正确 WPL =====
wpl = 0
details = []
for leaf in leaves:
    weight = tree[leaf][2]
    depth = depths[leaf]
    contrib = weight * depth
    wpl += contrib
    details.append((leaf, weight, depth, contrib))

# ===== 输出 =====
print("=== 节点信息 ===")
for n in sorted(tree):
    left, right, w = tree[n]
    is_leaf = (left is None and right is None)
    tag = "叶子" if is_leaf else "内部"
    wstr = f"权值={w}" if w is not None else "无权值标注"
    print(f"  节点{n}: {tag}, {wstr}, 路径长度(边数)={depths[n]}")

print(f"\n=== 叶子集合: {leaves} ===")
print(f"=== 有权值标注但非叶子的节点: {[n for n in tree if tree[n][2] is not None and (tree[n][0] is not None or tree[n][1] is not None)]} ===")

print(f"\n=== WPL 计算明细 ===")
for leaf, w, d, c in details:
    print(f"  节点{leaf}: 权值 {w} × 路径长度 {d} = {c}")
print(f"\n正确: WPL = {wpl}")

# ===== 验证断言 =====
assert 30 <= wpl <= 80, f"WPL={wpl} 不在 [30, 80]"
assert 4 <= len(leaves) <= 6, f"叶子数={len(leaves)} 不在 [4, 6]"
for leaf in leaves:
    w = tree[leaf][2]
    d = depths[leaf]
    assert 1 <= w <= 9, f"叶子{leaf} 权值={w} 不在 [1, 9]"
    assert 2 <= d <= 3, f"叶子{leaf} 路径长度={d} 不在 [2, 3]"
max_level = max(depths.values()) + 1  # 层数 = 最大边数 + 1
assert 3 <= max_level <= 4, f"树深度={max_level}层 不在 [3, 4]"
leaf_weights = [tree[l][2] for l in leaves]
assert len(leaf_weights) == len(set(leaf_weights)), f"叶子权值不唯一: {leaf_weights}"
print("\n=== 所有验证断言通过 ===")
