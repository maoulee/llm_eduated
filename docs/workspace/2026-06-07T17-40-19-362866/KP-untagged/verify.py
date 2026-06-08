# ===== AVL 树插入模拟器 =====
# 校验题干插入序列是否自洽，并输出每次旋转的类型

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def h(node):
    return 0 if node is None else node.height

def bf(node):
    if node is None:
        return 0
    return h(node.left) - h(node.right)

def update_height(node):
    node.height = 1 + max(h(node.left), h(node.right))

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

def insert(node, key, rotations, step):
    if node is None:
        return Node(key)
    if key < node.key:
        node.left = insert(node.left, key, rotations, step)
    else:
        node.right = insert(node.right, key, rotations, step)
    update_height(node)
    balance = bf(node)

    # LL
    if balance > 1 and key < node.left.key:
        rotations.append((step, key, node.key, "LL"))
        return right_rotate(node)
    # RR
    if balance < -1 and key > node.right.key:
        rotations.append((step, key, node.key, "RR"))
        return left_rotate(node)
    # LR
    if balance > 1 and key > node.left.key:
        rotations.append((step, key, node.key, "LR"))
        node.left = left_rotate(node.left)
        return right_rotate(node)
    # RL
    if balance < -1 and key < node.right.key:
        rotations.append((step, key, node.key, "RL"))
        node.right = right_rotate(node.right)
        return left_rotate(node)
    return node

def print_tree(node, level=0, prefix="Root: "):
    if node is not None:
        print("  " * level + prefix + f"{node.key} (h={node.height}, BF={bf(node)})")
        if node.left:
            print_tree(node.left, level + 1, "L--- ")
        if node.right:
            print_tree(node.right, level + 1, "R--- ")

def inorder(node):
    if node:
        return inorder(node.left) + [node.key] + inorder(node.right)
    return []

keys = [40, 20, 50, 10, 30, 25, 5, 60, 45, 42, 1]
root = None
rotations = []

for i, k in enumerate(keys):
    root = insert(root, k, rotations, k)
    print(f"\n插入 {k} 后:")
    print_tree(root)
    print()

print("=" * 60)
print("旋转记录:")
for step, key, unbalanced_node, rtype in rotations:
    print(f"  插入 {key} → 节点 {unbalanced_node} 失衡 → {rtype} 旋转")

print(f"\n总旋转次数: {len(rotations)}")
print(f"旋转类型序列: {[r[3] for r in rotations]}")

# 校验：最终树应该是平衡的
def check_balance(node):
    if node is None:
        return True
    if abs(bf(node)) > 1:
        return False
    return check_balance(node.left) and check_balance(node.right)

assert check_balance(root), "最终树不平衡！"
print("最终树平衡性校验: 通过")

# 校验中序遍历有序
sorted_keys = inorder(root)
assert sorted_keys == sorted(keys), f"中序遍历错误: {sorted_keys}"
print("中序遍历有序性校验: 通过")

print(f"\n最终中序遍历: {sorted_keys}")
print(f"节点数: {len(sorted_keys)}")
print("\n参数校验通过")
