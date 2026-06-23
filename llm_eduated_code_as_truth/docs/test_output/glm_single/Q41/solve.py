# ===== AVL树插入与平衡调整模拟 =====
# 本题需要模拟AVL树的插入和旋转操作，属于数据结构题
# 使用代码验证手动推导的结果

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 0

def get_height(node):
    if node is None:
        return 0
    return node.height

def get_bf(node):
    if node is None:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    if node is not None:
        node.height = max(get_height(node.left), get_height(node.right)) + 1

def print_tree(node, indent="", prefix=""):
    if node is not None:
        print(f"{indent}{prefix}{node.key} (h={node.height}, BF={get_bf(node)})")
        if node.left or node.right:
            if node.left:
                print_tree(node.left, indent + "    ", "L:")
            if node.right:
                print_tree(node.right, indent + "    ", "R:")

def insert_bst(node, key):
    """普通BST插入，不旋转，用于插入后观察失衡"""
    if node is None:
        return Node(key)
    if key < node.key:
        node.left = insert_bst(node.left, key)
    else:
        node.right = insert_bst(node.right, key)
    update_height(node)
    return node

def find_min_unbalanced(node):
    """后序遍历找到最小不平衡子树（从插入点回溯第一个失衡节点）"""
    # 这里简化：遍历所有节点，找到最深（高度最大）的失衡节点
    result = [None]
    def dfs(n):
        if n is None:
            return
        dfs(n.left)
        dfs(n.right)
        update_height(n)
        bf = get_bf(n)
        if abs(bf) > 1 and result[0] is None:
            result[0] = n
    dfs(node)
    return result[0]

def left_rotate(z):
    y = z.right
    T2 = y.left
    y.left = z
    z.right = T2
    update_height(z)
    update_height(y)
    return y

def right_rotate(z):
    y = z.left
    T3 = y.right
    y.right = z
    z.left = T3
    update_height(z)
    update_height(y)
    return y

# ===== 初始AVL树构建 =====
#         50
#        /  \
#       30   60
#      /  \
#     20  40
root = Node(50)
root.left = Node(30)
root.right = Node(60)
root.left.left = Node(20)
root.left.right = Node(40)

# 更新所有高度
def update_all_heights(node):
    if node is None:
        return
    update_all_heights(node.left)
    update_all_heights(node.right)
    update_height(node)

update_all_heights(root)

print("===== 初始AVL树 =====")
print_tree(root)

# ===== 子问题(1): 插入35（旋转前） =====
print("\n===== 子问题(1): 插入35（旋转前）=====")
root = insert_bst(root, 35)
update_all_heights(root)
print_tree(root)

# 找最小不平衡子树
unbalanced = find_min_unbalanced(root)
if unbalanced:
    print(f"\n最小不平衡子树根节点: {unbalanced.key}")
    print(f"  其平衡因子 BF = {get_bf(unbalanced)}")
    if unbalanced.left:
        print(f"  其左孩子: {unbalanced.left.key}, BF = {get_bf(unbalanced.left)}")
    if unbalanced.right:
        print(f"  其右孩子: {unbalanced.right.key}, BF = {get_bf(unbalanced.right)}")
    
    bf_root = get_bf(unbalanced)
    if bf_root > 1:
        # 左子树重
        bf_left = get_bf(unbalanced.left)
        if bf_left >= 1:
            print(f"  平衡调整类型: LL")
        else:
            print(f"  平衡调整类型: LR")
    elif bf_root < -1:
        # 右子树重
        bf_right = get_bf(unbalanced.right)
        if bf_right <= -1:
            print(f"  平衡调整类型: RR")
        else:
            print(f"  平衡调整类型: RL")

# ===== 子问题(2): 执行LR平衡调整 =====
print("\n===== 子问题(2): 执行LR平衡调整 =====")

# LR = 先以30为轴左旋，再以50为轴右旋
# 先重建树（旋转前状态）
root2 = Node(50)
root2.left = Node(30)
root2.right = Node(60)
root2.left.left = Node(20)
root2.left.right = Node(40)
root2.left.right.left = Node(35)
update_all_heights(root2)

print("旋转前树结构:")
print_tree(root2)

# LR旋转步骤1: 以30为轴左旋
print("\nLR步骤1: 以30为轴左旋")
# 30是50的左孩子
node_30 = root2.left  # 30
node_40 = node_30.right  # 40
child_35 = node_40.left  # 35

# 左旋30: 40上去，30下来，35变30的右孩子
node_30.right = child_35  # 30的右孩子变成35
node_40.left = node_30    # 40的左孩子变成30
root2.left = node_40      # 50的左孩子变成40
update_all_heights(root2)

print("第一次旋转后:")
print_tree(root2)

# LR旋转步骤2: 以50为轴右旋
print("\nLR步骤2: 以50为轴右旋")
node_40 = root2.left  # 40 (现在是50的左孩子)
node_50 = root2       # 50
child_right_of_40 = node_40.right  # 40的右孩子(null)

# 右旋50: 40上去，50下来，40的右孩子变50的左孩子
node_40.right = node_50
node_50.left = child_right_of_40
root2 = node_40
update_all_heights(root2)

print("第二次旋转后（最终AVL树）:")
print_tree(root2)

# 验证所有节点平衡因子
def check_all_balanced(node, results):
    if node is None:
        return
    check_all_balanced(node.left, results)
    check_all_balanced(node.right, results)
    bf = get_bf(node)
    results.append((node.key, bf, node.height))

results = []
check_all_balanced(root2, results)
print("\n各节点平衡因子检查:")
all_ok = True
for key, bf, h in results:
    status = "OK" if abs(bf) <= 1 else "UNBALANCED"
    if abs(bf) > 1:
        all_ok = False
    print(f"  节点{key}: 高度={h}, BF={bf}, {status}")
print(f"  整体平衡: {'是' if all_ok else '否'}")

# ===== 子问题(3): 插入55 =====
print("\n===== 子问题(3): 插入55 =====")
root3 = root2  # 在子问题(2)的基础上
root3 = insert_bst(root3, 55)
update_all_heights(root3)

print("插入55后（旋转前）:")
print_tree(root3)

# 检查是否失衡
unbalanced3 = find_min_unbalanced(root3)
if unbalanced3:
    print(f"\n最小不平衡子树根节点: {unbalanced3.key}")
    print(f"  其平衡因子 BF = {get_bf(unbalanced3)}")
    if unbalanced3.left:
        print(f"  其左孩子: {unbalanced3.left.key}, BF = {get_bf(unbalanced3.left)}")
    if unbalanced3.right:
        print(f"  其右孩子: {unbalanced3.right.key}, BF = {get_bf(unbalanced3.right)}")
    
    bf_root = get_bf(unbalanced3)
    if bf_root > 1:
        bf_left = get_bf(unbalanced3.left)
        rot_type = "LL" if bf_left >= 1 else "LR"
    elif bf_root < -1:
        bf_right = get_bf(unbalanced3.right)
        rot_type = "RR" if bf_right <= -1 else "RL"
    print(f"  平衡调整类型: {rot_type}")
    
    # 执行RL旋转
    print(f"\n执行{rot_type}旋转:")
    
    if rot_type == "RL":
        # RL = 先以右孩子为轴右旋，再以根为轴左旋
        # 右孩子是60，根是50
        # 找到50节点
        def find_node(node, key):
            if node is None:
                return None
            if node.key == key:
                return node
            if key < node.key:
                return find_node(node.left, key)
            return find_node(node.right, key)
        
        # RL步骤1: 以60为轴右旋
        print("RL步骤1: 以60为轴右旋")
        node_50 = unbalanced3  # 50
        node_60 = node_50.right  # 60
        node_55 = node_60.left   # 55
        
        # 右旋60: 55上去，60下来，55的右孩子变60的左孩子
        node_60.left = node_55.right  # 55的右孩子(null)变60的左孩子
        node_55.right = node_60       # 60变55的右孩子
        node_50.right = node_55       # 50的右孩子变55
        update_all_heights(root3)
        
        print("第一次旋转后:")
        print_tree(root3)
        
        # RL步骤2: 以50为轴左旋
        print("\nRL步骤2: 以50为轴左旋")
        node_50_ref = find_node(root3, 50)
        # 50的父节点是40，50是40的右孩子
        node_55_ref = node_50_ref.right  # 55
        child_left_of_55 = node_55_ref.left  # 55的左孩子(null)
        
        # 左旋50: 55上去，50下来，55的左孩子变50的右孩子
        node_55_ref.left = node_50_ref      # 50变55的左孩子
        node_50_ref.right = child_left_of_55 # 55的原左孩子变50的右孩子
        
        # 需要更新40的右孩子指针
        # 找到50的父节点
        def find_parent(node, key, parent=None):
            if node is None:
                return None
            if node.key == key:
                return parent
            if key < node.key:
                return find_parent(node.left, key, node)
            return find_parent(node.right, key, node)
        
        parent_of_50 = find_parent(root3, 50)
        if parent_of_50:
            if parent_of_50.right and parent_of_50.right.key == 50:
                parent_of_50.right = node_55_ref
            elif parent_of_50.left and parent_of_50.left.key == 50:
                parent_of_50.left = node_55_ref
        
        update_all_heights(root3)
        
        print("第二次旋转后（最终AVL树）:")
        print_tree(root3)
        
        results3 = []
        check_all_balanced(root3, results3)
        print("\n各节点平衡因子检查:")
        all_ok3 = True
        for key, bf, h in results3:
            status = "OK" if abs(bf) <= 1 else "UNBALANCED"
            if abs(bf) > 1:
                all_ok3 = False
            print(f"  节点{key}: 高度={h}, BF={bf}, {status}")
        print(f"  整体平衡: {'是' if all_ok3 else '否'}")
else:
    print("插入55后未失衡，树仍为平衡AVL树。")

print("\n===== 最终答案汇总 =====")
print("子问题(1): 插入35后，最小不平衡子树根节点为50，BF(50)=2，BF(30)=-1，调整类型为LR")
print("子问题(2): LR旋转 - 先以30为轴左旋，再以50为轴右旋，结果根为40")
print("子问题(3): 插入55后失衡，最小不平衡子树根为50，类型RL，先以60为轴右旋，再以50为轴左旋")
