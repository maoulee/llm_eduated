from collections import deque

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None

def height(node):
    if node is None:
        return 0
    return 1 + max(height(node.left), height(node.right))

def bf(node):
    """平衡因子 = 左子树高度 - 右子树高度，单个结点高度为1"""
    if node is None:
        return 0
    lh = height(node.left) if node.left else 0
    rh = height(node.right) if node.right else 0
    return lh - rh

def print_tree(root):
    """打印树结构"""
    if root is None:
        print("(empty)")
        return
    q = deque([root])
    while q:
        level_size = len(q)
        level = []
        for _ in range(level_size):
            node = q.popleft()
            level.append(str(node.key))
            if node.left:
                q.append(node.left)
            if node.right:
                q.append(node.right)
        print("  ".join(level))

def print_bfs_all(root):
    """打印每个节点的平衡因子"""
    def _walk(node):
        if node is None:
            return
        _walk(node.left)
        b = bf(node)
        h = height(node)
        print(f"  结点{node.key}: 高度={h}, BF={b}")
        _walk(node.right)
    _walk(root)

def find_min_unbalanced(root):
    """找到最小不平衡子树的根（离插入点最近的失衡结点）"""
    unbalanced = []
    def _walk(node):
        if node is None:
            return None
        _walk(node.left)
        if abs(bf(node)) > 1:
            unbalanced.append(node.key)
        _walk(node.right)
    _walk(root)
    return unbalanced

def insert_bst(root, key):
    """普通BST插入，返回根节点"""
    if root is None:
        return Node(key)
    if key < root.key:
        root.left = insert_bst(root.left, key)
    else:
        root.right = insert_bst(root.right, key)
    return root

def right_rotate(y):
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    return x

def left_rotate(x):
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    return y

def insert_avl(root, key, trace=False):
    """AVL插入（递归），返回新的根"""
    # Step 1: BST插入
    if root is None:
        return Node(key)
    if key < root.key:
        root.left = insert_avl(root.left, key, trace)
    else:
        root.right = insert_avl(root.right, key, trace)

    # Step 2: 更新高度和平衡因子
    balance = bf(root)

    # Step 3: 四种旋转情况
    # LL
    if balance > 1 and key < root.left.key:
        if trace: print(f"  LL旋转: 以结点{root.key}为轴右旋")
        return right_rotate(root)
    # RR
    if balance < -1 and key > root.right.key:
        if trace: print(f"  RR旋转: 以结点{root.key}为轴左旋")
        return left_rotate(root)
    # LR
    if balance > 1 and key > root.left.key:
        if trace: print(f"  LR旋转: 先左旋{root.left.key}，再右旋{root.key}")
        root.left = left_rotate(root.left)
        return right_rotate(root)
    # RL
    if balance < -1 and key < root.right.key:
        if trace: print(f"  RL旋转: 先右旋{root.right.key}，再左旋{root.key}")
        root.right = right_rotate(root.right)
        return left_rotate(root)

    return root

# ===== 构建初始AVL树 =====
#             33
#            /  \
#           20   50
#          / \   / \
#        10  30 40  60
#       /
#      5
root = Node(33)
root.left = Node(20)
root.right = Node(50)
root.left.left = Node(10)
root.left.right = Node(30)
root.left.left.left = Node(5)
root.right.left = Node(40)
root.right.right = Node(60)

print("="*60)
print("初始树:")
print_tree(root)
print("平衡因子检查:")
print_bfs_all(root)
print(f"所有失衡结点: {find_min_unbalanced(root)}")

# ===== (1) 插入1 =====
print("\n" + "="*60)
print("(1) 插入关键字 1")
# 先看普通BST插入后的结果
import copy
root_bst1 = copy.deepcopy(root)
root_bst1 = insert_bst(root_bst1, 1)
print("BST插入1后:")
print_tree(root_bst1)
print("平衡因子检查:")
print_bfs_all(root_bst1)
print(f"所有失衡结点: {find_min_unbalanced(root_bst1)}")

# AVL插入
root = insert_avl(root, 1, trace=True)
print("\nAVL调整后整棵树:")
print_tree(root)
print("平衡因子检查:")
print_bfs_all(root)
print(f"所有失衡结点: {find_min_unbalanced(root)}")

# ===== (2) 插入7 =====
print("\n" + "="*60)
print("(2) 插入关键字 7")
root_bst2 = copy.deepcopy(root)
root_bst2 = insert_bst(root_bst2, 7)
print("BST插入7后:")
print_tree(root_bst2)
print("平衡因子检查:")
print_bfs_all(root_bst2)
print(f"所有失衡结点: {find_min_unbalanced(root_bst2)}")

root = insert_avl(root, 7, trace=True)
print("\nAVL调整后整棵树:")
print_tree(root)
print("平衡因子检查:")
print_bfs_all(root)
print(f"所有失衡结点: {find_min_unbalanced(root)}")

# ===== (3) 插入25 =====
print("\n" + "="*60)
print("(3) 插入关键字 25")
root_bst3 = copy.deepcopy(root)
root_bst3 = insert_bst(root_bst3, 25)
print("BST插入25后:")
print_tree(root_bst3)
print("平衡因子检查:")
print_bfs_all(root_bst3)
print(f"所有失衡结点: {find_min_unbalanced(root_bst3)}")

root = insert_avl(root, 25, trace=True)
print("\nAVL调整后整棵树:")
print_tree(root)
print("平衡因子检查:")
print_bfs_all(root)
print(f"所有失衡结点: {find_min_unbalanced(root)}")

# ===== (4) 根结点33的平衡因子 =====
print("\n" + "="*60)
print("(4) 最终结果:")
print(f"根结点33的平衡因子: BF(33) = {bf(root)}")
print(f"  左子树高度 = {height(root.left)}")
print(f"  右子树高度 = {height(root.right)}")
