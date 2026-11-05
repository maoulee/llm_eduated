"""
AVL树插入序列验证脚本 - 版本4
使用小范围数字搜索友好序列
"""

import random

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    if not node:
        return 0
    return node.height

def get_balance(node):
    if not node:
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

def insert(root, key):
    rotations = []
    if not root:
        return Node(key), rotations
    
    if key < root.key:
        root.left, r = insert(root.left, key)
        rotations.extend(r)
    elif key > root.key:
        root.right, r = insert(root.right, key)
        rotations.extend(r)
    else:
        return root, rotations
    
    update_height(root)
    balance = get_balance(root)
    
    if balance > 1 and key < root.left.key:
        rotations.append(("LL", root.key))
        return right_rotate(root), rotations
    if balance < -1 and key > root.right.key:
        rotations.append(("RR", root.key))
        return left_rotate(root), rotations
    if balance > 1 and key > root.left.key:
        rotations.append(("LR", root.key))
        root.left = left_rotate(root.left)
        return right_rotate(root), rotations
    if balance < -1 and key < root.right.key:
        rotations.append(("RL", root.key))
        root.right = right_rotate(root.right)
        return left_rotate(root), rotations
    
    return root, rotations

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def test_sequence(seq):
    root = None
    all_rotations = []
    for key in seq:
        root, rotations = insert(root, key)
        for r in rotations:
            all_rotations.append((key, r[0], r[1]))
    rot_types = set(r[1] for r in all_rotations)
    return rot_types, all_rotations, inorder(root)

# 在小范围内搜索
results = []
for seed in range(10000):
    random.seed(seed)
    for n in [10, 11, 12]:
        seq = random.sample(range(1, 30), n)
        rot_types, all_rotations, inorder_result = test_sequence(seq)
        if rot_types == {"LL", "RR", "LR", "RL"}:
            results.append((seq, all_rotations, len(all_rotations)))
            if len(results) >= 20:
                break
    if len(results) >= 20:
        break

# 按旋转次数排序，找最少的
results.sort(key=lambda x: x[2])

for i, (seq, all_rotations, count) in enumerate(results[:10]):
    print(f"\n结果{i+1} (旋转{count}次):")
    print(f"序列: {seq}")
    print(f"旋转记录: {all_rotations}")
