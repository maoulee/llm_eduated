# 完整验证：从初始树构建，逐步插入1和6，验证所有答案

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
    result = str(node.val)
    if left or right:
        if right:
            result += f"({left},{right})"
        else:
            result += f"({left})"
    return result

def insert_avl(root, val):
    """标准AVL插入，带详细输出"""
    if root is None:
        return Node(val)
    if val < root.val:
        root.left = insert_avl(root.left, val)
    else:
        root.right = insert_avl(root.right, val)
    
    update_height(root)
    bf = balance_factor(root)
    
    if bf > 1:
        if val < root.left.val:
            # LL
            print(f"  LL型: 对节点{root.val}右旋")
            return right_rotate(root)
        else:
            # LR
            print(f"  LR型: 先对节点{root.left.val}左旋，再对节点{root.val}右旋")
            root.left = left_rotate(root.left)
            return right_rotate(root)
    if bf < -1:
        if val > root.right.val:
            # RR
            print(f"  RR型: 对节点{root.val}左旋")
            return left_rotate(root)
        else:
            # RL
            print(f"  RL型: 先对节点{root.right.val}右旋，再对节点{root.val}左旋")
            root.right = right_rotate(root.right)
            return left_rotate(root)
    return root

def is_avl(node):
    if node is None:
        return True
    bf = balance_factor(node)
    if abs(bf) > 1:
        print(f"  非AVL! 节点{node.val}的BF={bf}")
        return False
    return is_avl(node.left) and is_avl(node.right)

# ===== 构建初始树 =====
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

print("=" * 60)
print("子问题(1): 初始树平衡因子")
print("=" * 60)
print(f"树结构: {bracket_notation(root)}")
print(f"节点16: BF={balance_factor(root)}")
print(f"节点8: BF={balance_factor(root.left)}")
print(f"节点4: BF={balance_factor(root.left.left)}")
print(f"节点24: BF={balance_factor(root.right)}")
print(f"节点12: BF={balance_factor(root.left.right)}")
print(f"节点2: BF={balance_factor(root.left.left.left)}")
print(f"节点20: BF={balance_factor(root.right.left)}")
print(f"节点28: BF={balance_factor(root.right.right)}")
print(f"是否AVL: {is_avl(root)}")

print("\n" + "=" * 60)
print("子问题(2): 插入关键字1")
print("=" * 60)
root = insert_avl(root, 1)
print(f"插入后树结构: {bracket_notation(root)}")
print(f"是否AVL: {is_avl(root)}")
print(f"原节点4位置现在是谁: {root.left.left.val}")
print(f"其左孩子: {root.left.left.left.val if root.left.left.left else '空'}")
print(f"其右孩子: {root.left.left.right.val if root.left.left.right else '空'}")
print(f"旋转后平衡因子: {balance_factor(root.left.left)}")

print("\n" + "=" * 60)
print("子问题(3): 插入关键字6")
print("=" * 60)
print(f"插入前树: {bracket_notation(root)}")
# 手动检查插入6后的失衡情况
# 当前树: 16(8(2(1,4),12),24(20,28))
# 插入6: 6<16->8, 6<8->2, 6>2->4, 6>4->4的右子树(空) => 插入为4的右孩子
# 插入后回溯:
# 节点4: BF = 0-1 = -1
# 节点2: 左=1(高度1), 右=4(高度2) => BF = 1-2 = -1
# 节点8: 左=2(高度3, 因为2->4->6), 右=12(高度1) => BF = 3-1 = 2 => 失衡!
# 节点8的左孩子是节点2, 节点2的BF=-1 < 0 => LR型

root = insert_avl(root, 6)
print(f"插入后树结构: {bracket_notation(root)}")
print(f"是否AVL: {is_avl(root)}")

print("\n" + "=" * 60)
print("最终树各节点平衡因子")
print("=" * 60)
print(f"根节点16: BF={balance_factor(root)}")
print(f"左子树根: {root.left.val}, BF={balance_factor(root.left)}")
print(f"右子树根: {root.right.val}, BF={balance_factor(root.right)}")

# 子问题(4): 旋转操作顺序
print("\n" + "=" * 60)
print("子问题(4): LR型旋转操作顺序验证")
print("=" * 60)
print("LR型: 节点A的左子树较高，且左子树L的右子树较高")
print("第一步: 对A的左孩子L做左旋(将其右孩子提上来)")
print("第二步: 对A做右旋(将新的左孩子提上来)")
print("LL型: 对A直接做一次右旋即可")
print("关键区别: LL型只需一次旋转，LR/RL型需要两次旋转")
print("LR型第一次旋转是左旋(不是右旋!)，这是经典易错点")
