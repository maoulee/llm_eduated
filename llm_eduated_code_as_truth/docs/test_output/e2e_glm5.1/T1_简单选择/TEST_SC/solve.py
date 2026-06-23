from collections import deque

# Preorder and inorder sequences
preorder = [5, 3, 2, 4, 7, 6]
inorder  = [2, 3, 7, 4, 5, 6]

class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

def build_tree(preorder, inorder):
    """Reconstruct binary tree from preorder and inorder."""
    if not preorder or not inorder:
        return None
    root_val = preorder[0]
    root = Node(root_val)
    idx = inorder.index(root_val)
    root.left  = build_tree(preorder[1:1+idx], inorder[:idx])
    root.right = build_tree(preorder[1+idx:], inorder[idx+1:])
    return root

def compute_wpl(root):
    """WPL = sum(weight * depth) for all nodes, depth of root = 0."""
    wpl = 0
    queue = deque()
    queue.append((root, 0))
    while queue:
        node, depth = queue.popleft()
        wpl += node.val * depth
        if node.left:
            queue.append((node.left, depth + 1))
        if node.right:
            queue.append((node.right, depth + 1))
    return wpl

root = build_tree(preorder, inorder)

# Print tree structure for verification
def print_tree(node, depth=0):
    if node is None:
        return
    print("  " * depth + f"val={node.val}, depth={depth}, w*d={node.val*depth}")
    print_tree(node.left, depth + 1)
    print_tree(node.right, depth + 1)

print("=== Tree structure ===")
print_tree(root)

wpl = compute_wpl(root)
print(f"\n正确: {wpl}")
