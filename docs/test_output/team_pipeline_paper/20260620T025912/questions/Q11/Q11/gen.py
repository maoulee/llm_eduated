# gen.py — 二叉树遍历序列还原

# PARAMS
inorder = ['G', 'D', 'B', 'E', 'A', 'C', 'H', 'F']
postorder = ['G', 'D', 'E', 'B', 'H', 'F', 'C', 'A']

# 树节点定义
class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

# 从中序和后序还原二叉树
def build_tree(inorder, postorder):
    if not inorder:
        return None
    root_val = postorder[-1]
    root = Node(root_val)
    idx = inorder.index(root_val)
    left_in = inorder[:idx]
    right_in = inorder[idx+1:]
    left_post = postorder[:len(left_in)]
    right_post = postorder[len(left_in):-1]
    root.left = build_tree(left_in, left_post)
    root.right = build_tree(right_in, right_post)
    return root

# 中序遍历
def inorder_traverse(root):
    if root is None:
        return []
    return inorder_traverse(root.left) + [root.val] + inorder_traverse(root.right)

# 后序遍历
def postorder_traverse(root):
    if root is None:
        return []
    return postorder_traverse(root.left) + postorder_traverse(root.right) + [root.val]

# 先序遍历
def preorder_traverse(root):
    if root is None:
        return []
    return [root.val] + preorder_traverse(root.left) + preorder_traverse(root.right)

# 统计递归步数
step_count = 0
def build_tree_with_steps(inorder, postorder):
    global step_count
    if not inorder:
        return None
    step_count += 1  # 确定根结点
    root_val = postorder[-1]
    root = Node(root_val)
    idx = inorder.index(root_val)
    left_in = inorder[:idx]
    right_in = inorder[idx+1:]
    left_post = postorder[:len(left_in)]
    right_post = postorder[len(left_in):-1]
    if left_in:
        step_count += 1  # 划分左子树
    if right_in:
        step_count += 1  # 划分右子树
    root.left = build_tree_with_steps(left_in, left_post)
    root.right = build_tree_with_steps(right_in, right_post)
    return root

# 检查是否存在度为2的结点
def has_degree_2(root):
    if root is None:
        return False
    if root.left is not None and root.right is not None:
        return True
    return has_degree_2(root.left) or has_degree_2(root.right)

# 统计子树结点数
def count_nodes(root):
    if root is None:
        return 0
    return 1 + count_nodes(root.left) + count_nodes(root.right)

# 主逻辑
tree = build_tree(inorder, postorder)

# REASONING
print("REASONING:")
print("后序遍历最后一个元素是根结点: A")
print("在中序中找到 A 的位置，左边 [G,D,B,E] 是左子树，右边 [C,H,F] 是右子树")
print("递归还原左子树: 后序 [G,D,E,B]，中序 [G,D,B,E]，根为 B")
print("递归还原右子树: 后序 [H,F,C]，中序 [C,H,F]，根为 C")
print("继续递归直到所有子树还原完成")
print("先序遍历: 根左右顺序输出")

# 验证条件
# 1. 序列一致性
assert inorder_traverse(tree) == inorder, "中序遍历不一致"
assert postorder_traverse(tree) == postorder, "后序遍历不一致"

# 2. 树结构非退化（存在度为2的结点）
assert has_degree_2(tree), "树退化：不存在度为2的结点"

# 3. 左右子树均非空且规模>=2
assert count_nodes(tree.left) >= 2, "左子树规模 < 2"
assert count_nodes(tree.right) >= 2, "右子树规模 < 2"

# 4. 先序序列唯一确定，长度8，首元素为A
preorder = preorder_traverse(tree)
assert len(preorder) == 8, f"先序序列长度不为8: {len(preorder)}"
assert preorder[0] == 'A', f"先序首元素不为A: {preorder[0]}"

# 5. 推演步数 >= 6
global step_count
step_count = 0
build_tree_with_steps(inorder, postorder)
assert step_count >= 6, f"推演步数不足6: {step_count}"

# ANSWER
print(f"ANSWER: 先序遍历序列: {', '.join(preorder)}")
