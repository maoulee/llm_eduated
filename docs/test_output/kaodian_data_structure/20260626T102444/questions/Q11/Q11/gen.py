"""
后序+中序遍历序列还原二叉树，写出先序序列。
题干规则翻译为代码：
- 后序序列最后一个元素 = 当前子树的根
- 在中序序列中定位根 → 左侧=左子树中序，右侧=右子树中序
- 后序序列按中序的左右子树大小切分 → 左子树后序，右子树后序
- 递归还原
"""

POST = ['A','C','B','E','H','I','G','F','D']
IN   = ['A','B','C','D','E','F','H','G','I']

class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

# 全局记录递归深度
max_depth = [0]

def build(post, ino, depth):
    """递归还原：后序+中序 -> 二叉树"""
    if len(post) == 0:
        return None
    max_depth[0] = max(max_depth[0], depth)
    root_val = post[-1]              # 后序最后一个 = 根
    idx = ino.index(root_val)        # 在中序中定位根
    left_in  = ino[:idx]
    right_in = ino[idx+1:]
    left_post  = post[:len(left_in)]
    right_post = post[len(left_in):-1]
    node = Node(root_val)
    node.left  = build(left_post,  left_in,  depth+1)
    node.right = build(right_post, right_in, depth+1)
    return node

def preorder(node, result):
    if node is None:
        return
    result.append(node.val)
    preorder(node.left, result)
    preorder(node.right, result)
    return result

def postorder(node, result):
    if node is None:
        return
    postorder(node.left, result)
    postorder(node.right, result)
    result.append(node.val)
    return result

def inorder(node, result):
    if node is None:
        return
    inorder(node.left, result)
    result.append(node.val)
    inorder(node.right, result)
    return result

def count_degree2(node):
    """统计同时有左右孩子的节点数（度2节点）"""
    if node is None:
        return 0
    c = 1 if (node.left is not None and node.right is not None) else 0
    return c + count_degree2(node.left) + count_degree2(node.right)

# ========== PARAMS ==========
print("=== PARAMS ===")
print(f"后序序列: {POST}")
print(f"中序序列: {IN}")

# ========== REASONING ==========
print("\n=== REASONING ===")

# 第一步：根节点
root_val = POST[-1]
print(f"根节点 = 后序最后一个 = {root_val}")
print(f"根在中序中的位置 = {IN.index(root_val)}（下标从0起）")

# 还原
tree = build(POST, IN, 1)

# 打印还原步骤（逐层递归拆分）
def trace(post, ino, depth, tag="根"):
    if len(post) == 0:
        return
    rv = post[-1]
    idx = ino.index(rv)
    li, ri = ino[:idx], ino[idx+1:]
    lp, rp = post[:len(li)], post[len(li):-1]
    indent = "  " * (depth-1)
    print(f"{indent}[第{depth}层] {tag}: 根={rv}, 中序={ino}, 左子中序={li}, 右子中序={ri}")
    trace(lp, li, depth+1, tag=f"{rv}的左子")
    trace(rp, ri, depth+1, tag=f"{rv}的右子")

trace(POST, IN, 1)

# 非叶子节点列表（左孩子/右孩子）
print("\n--- Q1: 非叶子节点的左右孩子 ---")
non_leaf = []

def collect_non_leaf(node):
    if node is None:
        return
    if node.left is not None or node.right is not None:
        l = node.left.val if node.left else "空"
        r = node.right.val if node.right else "空"
        non_leaf.append((node.val, l, r))
        print(f"  节点 {node.val}: 左孩子={l}, 右孩子={r}")
    collect_non_leaf(node.left)
    collect_non_leaf(node.right)

collect_non_leaf(tree)

# 先序遍历
print("\n--- Q2: 先序遍历序列 ---")
pre_result = preorder(tree, [])
print(f"先序序列: {pre_result}")
print(f"先序序列(逗号分隔): {', '.join(pre_result)}")

# ========== ANSWER ==========
print("\n=== ANSWER ===")
print(f"Q1 非叶子节点及左右孩子:")
for v, l, r in non_leaf:
    print(f"  {v}: 左={l}, 右={r}")
print(f"Q2 先序序列: {', '.join(pre_result)}")

# ========== 通过条件 ASSERT（翻译 question.md 声明的 4 条判据）==========

# 条件1: 序列一致性 —— 两个序列元素集合相同（A~I各一次），且能唯一还原
assert set(POST) == set(IN), "序列1: 元素集合不同"
assert len(set(POST)) == len(POST) == 9, "序列1: 后序有重复元素"
assert len(set(IN)) == len(IN) == 9, "序列1: 中序有重复元素"
# 一致性：还原树再导出后序/中序，与输入一致
assert postorder(tree, []) == POST, "序列1: 还原树导出的后序与输入不一致"
assert inorder(tree, []) == IN, "序列1: 还原树导出的中序与输入不一致"

# 条件2: 结构约束 —— 度2节点 >= 3
deg2 = count_degree2(tree)
assert deg2 >= 3, f"结构: 度2节点={deg2} < 3"
print(f"\n度2节点数 = {deg2} (>=3 ✓)")

# 条件3: 先序完整性 —— 9个节点各一次，首节点=后序末尾=根
assert len(pre_result) == 9, "先序: 不是9个节点"
assert len(set(pre_result)) == 9, "先序: 有重复节点"
assert pre_result[0] == POST[-1], "先序: 首节点不是根(后序末尾)"

# 条件4: 递归深度 >= 3 (树高 >= 3)
assert max_depth[0] >= 3, f"深度: 树高={max_depth[0]} < 3"
print(f"递归深度(树高) = {max_depth[0]} (>=3 ✓)")

print("\n全部通过条件 assert 通过 ✓")
