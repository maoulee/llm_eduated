# AVL 树求解代码
# 模拟 AVL 树的插入与旋转过程

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
    # 普通 BST 插入
    if not node:
        return AVLNode(key)
    if key < node.key:
        node.left = insert(node.left, key)
    elif key > node.key:
        node.right = insert(node.right, key)
    else:
        return node  # 不允许重复关键字
    
    update_height(node)
    balance = get_balance(node)
    
    # LL 型：左左旋转
    if balance > 1 and key < node.left.key:
        return right_rotate(node)
    
    # RR 型：右右旋转
    if balance < -1 and key > node.right.key:
        return left_rotate(node)
    
    # LR 型：先左后右旋转
    if balance > 1 and key > node.left.key:
        node.left = left_rotate(node.left)
        return right_rotate(node)
    
    # RL 型：先右后左旋转
    if balance < -1 and key < node.right.key:
        node.right = right_rotate(node.right)
        return left_rotate(node)
    
    return node

def print_tree(node, level=0, prefix="Root: "):
    if node is not None:
        print(" " * (level * 4) + prefix + str(node.key))
        if node.left or node.right:
            if node.left:
                print_tree(node.left, level + 1, "L--- ")
            else:
                print(" " * ((level + 1) * 4) + "L--- None")
            if node.right:
                print_tree(node.right, level + 1, "R--- ")
            else:
                print(" " * ((level + 1) * 4) + "R--- None")

# 初始插入序列
initial_sequence = [30, 20, 40, 10, 25]
insert_key = 5

# 构建初始 AVL 树
root = None
for key in initial_sequence:
    root = insert(root, key)

print("初始 AVL 树（插入序列：{}）:".format(initial_sequence))
print_tree(root)
print()

# 插入新关键字
root = insert(root, insert_key)
print("插入 {} 后的 AVL 树:".format(insert_key))
print_tree(root)
print()

# 输出答案
print("插入 {} 后，根节点的关键字值为: {}".format(insert_key, root.key))
print("树的高度为: {}".format(get_height(root)))
