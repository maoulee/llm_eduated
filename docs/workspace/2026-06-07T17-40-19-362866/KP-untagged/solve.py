# ===== AVL 树插入模拟器 =====
# 模拟题干插入序列，输出每步树结构和旋转信息

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

    if balance > 1 and key < node.left.key:
        rotations.append((step, key, node.key, "LL"))
        return right_rotate(node)
    if balance < -1 and key > node.right.key:
        rotations.append((step, key, node.key, "RR"))
        return left_rotate(node)
    if balance > 1 and key > node.left.key:
        rotations.append((step, key, node.key, "LR"))
        node.left = left_rotate(node.left)
        return right_rotate(node)
    if balance < -1 and key < node.right.key:
        rotations.append((step, key, node.key, "RL"))
        node.right = right_rotate(node.right)
        return left_rotate(node)
    return node

def print_tree(node, level=0, prefix=""):
    if node is not None:
        print("    " * level + prefix + f"{node.key} [BF={bf(node)}]")
        if node.left:
            print_tree(node.left, level + 1, "L--- ")
        if node.right:
            print_tree(node.right, level + 1, "R--- ")

def inorder(node):
    if node:
        return inorder(node.left) + [node.key] + inorder(node.right)
    return []

# ===== 子问题(1): 插入 40, 20, 50, 10, 30, 25 =====
print("=" * 60)
print("子问题(1): 插入序列 40, 20, 50, 10, 30, 25")
print("=" * 60)
keys_1 = [40, 20, 50, 10, 30, 25]
root = None
rotations_1 = []
for k in keys_1:
    root = insert(root, k, rotations_1, k)
    print(f"\n插入 {k} 后:")
    print_tree(root)

print(f"\n--- 子问题(1)旋转记录 ---")
for step, key, unbalanced_node, rtype in rotations_1:
    print(f"  插入 {key}: 节点 {unbalanced_node} 失衡 → {rtype} 旋转")

print(f"\n--- 子问题(1)最终树 (插入25后) ---")
print_tree(root)

# ===== 子问题(2): 继续插入 5, 60, 45, 42, 1 =====
print("\n" + "=" * 60)
print("子问题(2): 继续插入 5, 60, 45, 42, 1")
print("=" * 60)
keys_2 = [5, 60, 45, 42, 1]
rotations_2 = []
for k in keys_2:
    root = insert(root, k, rotations_2, k)
    print(f"\n插入 {k} 后:")
    print_tree(root)

print(f"\n--- 子问题(2)旋转记录 ---")
for step, key, unbalanced_node, rtype in rotations_2:
    print(f"  插入 {key}: 节点 {unbalanced_node} 失衡 → {rtype} 旋转")

print(f"\n--- 最终树 (全部11个关键字) ---")
print_tree(root)

# ===== 汇总答案 =====
print("\n" + "=" * 60)
print("ANSWER 汇总")
print("=" * 60)

all_rotations = rotations_1 + rotations_2
print(f"\n子问题(1) LR旋转: 失衡节点={rotations_1[0][2]}, 插入关键字={rotations_1[0][1]}")

print(f"\n子问题(2) 旋转记录:")
for step, key, unbalanced_node, rtype in rotations_2:
    print(f"  插入 {key}: 节点 {unbalanced_node} 失衡 → {rtype} 旋转")

print(f"\n最终中序遍历: {inorder(root)}")

print("\nANSWER: (1) LR旋转,失衡节点40; (2) RR@40(插60),RL@40(插42),LL@10(插1); (3) ①lc->rchild ②node ③Height(lc->lchild) ④Height(lc->rchild)")
