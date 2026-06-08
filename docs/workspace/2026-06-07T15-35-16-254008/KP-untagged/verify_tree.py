# 临时验证脚本：确认初始AVL树合法性和两次插入的旋转过程
# 此脚本仅用于设计阶段验证，不是正式的verify.py

class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None
        self.height = 1  # 叶子高度为1

def height(node):
    if node is None:
        return 0
    return node.height

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

def insert(root, val):
    if root is None:
        return Node(val)
    if val < root.val:
        root.left = insert(root.left, val)
    else:
        root.right = insert(root.right, val)
    
    update_height(root)
    bf = balance_factor(root)
    
    # LL
    if bf > 1 and val < root.left.val:
        print(f"  LL旋转: 失衡节点={root.val}")
        return right_rotate(root)
    # RR
    if bf < -1 and val > root.right.val:
        print(f"  RR旋转: 失衡节点={root.val}")
        return left_rotate(root)
    # LR
    if bf > 1 and val > root.left.val:
        print(f"  LR旋转: 失衡节点={root.val}, 先左旋{root.left.val}, 再右旋{root.val}")
        root.left = left_rotate(root.left)
        return right_rotate(root)
    # RL
    if bf < -1 and val < root.right.val:
        print(f"  RL旋转: 失衡节点={root.val}")
        root.right = right_rotate(root.right)
        return left_rotate(root)
    
    return root

def print_tree_inorder(node, depth=0):
    if node:
        print_tree_inorder(node.left, depth+1)
        print(f"  {'  '*depth}{node.val} (BF={balance_factor(node)}, h={height(node)})")
        print_tree_inorder(node.right, depth+1)

def bracket_notation(node):
    if node is None:
        return ""
    left = bracket_notation(node.left)
    right = bracket_notation(node.right)
    result = str(node.val)
    if left or right:
        result += f"({left},{right})" if right else f"({left})"
    return result

def is_avl(node):
    if node is None:
        return True
    bf = balance_factor(node)
    if abs(bf) > 1:
        return False
    return is_avl(node.left) and is_avl(node.right)

# 构建初始AVL树
# 16(8(4(2),12),24(20,28))
root = Node(16)
root.left = Node(8)
root.right = Node(24)
root.left.left = Node(4)
root.left.right = Node(12)
root.right.left = Node(20)
root.right.right = Node(28)
root.left.left.left = Node(2)

# 更新所有高度
def update_all_heights(node):
    if node is None:
        return
    update_all_heights(node.left)
    update_all_heights(node.right)
    update_height(node)

update_all_heights(root)

print("===== 初始AVL树 =====")
print(f"括号表示: {bracket_notation(root)}")
print(f"是否AVL: {is_avl(root)}")
print("非叶节点平衡因子:")
print_tree_inorder(root)

print("\n===== 插入关键字1 =====")
root = insert(root, 1)
print(f"括号表示: {bracket_notation(root)}")
print(f"是否AVL: {is_avl(root)}")

print("\n===== 插入关键字6 =====")
root = insert(root, 6)
print(f"括号表示: {bracket_notation(root)}")
print(f"是否AVL: {is_avl(root)}")
print("最终树结构:")
print_tree_inorder(root)
