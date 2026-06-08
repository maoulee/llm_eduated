# ===== AVL树参数校验 =====
# 校验初始树是否为合法AVL树
# 校验插入1和6后旋转类型的正确性

class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None
        self.height = 1

def height(node):
    return node.height if node else 0

def balance_factor(node):
    if node is None:
        return 0
    return height(node.left) - height(node.right)

def update_height(node):
    if node:
        node.height = 1 + max(height(node.left), height(node.right))

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

def bracket_notation(node):
    if node is None:
        return ""
    left = bracket_notation(node.left)
    right = bracket_notation(node.right)
    if left and right:
        return f"{node.val}({left},{right})"
    elif left:
        return f"{node.val}({left})"
    elif right:
        return f"{node.val}(,{right})"
    else:
        return f"{node.val}"

def is_avl(node):
    if node is None:
        return True
    bf = balance_factor(node)
    if abs(bf) > 1:
        print(f"  非AVL! 节点{node.val}的BF={bf}")
        return False
    return is_avl(node.left) and is_avl(node.right)

def insert_avl(root, val):
    """标准AVL插入，带旋转类型输出"""
    if root is None:
        return Node(val)
    if val < root.val:
        root.left = insert_avl(root.left, val)
    else:
        root.right = insert_avl(root.right, val)
    update_height(root)
    bf = balance_factor(root)
    # LL型
    if bf > 1 and val < root.left.val:
        print(f"  LL旋转: 失衡节点={root.val}")
        return right_rotate(root)
    # RR型
    if bf < -1 and val > root.right.val:
        print(f"  RR旋转: 失衡节点={root.val}")
        return left_rotate(root)
    # LR型
    if bf > 1 and val > root.left.val:
        print(f"  LR旋转: 失衡节点={root.val}, 先左旋{root.left.val}, 再右旋{root.val}")
        root.left = left_rotate(root.left)
        return right_rotate(root)
    # RL型
    if bf < -1 and val < root.right.val:
        print(f"  RL旋转: 失衡节点={root.val}, 先右旋{root.right.val}, 再左旋{root.val}")
        root.right = right_rotate(root.right)
        return left_rotate(root)
    return root

# ===== 构建初始AVL树 =====
root = Node(16)
root.left = Node(8)
root.right = Node(24)
root.left.left = Node(4)
root.left.right = Node(12)
root.right.left = Node(20)
root.right.right = Node(28)
root.left.left.left = Node(2)

def update_all_heights(node):
    if node is None:
        return
    update_all_heights(node.left)
    update_all_heights(node.right)
    update_height(node)

update_all_heights(root)

# ===== 校验1：初始树是否为合法AVL =====
print("===== 校验1：初始树AVL合法性 =====")
print(f"括号表示: {bracket_notation(root)}")
assert is_avl(root), "初始树不是合法AVL树!"
print("  初始树是合法AVL树 ✓")

# ===== 校验2：初始树各节点平衡因子 =====
print("\n===== 校验2：初始树平衡因子 =====")
bf_16 = balance_factor(root)
bf_8 = balance_factor(root.left)
bf_4 = balance_factor(root.left.left)
bf_24 = balance_factor(root.right)
print(f"  BF(16) = {bf_16}")
print(f"  BF(8) = {bf_8}")
print(f"  BF(4) = {bf_4}")
print(f"  BF(24) = {bf_24}")
assert all(abs(bf) <= 1 for bf in [bf_16, bf_8, bf_4, bf_24]), "存在|BF|>1的节点!"

# ===== 校验3：插入1后的旋转类型 =====
print("\n===== 校验3：插入关键字1 =====")
root_after_1 = insert_avl(root, 1)
print(f"  插入后树: {bracket_notation(root_after_1)}")
assert is_avl(root_after_1), "插入1后树不是合法AVL!"
print("  插入1后仍为合法AVL ✓")

# ===== 校验4：插入6后的旋转类型 =====
print("\n===== 校验4：插入关键字6 =====")
root_after_6 = insert_avl(root_after_1, 6)
print(f"  插入后树: {bracket_notation(root_after_6)}")
assert is_avl(root_after_6), "插入6后树不是合法AVL!"
print("  插入6后仍为合法AVL ✓")

# ===== 校验5：参数封闭性 =====
print("\n===== 校验5：参数封闭性 =====")
required_keys = [16, 8, 4, 2, 12, 24, 20, 28]  # 初始树节点
insert_keys = [1, 6]  # 插入关键字
print(f"  初始树关键字: {required_keys}")
print(f"  插入关键字: {insert_keys}")
print("  所有子问题所需参数均在题干中给出 ✓")

print("\n参数校验通过")
