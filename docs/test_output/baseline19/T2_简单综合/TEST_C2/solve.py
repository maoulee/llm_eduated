# 二叉树遍历问题求解
# 前序: A B D E C F G
# 中序: D B E A F C G

preorder = ['A', 'B', 'D', 'E', 'C', 'F', 'G']
inorder = ['D', 'B', 'E', 'A', 'F', 'C', 'G']

class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

def build_tree(pre, ino):
    if not pre or not ino:
        return None
    root_val = pre[0]
    root = Node(root_val)
    idx = ino.index(root_val)
    root.left = build_tree(pre[1:1+idx], ino[:idx])
    root.right = build_tree(pre[1+idx:], ino[idx+1:])
    return root

root = build_tree(preorder, inorder)

# 层序遍历
def level_order(node):
    if not node:
        return []
    result = []
    queue = [node]
    while queue:
        curr = queue.pop(0)
        result.append(curr.val)
        if curr.left:
            queue.append(curr.left)
        if curr.right:
            queue.append(curr.right)
    return result

# 树高
def height(node):
    if not node:
        return 0
    return 1 + max(height(node.left), height(node.right))

# 叶子节点数
def leaf_count(node):
    if not node:
        return 0
    if not node.left and not node.right:
        return 1
    return leaf_count(node.left) + leaf_count(node.right)

# 打印树结构（文字描述）
def describe_tree(node, level=0, prefix="Root"):
    if node:
        print(f"{'  ' * level}{prefix}: {node.val}")
        if node.left or node.right:
            if node.left:
                describe_tree(node.left, level+1, "Left")
            else:
                print(f"{'  ' * (level+1)}Left: None")
            if node.right:
                describe_tree(node.right, level+1, "Right")
            else:
                print(f"{'  ' * (level+1)}Right: None")

print("=== 二叉树结构 ===")
describe_tree(root)

lo = level_order(root)
h = height(root)
lc = leaf_count(root)

print(f"\n层序遍历: {' '.join(lo)}")
print(f"树高: {h}")
print(f"叶子节点数: {lc}")
print(f"叶子节点: {lo[-4:]}")  # 最后4个是叶子
