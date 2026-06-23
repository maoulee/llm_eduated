# Reconstruct binary tree from preorder and inorder traversals
preorder = ['A', 'B', 'D', 'E', 'C', 'F', 'G']
inorder = ['D', 'B', 'E', 'A', 'C', 'F', 'G']

def build_tree(pre, ino):
    if not pre or not ino:
        return None
    root_val = pre[0]
    idx = ino.index(root_val)
    left_ino = ino[:idx]
    right_ino = ino[idx+1:]
    left_pre = pre[1:1+len(left_ino)]
    right_pre = pre[1+len(left_ino):]
    return {
        'val': root_val,
        'left': build_tree(left_pre, left_ino),
        'right': build_tree(right_pre, right_ino)
    }

tree = build_tree(preorder, inorder)

# Print tree structure
def print_tree(node, indent=0, prefix=""):
    if node:
        print(" " * indent + prefix + node['val'])
        if node['left'] or node['right']:
            print_tree(node['left'], indent+2, "L->")
            print_tree(node['right'], indent+2, "R->")

print("=== Tree Structure ===")
print_tree(tree)

# Print parent-child relationships
def print_relations(node, parent=None):
    if node:
        if parent:
            if node == parent['left']:
                print(f"{parent['val']} 的左孩子: {node['val']}")
            else:
                print(f"{parent['val']} 的右孩子: {node['val']}")
        print_relations(node['left'], node)
        print_relations(node['right'], node)

print("\n=== 节点关系 ===")
print_relations(tree)

# Calculate depth
def depth(node):
    if not node:
        return 0
    return 1 + max(depth(node['left']), depth(node['right']))

d = depth(tree)
print(f"\n深度: {d}")

# Check complete binary tree
def is_complete(node):
    from collections import deque
    if not node:
        return True
    queue = deque([node])
    found_none = False
    while queue:
        curr = queue.popleft()
        if curr is None:
            found_none = True
        else:
            if found_none:
                return False
            queue.append(curr['left'])
            queue.append(curr['right'])
    return True

complete = is_complete(tree)
print(f"完全二叉树: {complete}")

# Explain why not complete
print("\n=== 层序遍历检查 ===")
from collections import deque
queue = deque([tree])
level = 1
while queue:
    level_nodes = []
    for _ in range(len(queue)):
        curr = queue.popleft()
        if curr:
            level_nodes.append(curr['val'])
            queue.append(curr['left'])
            queue.append(curr['right'])
        else:
            level_nodes.append("None")
    print(f"第{level}层: {level_nodes}")
    level += 1
