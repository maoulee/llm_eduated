# ===== 独立AVL树模拟（不依赖param_design.py）=====
# 插入序列
SEQ = [16, 3, 7, 11, 9, 26, 18, 14, 15, 20]

class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None
        self.height = 1

def h(node):
    return node.height if node else 0

def bf(node):
    if not node:
        return 0
    return h(node.left) - h(node.right)

def upd(node):
    node.height = 1 + max(h(node.left), h(node.right))

def rot_right(y):
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    upd(y)
    upd(x)
    return x

def rot_left(x):
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    upd(x)
    upd(y)
    return y

def insert(root, val, events):
    if not root:
        return Node(val)
    if val < root.val:
        root.left = insert(root.left, val, events)
    elif val > root.val:
        root.right = insert(root.right, val, events)
    else:
        return root

    upd(root)
    balance = bf(root)

    if balance > 1:
        if bf(root.left) >= 0:
            events.append((val, "LL"))
            return rot_right(root)
        else:
            events.append((val, "LR"))
            root.left = rot_left(root.left)
            return rot_right(root)
    elif balance < -1:
        if bf(root.right) <= 0:
            events.append((val, "RR"))
            return rot_left(root)
        else:
            events.append((val, "RL"))
            root.right = rot_right(root.right)
            return rot_left(root)

    return root

from collections import deque

def level_order(root):
    if not root:
        return []
    result = []
    q = deque([root])
    while q:
        node = q.popleft()
        result.append(node.val)
        if node.left:
            q.append(node.left)
        if node.right:
            q.append(node.right)
    return result

def print_tree(root, indent="", prefix=""):
    if root:
        print(f"{indent}{prefix}{root.val}(h={root.height},bf={bf(root)})")
        if root.left or root.right:
            if root.left:
                print_tree(root.left, indent + "  ", "L:")
            else:
                print(f"{indent}  L: (null)")
            if root.right:
                print_tree(root.right, indent + "  ", "R:")
            else:
                print(f"{indent}  R: (null)")

# 模拟
root = None
events = []
for i, val in enumerate(SEQ):
    root = insert(root, val, events)
    if events and events[-1][0] == val:
        rtype = events[-1][1]
        print(f"插入 {val}: 失衡 -> {rtype}型调整")
    else:
        print(f"插入 {val}: 未失衡")
    print(f"  层序: {level_order(root)}")

print(f"\n===== 验证结果 =====")
print(f"总失衡次数: {len(events)}")
print(f"各次失衡: {events}")
print(f"旋转类型集合: {set(e[1] for e in events)}")
print(f"最终层序遍历: {level_order(root)}")
print(f"\n===== 最终树结构 =====")
print_tree(root)

# 验证最终树是否平衡
def check_avl(root):
    if not root:
        return True, 0
    ok_l, hl = check_avl(root.left)
    ok_r, hr = check_avl(root.right)
    balance_ok = abs(hl - hr) <= 1
    height_ok = (root.height == 1 + max(hl, hr))
    return (ok_l and ok_r and balance_ok and height_ok), 1 + max(hl, hr)

is_avl, _ = check_avl(root)
print(f"\n最终树是否为合法AVL: {is_avl}")

# 验证BST性质
def check_bst(root, lo=float('-inf'), hi=float('inf')):
    if not root:
        return True
    if root.val <= lo or root.val >= hi:
        return False
    return check_bst(root.left, lo, root.val) and check_bst(root.right, root.val, hi)

print(f"最终树是否为合法BST: {check_bst(root)}")
