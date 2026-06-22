# 额外验证：确认每个子问题的具体答案
# 同时验证子问题(4)中关于旋转操作的关键考察点

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

# 初始树
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

print("===== 子问题(1): 初始树各节点平衡因子 =====")
print(f"节点16的平衡因子: {balance_factor(root)}")
print(f"节点8的平衡因子: {balance_factor(root.left)}")
print(f"节点4的平衡因子: {balance_factor(root.left.left)}")
print(f"节点24的平衡因子: {balance_factor(root.right)}")
print(f"节点2的平衡因子: {balance_factor(root.left.left.left)}")

print("\n===== 子问题(2): 插入1后的LL旋转 =====")
# 手动模拟插入1
# 插入到4的左子树2的左子树 -> 节点4的BF=2，节点2的BF=1 -> LL型
node4_bf_before = balance_factor(root.left.left)  # 节点4
node2_bf = balance_factor(root.left.left.left)     # 节点2
print(f"插入1后，节点4的平衡因子: {node4_bf_before + 1} (应该是2)")
print(f"插入1后，节点2的平衡因子: {node2_bf + 1} (应该是1)")
print(f"失衡类型判定: 节点4 BF>1，新节点在其左子树的左子树 -> LL型")

# 执行LL旋转（右旋节点4）
new4 = right_rotate(root.left.left)
root.left.left = new4
print(f"旋转后子树(以原节点4位置): {bracket_notation(new4)}")
print(f"  节点2的左孩子: {new4.left.val} (应该是1)")
print(f"  节点2的右孩子: {new4.right.val} (应该是4)")
print(f"旋转后节点2的平衡因子: {balance_factor(new4)}")

print("\n===== 子问题(3): 继续插入6后的LR旋转 =====")
# 先确认当前树状态
print(f"当前树: {bracket_notation(root)}")
print(f"节点8的左子树根: {root.left.left.val} (应该是2)")

# 插入6: 6>4且6<8，插入到节点2的右子树4的左子树
# 但实际：6 > 2，6 < 8，6 < 4? 不，6 > 4
# 让我重新看树结构
# 树是: 16(8(2(1,4),12),24(20,28))
# 插入6: 6<16左, 6<8左, 6>2右, 6>4右 -> 4的右子树
# 所以6插入到4的右孩子
# 插入后节点8的BF: 左子树高度3(2->4->6)，右子树高度1(12) -> BF=2
# 节点2的BF: 左子树高度1(1)，右子树高度2(4->6) -> BF=-1
# 节点8 BF=2，其左孩子节点2 BF=-1 -> LR型

print("\n插入6的路径: 16->8->2->4->6的右子树")
print("插入6后各节点平衡因子:")
print(f"  节点8: 左子树高度=3，右子树高度=1，BF=2 (失衡)")
print(f"  节点2: 左子树高度=1(节点1)，右子树高度=2(节点4->6)，BF=-1")
print(f"失衡类型: 节点8 BF=2，左孩子节点2 BF=-1 -> LR型")

# LR旋转：先对节点2左旋，再对节点8右旋
print("\nLR第一步 - 左旋节点2:")
node8_left = root.left  # 节点8
node2 = node8_left.left  # 节点2
print(f"  左旋前: 节点2的右子树根 = {node2.right.val} (节点4)")
# 先插入6到树中（临时）
node2.right.right = Node(6)
update_all_heights(root)

# 重新获取
node8_left = root.left  # 节点8
node2 = node8_left.left  # 节点2
print(f"  插入6后节点2的平衡因子: {balance_factor(node2)}")
new_node2 = left_rotate(node2)
node8_left.left = new_node2
print(f"  左旋后: 节点4成为该子树根，4的左=2, 4的右=6+原4的右子树")
print(f"  左旋后子树: {bracket_notation(new_node2)}")

# 第二步：右旋节点8
print(f"\nLR第二步 - 右旋节点8:")
print(f"  右旋前节点8的左子树根: {node8_left.left.val}")
new_node8 = right_rotate(node8_left)
root.left = new_node8
print(f"  右旋后子树: {bracket_notation(new_node8)}")
print(f"  最终树: {bracket_notation(root)}")

# 验证最终结果
print(f"\n===== 最终验证 =====")
def is_avl(node):
    if node is None:
        return True
    bf = balance_factor(node)
    if abs(bf) > 1:
        print(f"  非AVL! 节点{node.val}的BF={bf}")
        return False
    return is_avl(node.left) and is_avl(node.right)
print(f"是否AVL: {is_avl(root)}")
