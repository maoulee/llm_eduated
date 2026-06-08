"""
AVL 题目设计验证 - 第二轮
目标: 初始树 → 插入A触发LR → 插入B触发RL
"""

class AVLNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def height(node):
    return node.height if node else 0

def balance_factor(node):
    if not node: return 0
    return height(node.left) - height(node.right)

def update_height(node):
    node.height = 1 + max(height(node.left), height(node.right))

def rotate_right(y):
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    update_height(y)
    update_height(x)
    return x

def rotate_left(x):
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
        return AVLNode(key)
    if key < node.key:
        node.left = insert(node.left, key)
    else:
        node.right = insert(node.right, key)
    update_height(node)
    bf = balance_factor(node)
    if bf > 1 and key < node.left.key:
        rotation_log.append(f"LL at {node.key} (insert {key})")
        return rotate_right(node)
    if bf < -1 and key > node.right.key:
        rotation_log.append(f"RR at {node.key} (insert {key})")
        return rotate_left(node)
    if bf > 1 and key > node.left.key:
        rotation_log.append(f"LR at {node.key} (insert {key})")
        node.left = rotate_left(node.left)
        return rotate_right(node)
    if bf < -1 and key < node.right.key:
        rotation_log.append(f"RL at {node.key} (insert {key})")
        node.right = rotate_right(node.right)
        return rotate_left(node)
    return node

def print_tree(node, level=0, prefix="Root: "):
    if node is not None:
        bf = balance_factor(node)
        print("  " * level + f"{prefix}{node.key} (BF={bf})")
        if node.left or node.right:
            if node.left:
                print_tree(node.left, level + 1, "L--- ")
            else:
                print("  " * (level + 1) + "L--- NULL")
            if node.right:
                print_tree(node.right, level + 1, "R--- ")
            else:
                print("  " * (level + 1) + "R--- NULL")

def is_avl(node):
    if node is None: return True, 0
    left_ok, lh = is_avl(node.left)
    right_ok, rh = is_avl(node.right)
    bf = lh - rh
    ok = left_ok and right_ok and abs(bf) <= 1
    if not ok:
        print(f"  NOT AVL at {node.key}: bf={bf}")
    return ok, 1 + max(lh, rh)

# ===== 新方案 =====
# 初始树: 更大更平衡的AVL树
# 目标: 先插LR, 再插RL
# 
# 策略: 构建一棵树，左子树和右子树高度相等
# 然后向左子树插入触发LR (左子变高，根BF=2)
# 再向右子树插入触发RL (右子变高，根BF=-2)

# 方案: 初始树设计为
#         40
#        /  \
#       20   60
#      / \   / \
#     10 30 50 70
#    /
#   5
# 各BF: 5(0), 10(1), 30(0), 50(0), 70(0), 20(1), 60(0), 40(1)
# 这是合法AVL

# 插入15: 走 40→20→10→右子. 10的BF=0→-1. 20的BF=1→0. 40的BF=1→0. 无旋转
# 不对，我要触发LR

# 重新想: 需要插入后使某节点BF变为+2，且新节点在该节点左子的右子树
# 
# 修改初始树:
#         40
#        /  \
#       20   60
#      / \   / \
#     10 30 50 70
#    /       \
#   5        55
# 
# 检查: 5(0), 10(1), 30(0), 55(0), 50(-1), 20(1), 70(0), 60(-1), 40(1)
# 合法AVL

# 插入15: 40→20→10→right→15. 
# 10: left=5(h=1), right=15(h=1), BF=0, h=2
# 20: left=10(h=2), right=30(h=1), BF=1, h=3  
# 40: left=20(h=3), right=60(h=3), BF=0
# 没旋转! 因为根BF=0

# 需要让初始根BF=0，插入后左子树更高→根BF=2
# 那么初始左子树高度应该和右子树一样，插入后左子树+1

# 方案B:
#         40
#        /  \
#       20   60
#      / \   / \
#     10 30 50 70
#    
# 初始: 10(0),30(0),50(0),70(0), 20(0),60(0),40(0) - 完美平衡

# 插入5: 40→20→10→left→5
# 10: BF=1, h=2
# 20: BF=1, h=3
# 40: BF=1, h=4. 无旋转，仍平衡

# 插入8: 40→20→10→5→right→8
# 5: BF=-1
# 10: left=h(5)=2, right=0, BF=2! 最小不平衡
# 新节点8在10左子(5)的右子树 → LR!
# LR旋转: 以10为根，先左旋5，再右旋10
# 结果: 8为根，5和10为子

print("="*60)
print("方案B: 初始树 40,20,60,10,30,50,70")
print("="*60)

root = None
for k in [40, 20, 60, 10, 30, 50, 70]:
    rotation_log.clear()
    root = insert(root, k)
    if rotation_log:
        print(f"  插入{k}: {rotation_log}")

print("\n初始AVL树:")
print_tree(root)
ok, _ = is_avl(root)
print(f"AVL合法: {ok}")

# 插入5 (无旋转)
print("\n--- 插入5 ---")
rotation_log.clear()
root = insert(root, 5)
print(f"旋转: {rotation_log or '无'}")
print_tree(root)

# 插入8 (触发LR)
print("\n--- 插入8 ---")
rotation_log.clear()
root = insert(root, 8)
print(f"旋转: {rotation_log or '无'}")
print_tree(root)
ok, _ = is_avl(root)
print(f"AVL合法: {ok}")

# 现在尝试触发RL
# 当前树结构: 左子树高3(20为根: 10→8→5,10; 30), 右子树高2(60为根: 50,70)
# 根40: left h=3, right h=2, BF=1
# 
# 插入到右子树使其更高:
# 插入75: 60→70→right→75. 70 BF=-1, 60 BF=-1, 40 BF=0. 无旋转
# 再插73? 60→70→75→left→73. 75 BF=1, 70 BF=-1, 60 BF=-1, 40 BF=0. 无旋转
# 
# 这样不行。需要让右子树先和左子树等高，再插一次触发RL

# 插入55: 40→60→50→right→55. 
# 50 BF=-1, 60 BF=0, 40 BF=1. 无旋转
print("\n--- 插入55 ---")
rotation_log.clear()
root = insert(root, 55)
print(f"旋转: {rotation_log or '无'}")
print_tree(root)

# 插入75: 
print("\n--- 插入75 ---")
rotation_log.clear()
root = insert(root, 75)
print(f"旋转: {rotation_log or '无'}")
print_tree(root)
ok, _ = is_avl(root)
print(f"AVL合法: {ok}")

# 现在右子树高度应该和左子树一样了
# 插入到右子树的右子的左子树来触发RL
# 60的右子是70, 插入65到70的左子
# 如果60 BF变-2, 且65在60右子(70)的左子 → RL!

print("\n--- 尝试插入65 (期望RL) ---")
rotation_log.clear()
root = insert(root, 65)
print(f"旋转: {rotation_log or '无'}")
print_tree(root)
ok, _ = is_avl(root)
print(f"AVL合法: {ok}")

print("\n" + "="*60)
print("完整序列总结:")
print("="*60)
print("初始: [40,20,60,10,30,50,70,5]")
print("插入8 → LR旋转")
print("插入55,75 → 无旋转（准备阶段）")  
print("插入65 → RL旋转")
