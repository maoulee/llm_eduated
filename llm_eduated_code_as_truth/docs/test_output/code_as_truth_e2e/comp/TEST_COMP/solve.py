"""
AVL 树插入模拟 —— solve.py
序列: 30, 15, 38, 7, 20, 25, 22, 5
平衡因子 = 左子树高度 - 右子树高度
"""

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
    if node is None:
        return 0
    return height(node.left) - height(node.right)

def print_tree(node, indent="", last=True):
    """打印树结构"""
    if node is not None:
        branch = "└── " if last else "├── "
        print(f"{indent}{branch}{node.key} (BF={bf(node)})")
        new_indent = indent + ("    " if last else "│   ")
        children = []
        if node.left:
            children.append((node.left, True))
        if node.right:
            children.append((node.right, False))
        for i, (child, is_left) in enumerate(children):
            is_last = (i == len(children) - 1)
            print_tree(child, new_indent, is_last)

def tree_to_dict(node):
    """返回每个节点的左右子节点"""
    if node is None:
        return {}
    result = {node.key: (node.left.key if node.left else None,
                          node.right.key if node.right else None)}
    result.update(tree_to_dict(node.left))
    result.update(tree_to_dict(node.right))
    return result

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

def insert(node, key, rotation_log):
    """插入并记录旋转信息"""
    if node is None:
        return Node(key), None

    if key < node.key:
        node.left, _ = insert(node.left, key, rotation_log)
    elif key > node.key:
        node.right, _ = insert(node.right, key, rotation_log)
    else:
        return node, None

    balance = bf(node)

    rotation_type = None
    new_root = node

    # LL
    if balance > 1 and key < node.left.key:
        rotation_type = "LL"
        new_root = right_rotate(node)
    # RR
    elif balance < -1 and key > node.right.key:
        rotation_type = "RR"
        new_root = left_rotate(node)
    # LR
    elif balance > 1 and key > node.left.key:
        rotation_type = "LR"
        node.left = left_rotate(node.left)
        new_root = right_rotate(node)
    # RL
    elif balance < -1 and key < node.right.key:
        rotation_type = "RL"
        node.right = right_rotate(node.right)
        new_root = left_rotate(node)

    return new_root, rotation_type

def insert_step(root, key, rotation_log):
    """单步插入，记录旋转信息"""
    root, rot = insert(root, key, rotation_log)
    if rot:
        rotation_log.append((key, rot))
    return root

# ========== 主逻辑 ==========

print("=" * 60)
print("AVL 树插入模拟")
print("序列: 30, 15, 38, 7, 20, 25, 22, 5")
print("平衡因子 = 左子树高度 - 右子树高度")
print("=" * 60)

# ---- 第一阶段: 插入 30, 15, 38, 7, 20 ----
print("\n【阶段1】插入 30, 15, 38, 7, 20")
root = None
for k in [30, 15, 38, 7, 20]:
    root, rot = insert(root, k, [])
    if rot:
        print(f"  插入 {k}: 发生旋转 {rot}")
    else:
        print(f"  插入 {k}: 无旋转")

print("\n  树结构:")
print_tree(root)

# 检查所有节点 BF
print("\n  各节点平衡因子:")
d = tree_to_dict(root)
for node_key in sorted(d.keys()):
    # 计算每个节点的BF
    pass

# 手动计算各节点BF
def print_all_bf(node, prefix="  "):
    if node:
        print(f"{prefix}节点 {node.key}: BF = {bf(node)}, "
              f"左子={node.left.key if node.left else 'None'}, "
              f"右子={node.right.key if node.right else 'None'}")
        print_all_bf(node.left, prefix + "  ")
        print_all_bf(node.right, prefix + "  ")

print_all_bf(root)

# ---- 插入 25 ----
print("\n" + "=" * 60)
print("【(1)问题】插入关键字 25")
print("=" * 60)

# 先看插入25之前的树
print("\n  插入25之前的树结构:")
print_tree(root)

# 手动插入25（BST方式，不做平衡）来看会发生什么
print("\n  BST插入路径: 30→15→20→25 (作为20的右子)")

# 记录插入前的BF
print("\n  插入25前各节点BF:")
print_all_bf(root)

# 执行AVL插入
log = []
root, rot = insert(root, 25, log)
if log:
    print(f"\n  插入25后: 发生旋转 {log[-1][1]}")
else:
    print(f"\n  插入25后: 无旋转")

print("\n  插入25并平衡后的树结构:")
print_tree(root)
print("\n  平衡后各节点BF:")
print_all_bf(root)

# 手动分析插入25的失衡情况
print("\n--- (1) 分析 ---")
print("插入25前的树（插入30,15,38,7,20后）:")
print("        30")
print("       /  \\")
print("      15   38")
print("     /  \\")
print("    7   20")
print()
print("BST插入25: 25>20, 作为20的右子节点")
print()
print("插入后(平衡前)的树:")
print("        30")
print("       /  \\")
print("      15   38")
print("     /  \\")
print("    7   20")
print("         \\")
print("         25")
print()

# 计算失衡
print("从底向上检查平衡因子:")
print("  节点7:  BF=0 (叶子)")
print("  节点20: BF=左(0)-右(1)=-1, |BF|<=1, 平衡")
print("  节点15: BF=左高(1)-右高(2)=-1, |BF|<=1, 平衡")
print("  节点38: BF=0 (叶子)")
print("  节点30: BF=左子树高(3)-右子树高(1)=2, |BF|=2>1, 失衡!")
print()
print("【答案(1)】")
print("  最小不平衡子树的根节点: 30")
print("  节点30的平衡因子: 2")
print("  失衡类型: 节点30的BF=2(左重), 新节点25插入在30的左子(15)的右子树中")
print("  旋转类型: LR旋转（双旋）")

# ---- (2) 旋转后的树结构 ----
print("\n--- (2) 分析 ---")
print("执行LR旋转(以30为失衡节点):")
print("  第一步: 对30的左子15执行左旋(围绕20)")
print("    旋转前:           旋转后:")
print("       15               20")
print("      /  \\             /  \\")
print("     7   20    →     15   25")
print("          \\          /")
print("          25         7")
print()
print("  第二步: 对30执行右旋(围绕20)")
print("    旋转前:           旋转后:")
print("       30               20")
print("      /  \\             /  \\")
print("     20   38    →     15   30")
print("    /  \\              /   /  \\")
print("   15   25            7   25   38")
print("   /")
print("  7")
print()
print("  旋转后的树结构:")
print("        20")
print("       /  \\")
print("      15   30")
print("     /    /  \\")
print("    7    25   38")

# 验证根节点BF
root_after_rot = Node(20)
root_after_rot.left = Node(15)
root_after_rot.left.left = Node(7)
root_after_rot.right = Node(30)
root_after_rot.right.left = Node(25)
root_after_rot.right.right = Node(38)

print(f"\n  旋转后根节点(20)的平衡因子: BF={bf(root_after_rot)}")
print(f"  (左子树高={height(root_after_rot.left)}, 右子树高={height(root_after_rot.right)})")

print("\n【答案(2)】")
print("  旋转后树结构如上")
print(f"  根节点(20)的平衡因子: {bf(root_after_rot)}")

# ---- (3) 插入22和5 ----
print("\n" + "=" * 60)
print("【(3)问题】在(2)基础上继续插入22和5")
print("=" * 60)

# 当前树: root已经是AVL插入25后的结果
print("\n  当前树结构(即(2)的结果):")
print_tree(root)

# 插入22
print("\n--- 插入22 ---")
log22 = []
root, rot22 = insert(root, 22, log22)
if log22:
    print(f"  插入22后: 发生旋转 {log22[-1][1]}")
else:
    print(f"  插入22后: 无旋转")

print("\n  BST插入路径: 20→30→25→22 (作为25的左子)")
print("\n  插入22后的树结构:")
print_tree(root)
print("\n  各节点BF:")
print_all_bf(root)

# 分析
print("\n  分析插入22:")
print("  树结构:")
print("        20")
print("       /  \\")
print("      15   30")
print("     /    /  \\")
print("    7    25   38")
print("        /")
print("       22")
print()
print("  各节点BF:")
print("    节点22: BF=0")
print("    节点25: BF=左(1)-右(0)=1, 平衡")
print("    节点7:  BF=0")
print("    节点15: BF=左(1)-右(0)=1, 平衡")
print("    节点38: BF=0")
print("    节点30: BF=左(25子树高=2)-右(38高=1)=1, 平衡")
print("    节点20: BF=左(15子树高=2)-右(30子树高=3)=-1, 平衡")
print()
print("  【结论】插入22后，所有节点|BF|<=1，树仍保持平衡，无需旋转。")

# 插入5
print("\n--- 插入5 ---")
log5 = []
root, rot5 = insert(root, 5, log5)
if log5:
    print(f"  插入5后: 发生旋转 {log5[-1][1]}")
else:
    print(f"  插入5后: 无旋转")

print("\n  BST插入路径: 20→15→7→5 (作为7的左子)")
print("\n  插入5后(平衡前)的树:")
print("        20")
print("       /  \\")
print("      15   30")
print("     /    /  \\")
print("    7    25   38")
print("   /    /")
print("  5    22")
print()
print("  从底向上检查BF:")
print("    节点5:  BF=0")
print("    节点7:  BF=左(1)-右(0)=1, 平衡")
print("    节点22: BF=0")
print("    节点25: BF=左(1)-右(0)=1, 平衡")
print("    节点15: BF=左(7子树高=2)-右(0)=2, |BF|=2>1, 失衡!")
print()
print("  最小不平衡子树根节点: 15")
print("  节点15的BF=2(左重)")
print("  新节点5插入在15的左子(7)的左子树中 → LL型(单旋)")
print()

if log5:
    print(f"  执行旋转: {log5[-1][1]}")
    print(f"\n  旋转后的树结构:")
    print_tree(root)
    print("\n  各节点BF:")
    print_all_bf(root)

print("\n  手动验证LL旋转(对15执行右旋):")
print("    旋转前:       旋转后:")
print("       15           7")
print("      /            / \\")
print("     7      →     5   15")
print("    /")
print("   5")
print()
print("  旋转后的完整树结构:")
print("        20")
print("       /  \\")
print("      7    30")
print("     / \\   /  \\")
print("    5  15 25   38")
print("       /")
print("      22")

# 验证
print("\n  验证旋转后各节点BF:")
# 构建旋转后的树验证
root_final = Node(20)
root_final.left = Node(7)
root_final.left.left = Node(5)
root_final.left.right = Node(15)
root_final.left.right.left = Node(22)
root_final.right = Node(30)
root_final.right.left = Node(25)
root_final.right.right = Node(38)
print_all_bf(root_final)

print(f"\n  全树高度: {height(root_final)}")

# ---- (4) 最终树 ----
print("\n" + "=" * 60)
print("【(4)问题】最终树汇总")
print("=" * 60)
print(f"\n  最终树结构:")
print_tree(root)

print("\n【答案(4)】")
root_key = root.key
left_key = root.left.key if root.left else None
right_key = root.right.key if root.right else None
print(f"  根节点关键字: {root_key}")
print(f"  根的左子节点关键字: {left_key}")
print(f"  根的右子节点关键字: {right_key}")

print("\n" + "=" * 60)
print("完整答案汇总")
print("=" * 60)
print("""
(1) 最小不平衡子树根节点: 30
    平衡因子: 2
    旋转类型: LR旋转(双旋)

(2) 旋转后树结构:
        20
       /  \\
      15   30
     /    /  \\
    7    25   38
    根节点(20)的平衡因子: 0

(3) 插入22后: 树仍保持平衡，无失衡，无需旋转。
    插入5后: 最小不平衡子树根节点为15，BF=2，LL旋转(单旋)。
    旋转后树结构:
        20
       /  \\
      7    30
     / \\   /  \\
    5  15 25   38
       /
      22

(4) 根节点关键字: 20
    左子节点关键字: 7
    右子节点关键字: 30
""")
