class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1
    
    def __repr__(self):
        return f"Node({self.key})"

def get_height(node):
    if not node:
        return 0
    return node.height

def get_bf(node):
    if not node:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(z):
    """右旋（LL旋转）"""
    y = z.left
    T3 = y.right
    y.right = z
    z.left = T3
    update_height(z)
    update_height(y)
    return y

def left_rotate(z):
    """左旋（RR旋转）"""
    y = z.right
    T2 = y.left
    y.left = z
    z.right = T2
    update_height(z)
    update_height(y)
    return y

def insert(node, key):
    if not node:
        return Node(key)
    if key < node.key:
        node.left = insert(node.left, key)
    else:
        node.right = insert(node.right, key)
    
    update_height(node)
    bf = get_bf(node)
    
    # LL
    if bf > 1 and key < node.left.key:
        return right_rotate(node)
    # RR
    if bf < -1 and key > node.right.key:
        return left_rotate(node)
    # LR
    if bf > 1 and key > node.left.key:
        node.left = left_rotate(node.left)
        return right_rotate(node)
    # RL
    if bf < -1 and key < node.right.key:
        node.right = right_rotate(node.right)
        return left_rotate(node)
    
    return node

def find_imbalance(node, inserted_key):
    """从插入点回溯找到失衡节点"""
    if not node:
        return None, 0
    if node.key == inserted_key:
        return None, 0
    
    if inserted_key < node.key:
        child = node.left
    else:
        child = node.right
    
    if not child:
        return None, 0
    
    imbalance_node, bf = find_imbalance(child, inserted_key)
    if imbalance_node:
        return imbalance_node, bf
    
    update_height(node)
    bf = get_bf(node)
    if abs(bf) > 1:
        return node, bf
    
    return None, 0

def print_tree(node, prefix="", is_left=True):
    if node:
        print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
        if node.key != 0:
            print(prefix + ("└── " if is_left else "┌── ") + str(node.key))
        print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

def tree_to_ascii(node, level=0, pos="root"):
    """生成树形图"""
    lines = []
    if not node:
        return lines
    # 递归获取子树
    left_lines = tree_to_ascii(node.left, level + 1, "left")
    right_lines = tree_to_ascii(node.right, level + 1, "right")
    
    # 当前节点
    indent = "  " * level
    line = f"{indent}{node.key}"
    
    # 合并
    max_len = max(len(l) for l in left_lines + right_lines + [line]) if left_lines or right_lines else len(line)
    
    if not left_lines and not right_lines:
        return [line]
    
    # 简单方式：返回层级信息
    return [(node.key, level)] + left_lines + right_lines

def check_balance(node):
    """检查树是否平衡"""
    if not node:
        return True
    bf = get_bf(node)
    if abs(bf) > 1:
        return False
    return check_balance(node.left) and check_balance(node.right)

def get_all_bf(node):
    """获取所有节点的BF"""
    result = {}
    if not node:
        return result
    result[node.key] = get_bf(node)
    result.update(get_all_bf(node.left))
    result.update(get_all_bf(node.right))
    return result

def get_all_height(node):
    """获取所有节点的高度"""
    result = {}
    if not node:
        return result
    result[node.key] = get_height(node)
    result.update(get_all_height(node.left))
    result.update(get_all_height(node.right))
    return result

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

# ==================== 验证 ====================
print("=" * 60)
print("Step 0: 构建初始树")
print("=" * 60)

# 手动构建初始树
root = Node(20)
root.left = Node(10)
root.right = Node(30)
root.left.left = Node(5)
root.right.left = Node(25)
root.right.right = Node(35)

# 更新高度
for node in [root.left.left, root.right.left, root.right.right, root.left, root.right, root]:
    update_height(node)

print(f"初始树中序遍历: {inorder(root)}")
print(f"初始树平衡: {check_balance(root)}")
print(f"初始树各节点BF: {get_all_bf(root)}")
print(f"初始树各节点H: {get_all_height(root)}")

# ==================== 子问题(1): 插入1 ====================
print("\n" + "=" * 60)
print("Step 1: 插入关键字1")
print("=" * 60)

# 先手动插入1（不旋转）来检查失衡
root_temp = Node(20)
root_temp.left = Node(10)
root_temp.right = Node(30)
root_temp.left.left = Node(5)
root_temp.right.left = Node(25)
root_temp.right.right = Node(35)
for node in [root_temp.left.left, root_temp.right.left, root_temp.right.right, root_temp.left, root_temp.right, root_temp]:
    update_height(node)

# 插入1
root_temp.left.left.left = Node(1)
update_height(root_temp.left.left)
update_height(root_temp.left)
update_height(root_temp)

print(f"插入1后（未旋转）各节点BF: {get_all_bf(root_temp)}")
print(f"插入1后（未旋转）各节点H: {get_all_height(root_temp)}")

# 找到失衡节点
imbalance_node, imbalance_bf = find_imbalance(root_temp, 1)
print(f"失衡节点: {imbalance_node.key if imbalance_node else 'None'}")
print(f"失衡节点BF: {imbalance_bf}")

# 判定旋转类型
if imbalance_node:
    child = imbalance_node.left if 1 < imbalance_node.key else imbalance_node.right
    if child and 1 < child.key:
        print("旋转类型: LL")
    elif child and 1 > child.key:
        print("旋转类型: LR")

# 执行LL旋转
# 失衡节点是10，右旋
# 10的左孩子是5，5成为新根，10成为5的右孩子
root_after_ll = root  # 从原始root开始
root_after_ll.left = right_rotate(root_after_ll.left)  # 对节点10右旋

print(f"\nLL旋转后各节点BF: {get_all_bf(root_after_ll)}")
print(f"LL旋转后各节点H: {get_all_height(root_after_ll)}")
print(f"LL旋转后树平衡: {check_balance(root_after_ll)}")
print(f"LL旋转后中序遍历: {inorder(root_after_ll)}")

# 验证树结构
print(f"\nLL旋转后树结构:")
print(f"  根: {root_after_ll.key}")
print(f"  左子: {root_after_ll.left.key}, 右子: {root_after_ll.right.key}")
print(f"  左子(5)的左: {root_after_ll.left.left.key}, 右: {root_after_ll.left.right.key}")
print(f"  右子(30)的左: {root_after_ll.right.left.key}, 右: {root_after_ll.right.right.key}")

# ==================== 子问题(3): 插入2, 40, 45 ====================
print("\n" + "=" * 60)
print("Step 2: 插入2")
print("=" * 60)

root_after_2 = insert(root_after_ll, 2)
print(f"插入2后各节点BF: {get_all_bf(root_after_2)}")
print(f"插入2后各节点H: {get_all_height(root_after_2)}")
print(f"插入2后树平衡: {check_balance(root_after_2)}")
print(f"插入2后中序遍历: {inorder(root_after_2)}")

print("\n" + "=" * 60)
print("Step 3: 插入40")
print("=" * 60)

root_after_40 = insert(root_after_2, 40)
print(f"插入40后各节点BF: {get_all_bf(root_after_40)}")
print(f"插入40后各节点H: {get_all_height(root_after_40)}")
print(f"插入40后树平衡: {check_balance(root_after_40)}")
print(f"插入40后中序遍历: {inorder(root_after_40)}")

print("\n" + "=" * 60)
print("Step 4: 插入45")
print("=" * 60)

# 先手动插入45（不旋转）来检查失衡
# 复制树结构
def copy_tree(node):
    if not node:
        return None
    new_node = Node(node.key)
    new_node.left = copy_tree(node.left)
    new_node.right = copy_tree(node.right)
    new_node.height = node.height
    return new_node

root_temp_45 = copy_tree(root_after_40)
# 手动插入45
root_temp_45.right.right.right.right = Node(45)
update_height(root_temp_45.right.right.right.right)
update_height(root_temp_45.right.right.right)
update_height(root_temp_45.right.right)
update_height(root_temp_45.right)
update_height(root_temp_45)

print(f"插入45后（未旋转）各节点BF: {get_all_bf(root_temp_45)}")
print(f"插入45后（未旋转）各节点H: {get_all_height(root_temp_45)}")

# 找到失衡节点
imbalance_node_45, imbalance_bf_45 = find_imbalance(root_temp_45, 45)
print(f"失衡节点: {imbalance_node_45.key if imbalance_node_45 else 'None'}")
print(f"失衡节点BF: {imbalance_bf_45}")

# 判定旋转类型
if imbalance_node_45:
    child = imbalance_node_45.right if 45 > imbalance_node_45.key else imbalance_node_45.left
    if child and 45 > child.key:
        print("旋转类型: RR")
    elif child and 45 < child.key:
        print("旋转类型: RL")

# 执行完整插入（含旋转）
root_final = insert(root_after_40, 45)
print(f"\nRR旋转后各节点BF: {get_all_bf(root_final)}")
print(f"RR旋转后各节点H: {get_all_height(root_final)}")
print(f"RR旋转后树平衡: {check_balance(root_final)}")
print(f"RR旋转后中序遍历: {inorder(root_final)}")

# 验证最终树结构
print(f"\n最终树结构:")
print(f"  根: {root_final.key}")
print(f"  左子: {root_final.left.key}, 右子: {root_final.right.key}")
print(f"  左子({root_final.left.key})的左: {root_final.left.left.key}, 右: {root_final.left.right.key}")
print(f"  右子({root_final.right.key})的左: {root_final.right.left.key}, 右: {root_final.right.right.key}")
if root_final.right.right:
    print(f"  右子右子({root_final.right.right.key})的左: {root_final.right.right.left.key if root_final.right.right.left else 'None'}, 右: {root_final.right.right.right.key if root_final.right.right.right else 'None'}")

# ==================== 对比solution.md中的答案 ====================
print("\n" + "=" * 60)
print("对比验证")
print("=" * 60)

# Solution说插入2后：节点1的BF=-1, H=2; 节点2的BF=0, H=1; 节点5的BF=1, H=3
# 但solution的树形图显示2是10的左孩子
# 让我检查：在LL旋转后的树中，2应该插入到哪里？
# LL旋转后树：
#         20
#        /  \
#       5    30
#      / \   / \
#     1  10 25  35
# 2 < 20 → 左, 2 > 5 → 右, 2 < 10 → 左
# 所以2作为10的左孩子插入 ✓

# 但代码中insert函数会自动旋转，让我检查插入2后是否触发了旋转
print(f"插入2后是否触发旋转: {root_after_2 is not root_after_ll}")
print(f"插入2后根节点: {root_after_2.key}")
print(f"插入2后左子: {root_after_2.left.key}")
print(f"插入2后左子的右子: {root_after_2.left.right.key}")
print(f"插入2后左子的右子的左子: {root_after_2.left.right.left.key if root_after_2.left.right.left else 'None'}")

# 检查solution中插入2后的BF
# solution说: 节点1: BF=0, H=1; 节点10: BF=1, H=2; 节点5: BF=-1, H=3
# 但代码显示: 节点1: BF=-1, H=2; 节点2: BF=0, H=1; 节点5: BF=1, H=3
# 差异：solution中2是10的左孩子，1没有孩子
# 代码中2是1的右孩子？让我检查

print(f"\n插入2后树结构详细:")
print(f"  根(20)的左子: {root_after_2.left.key}")
print(f"  5的左子: {root_after_2.left.left.key}")
print(f"  5的右子: {root_after_2.left.right.key}")
print(f"  1的左子: {root_after_2.left.left.left}")
print(f"  1的右子: {root_after_2.left.left.right.key if root_after_2.left.left.right else 'None'}")
print(f"  10的左子: {root_after_2.left.right.left.key if root_after_2.left.right.left else 'None'}")
print(f"  10的右子: {root_after_2.left.right.right}")

# 关键问题：2应该插入到哪里？
# 在BST中，2 > 1，所以2应该在1的右子树
# 但solution说2是10的左孩子
# 让我重新检查：LL旋转后的树中，1是5的左孩子，10是5的右孩子
# 2 < 20 → 左(到5), 2 > 5 → 右(到10), 2 < 10 → 左(到10的左子树)
# 10的左子树为空，所以2作为10的左孩子插入
# 但等等，BST插入是从根开始比较：
# 2 < 20 → 左(到5)
# 2 > 5 → 右(到10)  
# 2 < 10 → 左(到10的左子树，为空)
# 所以2作为10的左孩子插入 ✓

# 但我的代码中insert函数是从根递归插入的，让我检查代码逻辑
# insert(root_after_ll, 2):
# 2 < 20 → insert(root_after_ll.left, 2)  # root_after_ll.left 是 5
# 2 > 5 → insert(5.right, 2)  # 5.right 是 10
# 2 < 10 → insert(10.left, 2)  # 10.left 是 None
# 返回 Node(2)
# 所以 10.left = Node(2) ✓

# 那为什么代码输出显示 1的右子是2？
# 让我重新检查...

# 实际上，让我打印更详细的结构
def print_structure(node, indent=0):
    if not node:
        return
    prefix = "  " * indent
    left_key = node.left.key if node.left else None
    right_key = node.right.key if node.right else None
    print(f"{prefix}Node({node.key}): left={left_key}, right={right_key}, H={node.height}, BF={get_bf(node)}")
    print_structure(node.left, indent + 1)
    print_structure(node.right, indent + 1)

print("\n插入2后的详细结构:")
print_structure(root_after_2)

print("\n插入40后的详细结构:")
print_structure(root_after_40)

print("\n插入45后的详细结构:")
print_structure(root_final)
