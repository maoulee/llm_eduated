"""
gen.py: 构造满足约束的二叉树 → 导出后序/中序/先序序列 → 验证全部约束
"""

# --- 二叉树节点 ---
class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

# --- 构造目标二叉树 ---
# 手工构造一棵 8 节点、非满、非完全、左右非对称、树高>=3 的二叉树
#
#         A
#        / \
#       B   C
#      /   / \
#     D   E   F
#    /       /
#   G       H
#
# 节点数=8, 树高=3 (A->B->D->G 边数=3)
# 非满: B 只有左子, C 有左右, D 只有左子, F 只有左子
# 非完全: 第3层 G 在最左, H 在 F 下(第4层从左数第1个位置但第3层不连续)
# 左右非对称: 左子树(B)4节点, 右子树(C)3节点

root = Node('A')
root.left = Node('B')
root.right = Node('C')
root.left.left = Node('D')
root.right.left = Node('E')
root.right.right = Node('F')
root.left.left.left = Node('G')
root.right.right.left = Node('H')

# --- 遍历函数 ---
def preorder(n, out):
    if n is None:
        return
    out.append(n.val)
    preorder(n.left, out)
    preorder(n.right, out)

def inorder(n, out):
    if n is None:
        return
    inorder(n.left, out)
    out.append(n.val)
    inorder(n.right, out)

def postorder(n, out):
    if n is None:
        return
    postorder(n.left, out)
    postorder(n.right, out)
    out.append(n.val)

pre_seq = []
in_seq = []
post_seq = []
preorder(root, pre_seq)
inorder(root, in_seq)
postorder(root, post_seq)

print("=== 序列 ===")
print(f"先序: {pre_seq}")
print(f"中序: {in_seq}")
print(f"后序: {post_seq}")

# --- 验证约束 ---
N = len(pre_seq)
print(f"\n=== 约束验证 ===")
print(f"节点数 N = {N}")
assert 7 <= N <= 9, f"N={N} 不在 7~9 范围"

# 序列一致性
assert set(post_seq) == set(in_seq), "后序与中序元素集合不同"
print(f"序列一致性: PASS (集合相同)")

# --- 树高 ---
def tree_height(n):
    if n is None:
        return -1
    return 1 + max(tree_height(n.left), tree_height(n.right))

h = tree_height(root)
print(f"树高(边数) = {h}")
assert h >= 3, f"树高={h} < 3"
print(f"树高>=3: PASS")

# --- 非满二叉树 ---
def is_full(n):
    if n is None:
        return True
    has_l = n.left is not None
    has_r = n.right is not None
    if has_l != has_r:
        return False
    return is_full(n.left) and is_full(n.right)

full = is_full(root)
print(f"非满二叉树: {'PASS' if not full else 'FAIL'}")
assert not full, "是满二叉树"

# --- 非完全二叉树 ---
# 用层序遍历检查: 完全二叉树层序中, 第一个非满节点之后不能有更多节点
def is_complete(n):
    if n is None:
        return True
    from collections import deque
    q = deque([n])
    seen_nonfull = False
    while q:
        node = q.popleft()
        has_l = node.left is not None
        has_r = node.right is not None
        if seen_nonfull:
            if has_l or has_r:
                return False
        if not has_l and has_r:
            return False
        if not (has_l and has_r):
            seen_nonfull = True
        if has_l:
            q.append(node.left)
        if has_r:
            q.append(node.right)
    return True

complete = is_complete(root)
print(f"非完全二叉树: {'PASS' if not complete else 'FAIL'}")
assert not complete, "是完全二叉树"

# --- 左右非对称 ---
def count_nodes(n):
    if n is None:
        return 0
    return 1 + count_nodes(n.left) + count_nodes(n.right)

left_count = count_nodes(root.left)
right_count = count_nodes(root.right)
print(f"左子树节点数={left_count}, 右子树节点数={right_count}")
assert left_count != right_count, "左右子树节点数相同"
print(f"左右非对称: PASS (节点数不同)")

# --- 递归还原步数 ---
# 从后序+中序还原，统计递归拆分次数
def restore_and_count(post, ino):
    """从后序+中序还原二叉树，返回(树, 递归拆分步数)"""
    steps = [0]
    def build(post_seq, in_seq):
        if not post_seq or not in_seq:
            return None
        steps[0] += 1
        root_val = post_seq[-1]
        idx = in_seq.index(root_val)
        node = Node(root_val)
        node.left = build(post_seq[:idx], in_seq[:idx])
        node.right = build(post_seq[idx:-1], in_seq[idx+1:])
        return node
    tree = build(list(post), list(ino))
    return tree, steps[0]

restored, step_count = restore_and_count(post_seq, in_seq)
print(f"\n递归还原步数 = {step_count}")
assert step_count >= 3, f"递归步数={step_count} < 3"
print(f"递归步数>=3: PASS")

# --- 验证还原后的树与原树遍历序列一致 ---
restored_pre = []
restored_in = []
restored_post = []
preorder(restored, restored_pre)
inorder(restored, restored_in)
postorder(restored, restored_post)

assert restored_pre == pre_seq, "还原树先序不一致"
assert restored_in == in_seq, "还原树中序不一致"
assert restored_post == post_seq, "还原树后序不一致"
print(f"还原一致性: PASS (还原后的树遍历序列与原树完全一致)")

# --- 求解过程输出 ---
print(f"\n=== 求解数据流 ===")
print(f"后序序列 Post = {post_seq}")
print(f"中序序列 In   = {in_seq}")
print(f"先序序列 Pre  = {pre_seq}")

# 详细还原步骤
print(f"\n=== 逐步还原过程 ===")
def restore_verbose(post, ino, depth=0):
    if not post or not ino:
        return None
    indent = "  " * depth
    root_val = post[-1]
    idx = ino.index(root_val)
    left_in = ino[:idx]
    right_in = ino[idx+1:]
    left_post = post[:idx]
    right_post = post[idx:-1]
    print(f"{indent}根节点 = {root_val} (后序末尾)")
    print(f"{indent}  中序: {ino} → 根 {root_val} 在位置 {idx}")
    print(f"{indent}  左子树中序: {left_in}, 右子树中序: {right_in}")
    print(f"{indent}  左子树后序: {left_post}, 右子树后序: {right_post}")
    node = Node(root_val)
    if left_in:
        print(f"{indent}  → 递归处理左子树:")
        node.left = restore_verbose(left_post, left_in, depth+1)
    if right_in:
        print(f"{indent}  → 递归处理右子树:")
        node.right = restore_verbose(right_post, right_in, depth+1)
    return node

restore_verbose(post_seq, in_seq)

print(f"\n=== 最终答案 ===")
print(f"先序遍历序列: {''.join(pre_seq)}")
print(f"  即: {' → '.join(pre_seq)}")
