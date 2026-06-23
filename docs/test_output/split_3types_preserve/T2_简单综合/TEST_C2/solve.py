from collections import deque

preorder = ['a', 'b', 'd', 'e', 'g', 'c', 'f']
inorder = ['d', 'b', 'e', 'g', 'a', 'c', 'f']

# Reconstruct binary tree
class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

def build(pre, ino):
    if not pre:
        return None
    root = Node(pre[0])
    idx = ino.index(pre[0])
    left_ino = ino[:idx]
    right_ino = ino[idx+1:]
    left_pre = pre[1:1+len(left_ino)]
    right_pre = pre[1+len(left_ino):]
    root.left = build(left_pre, left_ino)
    root.right = build(right_pre, right_ino)
    return root

root = build(preorder, inorder)

# Print tree structure
def print_tree(node, prefix="", is_left=True):
    if node is None:
        return
    print(prefix + ("├── " if is_left else "└── ") + node.val)
    if node.left or node.right:
        new_prefix = prefix + ("│   " if is_left else "    ")
        print_tree(node.left, new_prefix, True)
        print_tree(node.right, new_prefix, False)

print("=== 二叉树结构 ===")
print("根: " + root.val)
print_tree(root.left, "", True)
print_tree(root.right, "", False)

# Level-order traversal
def level_order(root):
    if not root:
        return []
    result = []
    q = deque([root])
    while q:
        node = q.popleft()
        result.append(node.val)
        if node.left:
            q.append(node.left)
        if node.right:
            q.append(node.right)
    return result

lo = level_order(root)
print("\n=== 层序遍历 ===")
print("层序遍历: " + ", ".join(lo))

# Height, leaf count, degree-2 count
def get_stats(node):
    if node is None:
        return 0, 0, 0  # height, leaves, deg2
    if node.left is None and node.right is None:
        return 1, 1, 0
    lh, ll, ld2 = get_stats(node.left) if node.left else (0, 0, 0)
    rh, rl, rd2 = get_stats(node.right) if node.right else (0, 0, 0)
    h = max(lh, rh) + 1
    leaves = ll + rl
    deg2 = ld2 + rd2 + (1 if node.left and node.right else 0)
    return h, leaves, deg2

h, leaves, deg2 = get_stats(root)
print("\n=== 统计信息 ===")
print("高度: " + str(h))
print("叶子节点个数: " + str(leaves))
print("度为2的节点个数: " + str(deg2))
