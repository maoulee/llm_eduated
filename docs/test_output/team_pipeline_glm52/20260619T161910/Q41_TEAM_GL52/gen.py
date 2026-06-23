import math

class AVLNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    if node is None:
        return 0
    return node.height

def get_bf(node):
    if node is None:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(y):
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    update_height(y)
    update_height(x)
    return x

def left_rotate(x):
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    update_height(x)
    update_height(y)
    return y

rotation_events = []

def insert(root, key):
    if root is None:
        return AVLNode(key)
    if key < root.key:
        root.left = insert(root.left, key)
    elif key > root.key:
        root.right = insert(root.right, key)
    else:
        return root

    update_height(root)
    bf = get_bf(root)

    if bf > 1 or bf < -1:
        if bf > 1:
            child_bf = get_bf(root.left)
            child_key = root.left.key
            rot_type = "LL" if child_bf >= 0 else "LR"
        else:
            child_bf = get_bf(root.right)
            child_key = root.right.key
            rot_type = "RR" if child_bf <= 0 else "RL"

        rotation_events.append({
            'key_inserted': key,
            'unbalanced_root': root.key,
            'bf_root': bf,
            'child_key': child_key,
            'child_bf': child_bf,
            'rot_type': rot_type,
        })

    if bf > 1:
        if get_bf(root.left) >= 0:
            root = right_rotate(root)
        else:
            root.left = left_rotate(root.left)
            root = right_rotate(root)
    elif bf < -1:
        if get_bf(root.right) <= 0:
            root = left_rotate(root)
        else:
            root.right = right_rotate(root.right)
            root = left_rotate(root)

    return root

def clone_tree(node):
    """Deep clone for snapshot."""
    if node is None:
        return None
    n = AVLNode(node.key)
    n.height = node.height
    n.left = clone_tree(node.left)
    n.right = clone_tree(node.right)
    return n

def print_tree(node, prefix="", is_left=True, is_root=True):
    if is_root and node:
        bf = get_bf(node)
        print(f"{prefix}{node.key}(BF={bf})")
        if node.left or node.right:
            if node.left:
                print_tree(node.left, prefix, True, False)
            elif node.right:
                print(f"{prefix}├── (空)")
            if node.right:
                print_tree(node.right, prefix, False, False)
            elif node.left:
                print(f"{prefix}└── (空)")
    elif node:
        bf = get_bf(node)
        connector = "├── " if is_left else "└── "
        print(f"{prefix}{connector}{node.key}(BF={bf})")
        new_prefix = prefix + ("│   " if is_left else "    ")
        if node.left:
            print_tree(node.left, new_prefix, True, False)
        if node.right:
            print_tree(node.right, new_prefix, False, False)

def print_all_bf(node):
    """Print all nodes with their BF values, indented by depth."""
    def helper(n, depth):
        if n is None:
            return
        bf = get_bf(n)
        print(f"  {'  ' * depth}节点 {n.key}: BF = {bf}")
        helper(n.left, depth + 1)
        helper(n.right, depth + 1)
    helper(node, 0)

def tree_to_inorder(node):
    """In-order traversal."""
    if node is None:
        return []
    return tree_to_inorder(node.left) + [node.key] + tree_to_inorder(node.right)

# ============================================================
# Chosen sequence: S = [30, 20, 10, 15, 25, 5, 40, 50, 45]
# Constraints verified: LL + RL, n=9, gap=6
# ============================================================

S = [30, 20, 10, 15, 25, 5, 40, 50, 45]
n = len(S)

print(f"序列 S = {S}")
print(f"n = {n}")
print()

# Run insertion with snapshots
rotation_events = []
root = None
snapshots = []

for i, k in enumerate(S):
    events_before = len(rotation_events)
    root = insert(root, k)
    new_events = rotation_events[events_before:]
    snapshots.append((i + 1, k, clone_tree(root), new_events))

# Print step-by-step
print("=" * 60)
print("逐步插入过程")
print("=" * 60)

for step, key, tree, new_rots in snapshots:
    print(f"\n【第 {step} 步】插入关键字 {key}")
    if new_rots:
        ev = new_rots[0]
        print(f"  ★ 发生失衡！")
        print(f"    最小不平衡子树的根节点：{ev['unbalanced_root']}（BF = {ev['bf_root']}）")
        print(f"    相关子节点：{ev['child_key']}（BF = {ev['child_bf']}）")
        print(f"    旋转类型：{ev['rot_type']}")
    print(f"  当前树结构（含BF值）：")
    print_all_bf(tree)

# Rotation events summary
print("\n" + "=" * 60)
print("失衡事件汇总")
print("=" * 60)

for i, ev in enumerate(rotation_events):
    print(f"\n第 {i+1} 次失衡：")
    print(f"  触发关键字：{ev['key_inserted']}")
    print(f"  最小不平衡子树根节点：{ev['unbalanced_root']}")
    print(f"  根节点 BF = {ev['bf_root']}")
    print(f"  子节点：{ev['child_key']}，BF = {ev['child_bf']}")
    print(f"  旋转类型：{ev['rot_type']}")

# Tree at each imbalance point (BEFORE and AFTER rotation)
print("\n" + "=" * 60)
print("各失衡点的树结构（旋转前 vs 旋转后）")
print("=" * 60)

# Re-run with detailed tracking
rotation_events = []
root = None

for i, k in enumerate(S):
    # Before insert: save tree state
    events_before = len(rotation_events)
    root = insert(root, k)
    new_rots = rotation_events[events_before:]

    if new_rots:
        ev = new_rots[0]
        print(f"\n--- 第 {events_before + 1} 次失衡（插入 {k} 后）---")
        print(f"\n旋转后树结构：")
        print_tree(root)
        print(f"\n旋转后各节点 BF：")
        print_all_bf(root)

# Final tree
print("\n" + "=" * 60)
print("最终 AVL 树")
print("=" * 60)
rotation_events = []
root_final = None
for k in S:
    root_final = insert(root_final, k)
print_tree(root_final)
print(f"\n中序遍历：{tree_to_inorder(root_final)}")
print(f"\n最终各节点 BF：")
print_all_bf(root_final)

# Constraint verification
print("\n" + "=" * 60)
print("约束验证")
print("=" * 60)
rot_types = [e['rot_type'] for e in rotation_events]
print(f"  旋转类型序列：{rot_types}")
print(f"  不同旋转类型数：{len(set(rot_types))}")
print(f"  包含双旋：{any(t in ('LR','RL') for t in rot_types)}")
print(f"  序列长度：{n}（要求7~9）")
first_idx = S.index(rotation_events[0]['key_inserted'])
second_idx = S.index(rotation_events[1]['key_inserted'])
print(f"  两次失衡间隔：{second_idx - first_idx} 步（要求≥3）")
print(f"  两次旋转类型不同：{rot_types[0]} ≠ {rot_types[1]} = {rot_types[0] != rot_types[1]}")
