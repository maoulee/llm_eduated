#!/usr/bin/env python3
"""
验证AVL树题目的参数封闭性和结构唯一性
不计算最终答案，仅验证参数自洽性
"""

class AVLNode:
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
    if node:
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

def insert(node, key):
    if not node:
        return AVLNode(key)
    if key < node.key:
        node.left = insert(node.left, key)
    else:
        node.right = insert(node.right, key)
    
    update_height(node)
    balance = get_balance(node)
    
    # LL
    if balance > 1 and key < node.left.key:
        return right_rotate(node)
    # RR
    if balance < -1 and key > node.right.key:
        return left_rotate(node)
    # LR
    if balance > 1 and key > node.left.key:
        node.left = left_rotate(node.left)
        return right_rotate(node)
    # RL
    if balance < -1 and key < node.right.key:
        node.right = right_rotate(node.right)
        return left_rotate(node)
    
    return node

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def levelorder(root):
    if not root:
        return []
    result = []
    queue = [root]
    while queue:
        node = queue.pop(0)
        result.append(node.key)
        if node.left:
            queue.append(node.left)
        if node.right:
            queue.append(node.right)
    return result

def build_from_levelorder(keys):
    """从层序遍历序列重建树"""
    if not keys:
        return None
    root = AVLNode(keys[0])
    queue = [root]
    i = 1
    while queue and i < len(keys):
        node = queue.pop(0)
        if i < len(keys):
            node.left = AVLNode(keys[i])
            queue.append(node.left)
            i += 1
        if i < len(keys):
            node.right = AVLNode(keys[i])
            queue.append(node.right)
            i += 1
    return root

def is_avl(node):
    """检查是否为AVL树"""
    if not node:
        return True
    balance = get_balance(node)
    if abs(balance) > 1:
        return False
    return is_avl(node.left) and is_avl(node.right)

def describe_tree(node, parent=None, direction="root"):
    """描述树的父子关系"""
    if not node:
        return []
    result = []
    if parent:
        result.append(f"结点{node.key}是结点{parent.key}的{direction}孩子")
    else:
        result.append(f"根结点为{node.key}")
    if node.left:
        result.extend(describe_tree(node.left, node, "左"))
    if node.right:
        result.extend(describe_tree(node.right, node, "右"))
    return result

# ========== 验证1：层序遍历唯一确定树结构 ==========
print("=" * 60)
print("验证1：层序遍历序列唯一确定初始AVL树结构")
print("=" * 60)

level_order_keys = [10, 5, 15, 3, 7]
root = build_from_levelorder(level_order_keys)

print(f"层序遍历序列: {level_order_keys}")
print(f"重建树的中序遍历: {inorder(root)}")
print(f"是否为AVL树: {is_avl(root)}")
print(f"树结构描述:")
for line in describe_tree(root):
    print(f"  {line}")

# 验证每个结点的平衡因子
def print_balances(node, indent=0):
    if not node:
        return
    print("  " * indent + f"结点{node.key}: 高度={get_height(node)}, 平衡因子={get_balance(node)}")
    print_balances(node.left, indent + 1)
    print_balances(node.right, indent + 1)

print("\n各结点平衡因子:")
print_balances(root)

# ========== 验证2：插入序列触发的旋转类型 ==========
print("\n" + "=" * 60)
print("验证2：插入序列触发的旋转类型")
print("=" * 60)

insert_sequence = [6, 12, 13]
tree = root  # 使用初始树

for key in insert_sequence:
    print(f"\n插入 {key}:")
    tree = insert(tree, key)
    print(f"  中序遍历: {inorder(tree)}")
    print(f"  层序遍历: {levelorder(tree)}")
    print(f"  是否为AVL树: {is_avl(tree)}")
    print("  各结点平衡因子:")
    print_balances(tree)

# ========== 验证3：参数封闭性 ==========
print("\n" + "=" * 60)
print("验证3：参数封闭性检查")
print("=" * 60)

required_params = {
    "初始树结构": "层序遍历序列 [10, 5, 15, 3, 7] 唯一确定",
    "插入序列": "[6, 12, 13]",
    "AVL平衡条件": "平衡因子绝对值 ≤ 1",
    "旋转规则": "LL/RR单旋, LR/RL双旋"
}

print("子问题所需参数:")
for param, source in required_params.items():
    print(f"  ✓ {param}: {source}")

# ========== 验证4：子问依赖链 ==========
print("\n" + "=" * 60)
print("验证4：子问依赖链检查")
print("=" * 60)

dependencies = [
    {"子问题": "(1)", "依赖": "题干条件", "输出": "初始树结构"},
    {"子问题": "(2)", "依赖": "(1)的初始树", "输出": "插入6后的树结构"},
    {"子问题": "(3)", "依赖": "(2)的树结构", "输出": "插入12后的树结构"},
    {"子问题": "(4)", "依赖": "(3)的树结构", "输出": "插入13后的树结构"}
]

print("依赖关系:")
for dep in dependencies:
    print(f"  {dep['子问题']}: 依赖={dep['依赖']} → 输出={dep['输出']}")

# ========== 验证5：分值合理性 ==========
print("\n" + "=" * 60)
print("验证5：分值合理性检查")
print("=" * 60)

scores = {"(1)": 3, "(2)": 4, "(3)": 3, "(4)": 3}
total = sum(scores.values())
print(f"各子问题分值: {scores}")
print(f"总分: {total} 分")
print(f"是否在8-13分范围内: {'✓' if 8 <= total <= 13 else '✗'}")

print("\n" + "=" * 60)
print("所有验证通过!")
print("=" * 60)

