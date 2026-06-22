"""
独立验证AVL树插入序列的旋转过程和最终树结构。
"""

class AVLNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    if not node:
        return 0
    return node.height

def get_balance(node):
    if not node:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(z):
    """RR旋转的逆操作：右旋"""
    y = z.left
    T3 = y.right
    y.right = z
    z.left = T3
    update_height(z)
    update_height(y)
    return y

def left_rotate(z):
    """LL旋转的逆操作：左旋"""
    y = z.right
    T2 = y.left
    y.left = z
    z.right = T2
    update_height(z)
    update_height(y)
    return y

def insert(node, key, rotations_log, path=""):
    """插入节点并记录旋转"""
    # BST插入
    if not node:
        return AVLNode(key)
    
    if key < node.key:
        node.left = insert(node.left, key, rotations_log, path + "L")
    else:
        node.right = insert(node.right, key, rotations_log, path + "R")
    
    update_height(node)
    
    # 获取平衡因子
    balance = get_balance(node)
    
    # LL情况
    if balance > 1 and key < node.left.key:
        rotations_log.append((key, 'RR', node.key))  # LL型不平衡，需要右旋（RR旋转）
        return right_rotate(node)
    
    # RR情况
    if balance < -1 and key > node.right.key:
        rotations_log.append((key, 'LL', node.key))  # RR型不平衡，需要左旋（LL旋转）
        return left_rotate(node)
    
    # LR情况
    if balance > 1 and key > node.left.key:
        node.left = left_rotate(node.left)
        rotations_log.append((key, 'LR', node.key))
        return right_rotate(node)
    
    # RL情况
    if balance < -1 and key < node.right.key:
        node.right = right_rotate(node.right)
        rotations_log.append((key, 'RL', node.key))
        return left_rotate(node)
    
    return node

def count_leaves(node):
    if not node:
        return 0
    if not node.left and not node.right:
        return 1
    return count_leaves(node.left) + count_leaves(node.right)

def get_leaves(node, result=None):
    if not node:
        return result if result else []
    if not node.left and not node.right:
        result = result if result else []
        result.append(node.key)
        return result
    get_leaves(node.left, result)
    get_leaves(node.right, result)
    return result

def inorder(node, result=None):
    if not node:
        return result if result else []
    inorder(node.left, result)
    result = result if result else []
    result.append(node.key)
    inorder(node.right, result)
    return result

def tree_height(node):
    if not node:
        return 0
    return node.height

def print_tree(node, prefix="", is_left=True):
    if not node:
        return
    print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
    print(prefix + ("└── " if is_left else "┌── ") + str(node.key))
    print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

def check_balance(node):
    """检查树是否平衡"""
    if not node:
        return True
    balance = get_balance(node)
    if abs(balance) > 1:
        return False
    return check_balance(node.left) and check_balance(node.right)

# 主验证
sequence = [10, 20, 30, 5, 1, 2, 15, 12, 18, 25, 28, 22]
rotations_log = []
root = None

print("=" * 60)
print("AVL树插入序列验证")
print("=" * 60)
print(f"插入序列: {sequence}")
print()

for key in sequence:
    root = insert(root, key, rotations_log)

print("旋转记录:")
for key, rot_type, center in rotations_log:
    print(f"  插入 {key}: {rot_type}旋转，中心节点={center}")

print()
print("旋转类型集合:", set(r[1] for r in rotations_log))
print("是否包含全部四种:", set(r[1] for r in rotations_log) == {'LL', 'RR', 'LR', 'RL'})

print()
print("最终AVL树结构:")
print_tree(root)

print()
print(f"树的高度（根节点高度为1）: {tree_height(root)}")
print(f"叶子节点个数: {count_leaves(root)}")
print(f"叶子节点: {get_leaves(root)}")
print(f"中序遍历: {inorder(root)}")
print(f"树是否平衡: {check_balance(root)}")

# 验证solution中的答案
print()
print("=" * 60)
print("与solution.md答案对比")
print("=" * 60)

# 子问题(1)
print("\n(1) 插入30后的旋转:")
print(f"  代码结果: 插入30触发RR旋转，中心节点10")
print(f"  solution: RR旋转，中心节点10")
print(f"  匹配: {'✓' if rotations_log[0] == (30, 'RR', 10) else '✗'}")

# 子问题(2)
expected_rotations = [
    (30, 'RR', 10),
    (1, 'LL', 10),
    (2, 'LL', 20),
    (12, 'RL', 10),
    (18, 'LR', 20),
    (25, 'RR', 5),
    (28, 'LR', 30),
    (22, 'RL', 20),
]

print("\n(2) 完整旋转记录对比:")
all_match = True
for i, (exp, got) in enumerate(zip(expected_rotations, rotations_log)):
    match = exp == got
    if not match:
        all_match = False
    print(f"  {exp} vs {got} {'✓' if match else '✗ MISMATCH'}")

if len(expected_rotations) != len(rotations_log):
    print(f"  数量不匹配: 期望{len(expected_rotations)}次，实际{len(rotations_log)}次")
    all_match = False

print(f"  全部匹配: {'✓' if all_match else '✗'}")

# 子问题(3)
print("\n(3) 最终树属性:")
print(f"  高度: 期望4, 实际{tree_height(root)} {'✓' if tree_height(root) == 4 else '✗'}")
print(f"  叶子数: 期望5, 实际{count_leaves(root)} {'✓' if count_leaves(root) == 5 else '✗'}")
expected_inorder = [1, 2, 5, 10, 12, 15, 18, 20, 22, 25, 28, 30]
actual_inorder = inorder(root)
print(f"  中序遍历: 期望{expected_inorder}")
print(f"            实际{actual_inorder}")
print(f"            匹配: {'✓' if expected_inorder == actual_inorder else '✗'}")

# 额外检查：solution中插入25的推导有问题
print()
print("=" * 60)
print("solution.md中的问题检查")
print("=" * 60)
print("""
solution.md在插入25的推导中写道：
  '插入后：节点20的BF = 左高0 - 右高2 = -2，不平衡'
  '20的右孩子30的BF = 1（左子树高）→ RL型... 等等，需要重新检查'
  然后直接引用了代码结果。

这说明求解者在手动推导插入25时出现了错误，然后退回到代码结果。
这是一个求解质量问题，但不影响最终答案的正确性。
""")

# 检查solution中最终树结构的准确性
print("\n最终树结构详细验证:")
print("根据代码输出的树结构:")
print_tree(root)
print()
print("solution.md中的树结构:")
print("""
            15
           /  \\
          5    25
         / \\   / \\
        2  12 20  30
       /    \\   \\   \\
      1     10  18  28
              \\     /
              12   22  (此处需根据实际结构)
""")
print("注意：solution中的树结构有错误：")
print("1. 节点12出现了两次（一次在15的左子树，一次在10的右孩子位置）")
print("2. 标注了'(此处需根据实际结构)'，说明求解者不确定")
print("3. 28的孩子标注为22，但实际22是20的右孩子")
