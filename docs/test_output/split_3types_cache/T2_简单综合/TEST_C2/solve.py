# 从前序+中序还原二叉树，求叶子节点数和深度

preorder = ['A', 'B', 'D', 'F', 'E', 'C', 'G', 'H']
inorder = ['F', 'D', 'B', 'E', 'A', 'C', 'G', 'H']

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

# 括号表示法
def parenthesize(node):
    if node is None:
        return ""
    s = node.val
    if node.left or node.right:
        s += "("
        s += parenthesize(node.left)
        if node.right:
            s += "," + parenthesize(node.right)
        s += ")"
    return s

# 叶子节点数
def leaf_count(node):
    if node is None:
        return 0
    if node.left is None and node.right is None:
        return 1
    return leaf_count(node.left) + leaf_count(node.right)

# 深度
def depth(node):
    if node is None:
        return 0
    return 1 + max(depth(node.left), depth(node.right))

# 打印结构（节点 -> 左孩子, 右孩子）
def print_structure(node, indent=0):
    if node is None:
        return
    left_val = node.left.val if node.left else "None"
    right_val = node.right.val if node.right else "None"
    print("  " * indent + f"{node.val} -> left: {left_val}, right: {right_val}")
    print_structure(node.left, indent + 1)
    print_structure(node.right, indent + 1)

print("树的结构（括号表示法）:", parenthesize(root))
print()
print("各节点的孩子关系:")
print_structure(root)
print()
leaves = leaf_count(root)
d = depth(root)
print(f"叶子节点个数: {leaves}")
print(f"树的深度: {d}")
