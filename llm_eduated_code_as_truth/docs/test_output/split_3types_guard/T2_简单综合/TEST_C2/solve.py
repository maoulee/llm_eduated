# 二叉树重建与遍历

pre_order = ['A', 'B', 'D', 'E', 'C', 'F', 'G']
in_order = ['D', 'B', 'E', 'A', 'F', 'C', 'G']

class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

def build_tree(pre, inorder):
    if not pre or not inorder:
        return None
    root_val = pre[0]
    root = Node(root_val)
    idx = inorder.index(root_val)
    left_inorder = inorder[:idx]
    right_inorder = inorder[idx+1:]
    left_size = len(left_inorder)
    root.left = build_tree(pre[1:1+left_size], left_inorder)
    root.right = build_tree(pre[1+left_size:], right_inorder)
    return root

def post_order(root):
    if not root:
        return []
    return post_order(root.left) + post_order(root.right) + [root.val]

def depth(root):
    if not root:
        return 0
    return 1 + max(depth(root.left), depth(root.right))

def count_leaves(root):
    if not root:
        return 0
    if root.left is None and root.right is None:
        return 1
    return count_leaves(root.left) + count_leaves(root.right)

root = build_tree(pre_order, in_order)

post = post_order(root)
d = depth(root)
leaves = count_leaves(root)

print(f"后序遍历: {' '.join(post)}")
print(f"深度: {d}")
print(f"叶子节点个数: {leaves}")
