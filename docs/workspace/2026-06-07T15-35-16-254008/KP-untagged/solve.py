# ===== AVL树插入与旋转求解 =====

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
        return False
    return is_avl(node.left) and is_avl(node.right)

def insert_avl(root, val):
    if root is None:
        return Node(val)
    if val < root.val:
        root.left = insert_avl(root.left, val)
    else:
        root.right = insert_avl(root.right, val)
    update_height(root)
    bf = balance_factor(root)
    if bf > 1 and val < root.left.val:
        print(f"  旋转类型: LL, 失衡节点={root.val}")
        return right_rotate(root)
    if bf < -1 and val > root.right.val:
        print(f"  旋转类型: RR, 失衡节点={root.val}")
        return left_rotate(root)
    if bf > 1 and val > root.left.val:
        print(f"  旋转类型: LR, 失衡节点={root.val}, 先左旋{root.left.val}, 再右旋{root.val}")
        root.left = left_rotate(root.left)
        return right_rotate(root)
    if bf < -1 and val < root.right.val:
        print(f"  旋转类型: RL, 失衡节点={root.val}, 先右旋{root.right.val}, 再左旋{root.val}")
        root.right = right_rotate(root.right)
        return left_rotate(root)
    return root

def update_all_heights(node):
    if node is None:
        return
    update_all_heights(node.left)
    update_all_heights(node.right)
    update_height(node)

# ===== 构建初始AVL树: 16(8(4(2),12),24(20,28)) =====
root = Node(16)
root.left = Node(8)
root.right = Node(24)
root.left.left = Node(4)
root.left.right = Node(12)
root.right.left = Node(20)
root.right.right = Node(28)
root.left.left.left = Node(2)
update_all_heights(root)

# ===== 子问题(1): 初始平衡因子 + 插入1的失衡判定 =====
print("=" * 60)
print("子问题(1): 初始树平衡因子")
print("=" * 60)
print(f"  初始树: {bracket_notation(root)}")
print(f"  BF(16) = {balance_factor(root)}")
print(f"  BF(8)  = {balance_factor(root.left)}")
print(f"  BF(4)  = {balance_factor(root.left.left)}")
print(f"  BF(24) = {balance_factor(root.right)}")
print(f"\n插入关键字1:")
root = insert_avl(root, 1)
print(f"  插入后树: {bracket_notation(root)}")
print(f"  是否AVL: {is_avl(root)}")

# ===== 子问题(2): 插入1后的树结构 =====
print(f"\n{'=' * 60}")
print("子问题(2): 插入1并完成LL旋转后的树结构")
print("=" * 60)
print(f"  调整后树: {bracket_notation(root)}")
print(f"  节点8的左孩子: {root.left.left.val} (原为4, 现为2)")
print(f"  节点2的右孩子: {root.left.left.right.val} (节点4)")
print(f"  节点4的左孩子: {root.left.left.right.left}")

# ===== 子问题(3): 插入6的失衡判定与LR旋转 =====
print(f"\n{'=' * 60}")
print("子问题(3): 插入关键字6")
print("=" * 60)
root = insert_avl(root, 6)
print(f"  调整后树: {bracket_notation(root)}")
print(f"  是否AVL: {is_avl(root)}")
print(f"  根节点16的左孩子: {root.left.val} (节点4)")
print(f"  节点4的左孩子: {root.left.left.val} (节点2)")
print(f"  节点4的右孩子: {root.left.right.val} (节点8)")

# ===== 子问题(4): 旋转对比 =====
print(f"\n{'=' * 60}")
print("子问题(4): LL与LR旋转对比")
print("=" * 60)
print("  LL型: 1次旋转(右旋), 用于新节点在失衡节点左孩子的左子树")
print("  LR型: 2次旋转(先左旋再右旋), 用于新节点在失衡节点左孩子的右子树")
print("  误判后果: 若LR型第一次旋转方向错误(右旋而非左旋),")
print("           会加剧失衡而非恢复平衡")

# ===== 最终答案汇总 =====
print(f"\n{'=' * 60}")
print("ANSWER汇总")
print("=" * 60)
print("ANSWER(1): BF(16)=1, BF(8)=1, BF(4)=1, BF(24)=0; 失衡节点=4, LL型")
print("ANSWER(2): 16(8(2(1,4),12),24(20,28))")
print("ANSWER(3): 失衡节点=8, LR型; 调整后: 16(4(2(1),8(6,12)),24(20,28))")
print("ANSWER(4): LL型1次右旋; LR型2次旋转(先左旋后右旋); 误判方向会加剧失衡")
