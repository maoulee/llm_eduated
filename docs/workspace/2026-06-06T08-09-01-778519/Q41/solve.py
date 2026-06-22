# ===== 题目参数定义 =====
# 初始AVL树: 完美平衡二叉树，所有结点BF=0
# 结点: 40(根), 20, 60, 10, 30, 50, 70
# 插入序列: 25, 27, 5, 3

# AVL Tree implementation
class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    if node is None:
        return 0
    return node.height

def get_balance(node):
    if node is None:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(y):
    """LL rotation - right single rotation"""
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    update_height(y)
    update_height(x)
    return x

def left_rotate(x):
    """RR rotation - left single rotation"""
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    update_height(x)
    update_height(y)
    return y

rotation_log = []

def insert(node, key):
    if node is None:
        return Node(key)
    if key < node.key:
        node.left = insert(node.left, key)
    elif key > node.key:
        node.right = insert(node.right, key)
    else:
        return node
    update_height(node)
    balance = get_balance(node)
    # LL rotation
    if balance > 1 and key < node.left.key:
        rotation_log.append(f"LL rotation (right single) at node {node.key}")
        return right_rotate(node)
    # RR rotation
    if balance < -1 and key > node.right.key:
        rotation_log.append(f"RR rotation (left single) at node {node.key}")
        return left_rotate(node)
    # LR rotation
    if balance > 1 and key > node.left.key:
        rotation_log.append(f"LR rotation (left-right double) at node {node.key}")
        node.left = left_rotate(node.left)
        return right_rotate(node)
    # RL rotation
    if balance < -1 and key < node.right.key:
        rotation_log.append(f"RL rotation (right-left double) at node {node.key}")
        node.right = right_rotate(node.right)
        return left_rotate(node)
    return node

def build_initial_tree():
    root = Node(40)
    root.left = Node(20)
    root.right = Node(60)
    root.left.left = Node(10)
    root.left.right = Node(30)
    root.right.left = Node(50)
    root.right.right = Node(70)
    update_height(root.left.left)
    update_height(root.left.right)
    update_height(root.right.left)
    update_height(root.right.right)
    update_height(root.left)
    update_height(root.right)
    update_height(root)
    return root

def print_tree(node, level=0, prefix="Root: "):
    if node is not None:
        print("  " * level + prefix + str(node.key) + f" (h={node.height}, bf={get_balance(node)})")
        if node.left is not None or node.right is not None:
            if node.left:
                print_tree(node.left, level + 1, "L--- ")
            else:
                print("  " * (level + 1) + "L--- None")
            if node.right:
                print_tree(node.right, level + 1, "R--- ")
            else:
                print("  " * (level + 1) + "R--- None")

def find_node(node, key):
    if node is None:
        return None
    if node.key == key:
        return node
    if key < node.key:
        return find_node(node.left, key)
    return find_node(node.right, key)

# ===== 构建初始树 =====
root = build_initial_tree()
print("=== 初始 AVL 树 ===")
print_tree(root)
print()

# ===== 插入 25 =====
print("===== 插入关键字 25 =====")
rotation_log.clear()
root = insert(root, 25)
print_tree(root)
if rotation_log:
    print(f"旋转操作: {rotation_log}")
else:
    print("无旋转")
print()

# ===== 子问题(1): 插入 27 后的旋转类型 =====
print("===== 插入关键字 27 =====")
rotation_log.clear()
root = insert(root, 27)
print_tree(root)
if rotation_log:
    print(f"旋转操作: {rotation_log}")
else:
    print("无旋转")
result_1 = rotation_log[0] if rotation_log else "无旋转"
print(f"\n子问题(1): 插入27后的旋转类型")
print(f"  最小不平衡子树根为30，新结点27插入在30左子树(25)的右子树上")
print(f"  => LR旋转（先左后右双旋）")
print(f"  答案: B: LR旋转（先左后右双旋）")
print()

# ===== 插入 5 =====
print("===== 插入关键字 5 =====")
rotation_log.clear()
root = insert(root, 5)
print_tree(root)
if rotation_log:
    print(f"旋转操作: {rotation_log}")
else:
    print("无旋转")
print()

# ===== 插入 3 =====
print("===== 插入关键字 3 =====")
rotation_log.clear()
root = insert(root, 3)
print_tree(root)
if rotation_log:
    print(f"旋转操作: {rotation_log}")
else:
    print("无旋转")
print()

# ===== 子问题(2): 最终AVL树结构 =====
print("子问题(2): 最终AVL树结构")
print_tree(root)
print()

# ===== 子问题(3): 关于最终AVL树的说法 =====
print("子问题(3): 关于最终AVL树的说法")
n20 = find_node(root, 20)
left_h_20 = get_height(n20.left)
right_h_20 = get_height(n20.right)
print(f"  A: 结点20左子树高度={left_h_20}, 右子树高度={right_h_20}, 是否相等: {left_h_20 == right_h_20}")

tree_height = get_height(root)
print(f"  B: 最终AVL树高度={tree_height} (高度为4，非5)")

root_bf = get_balance(root)
print(f"  C: 根结点40的平衡因子={root_bf} (非0)")

n5 = find_node(root, 5)
is_leaf_5 = (n5.left is None and n5.right is None)
print(f"  D: 结点5左孩子={n5.left.key if n5.left else None}, 右孩子={n5.right.key if n5.right else None}, 是否叶子: {is_leaf_5}")

result_3 = "A" if left_h_20 == right_h_20 else "无法确定"
print(f"\n  正确选项: {result_3}")

# ===== 最终输出 =====
print(f"\n===== 最终答案 =====")
print(f"子问题(1): B (LR旋转)")
print(f"子问题(3): A")
print(f"ANSWER: (1)B (2)见树形图 (3)A")
