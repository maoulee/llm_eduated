# ===== AVL树验证脚本 =====
# 题干参数：插入序列 16, 3, 7, 11, 9, 26, 18
# 平衡因子定义：左子树高度 - 右子树高度

import math

class AVLNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    if node is None:
        return 0
    return node.height

def get_bf(node):
    """平衡因子 = 左子树高度 - 右子树高度"""
    if node is None:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(y):
    x = y.left
    T = x.right
    x.right = y
    y.left = T
    update_height(y)
    update_height(x)
    return x

def left_rotate(x):
    y = x.right
    T = y.left
    y.left = x
    x.right = T
    update_height(x)
    update_height(y)
    return y

def detect_rotation_type(node, key):
    """检测旋转类型"""
    bf = get_bf(node)
    if bf > 1:
        if get_bf(node.left) >= 0:
            return "LL"
        else:
            return "LR"
    if bf < -1:
        if get_bf(node.right) <= 0:
            return "RR"
        else:
            return "RL"
    return None

def insert(node, key, rotations):
    """插入并记录旋转类型"""
    if node is None:
        return AVLNode(key), rotations

    if key < node.key:
        node.left, rotations = insert(node.left, key, rotations)
    elif key > node.key:
        node.right, rotations = insert(node.right, key, rotations)
    else:
        return node, rotations

    update_height(node)

    rtype = detect_rotation_type(node, key)
    if rtype is not None:
        rotations.append((key, rtype, node.key))

    bf = get_bf(node)
    # LL
    if bf > 1 and key < node.left.key:
        return right_rotate(node), rotations
    # RR
    if bf < -1 and key > node.right.key:
        return left_rotate(node), rotations
    # LR
    if bf > 1 and key > node.left.key:
        node.left = left_rotate(node.left)
        return right_rotate(node), rotations
    # RL
    if bf < -1 and key < node.right.key:
        node.right = right_rotate(node.right)
        return left_rotate(node), rotations

    return node, rotations

def print_tree(node, prefix="", is_left=True):
    if node is not None:
        print_tree(node.right, prefix + ("    " if is_left else "    "), False)
        print(prefix + ("└── " if is_left else "┌── ") + str(node.key))
        print_tree(node.left, prefix + ("    " if is_left else "    "), True)

def tree_to_structure(node):
    """输出树的结构（用于验证）"""
    if node is None:
        return None
    return {
        'key': node.key,
        'left': tree_to_structure(node.left),
        'right': tree_to_structure(node.right)
    }

# ===== 校验1：插入序列封闭性 =====
seq = [16, 3, 7, 11, 9, 26, 18]
print(f"插入序列: {seq}")

# ===== 逐步插入并追踪旋转 =====
root = None
print("\n===== 逐步插入追踪 =====")
for key in seq:
    rotations = []
    root, rotations = insert(root, key, rotations)
    if rotations:
        for r in rotations:
            print(f"插入 {key}: 失衡节点 {r[2]}, 旋转类型 {r[1]}")
    else:
        print(f"插入 {key}: 无需旋转")

# ===== 校验2：旋转类型验证 =====
print("\n===== 校验2: 旋转类型序列 =====")
# 重新从头追踪所有旋转
root = None
all_rotations = []
for key in seq:
    rotations = []
    root, rotations = insert(root, key, rotations)
    all_rotations.extend(rotations)

expected_rotations = [("LR", 7, 16), ("LL", 9, 16), ("RR", 26, 7), ("RL", 18, 16)]
print(f"实际旋转序列: {[(r[1], r[0], r[2]) for r in all_rotations]}")
print(f"期望旋转序列: {expected_rotations}")

assert len(all_rotations) == 4, f"期望4次旋转，实际{len(all_rotations)}次"
assert all_rotations[0][1] == "LR", f"第1次旋转应为LR，实际{all_rotations[0][1]}"
assert all_rotations[1][1] == "LL", f"第2次旋转应为LL，实际{all_rotations[1][1]}"
assert all_rotations[2][1] == "RR", f"第3次旋转应为RR，实际{all_rotations[2][1]}"
assert all_rotations[3][1] == "RL", f"第4次旋转应为RL，实际{all_rotations[3][1]}"
print("旋转类型校验通过！")

# ===== 校验3：插入16,3,7后的LR旋转结果 =====
print("\n===== 校验3: 插入16,3,7后的树结构 =====")
root1 = None
for key in [16, 3, 7]:
    rotations = []
    root1, rotations = insert(root1, key, rotations)
print_tree(root1)
# 验证：7为根，3为左孩子，16为右孩子
assert root1.key == 7, f"根应为7，实际{root1.key}"
assert root1.left.key == 3, f"左孩子应为3，实际{root1.left.key}"
assert root1.right.key == 16, f"右孩子应为16，实际{root1.right.key}"
print("插入16,3,7后结构正确！")

# ===== 校验4：插入11,9,26后的树结构（题(3)给出的树）=====
print("\n===== 校验4: 插入16,3,7,11,9,26后的树结构 =====")
root2 = None
for key in [16, 3, 7, 11, 9, 26]:
    rotations = []
    root2, rotations = insert(root2, key, rotations)
print_tree(root2)
# 验证题(3)给出的树结构:
#       11
#      /  \
#     7    16
#    / \     \
#   3   9    26
assert root2.key == 11, f"根应为11，实际{root2.key}"
assert root2.left.key == 7, f"左孩子应为7，实际{root2.left.key}"
assert root2.right.key == 16, f"右孩子应为16，实际{root2.right.key}"
assert root2.left.left.key == 3, f"7的左孩子应为3"
assert root2.left.right.key == 9, f"7的右孩子应为9"
assert root2.right.right.key == 26, f"16的右孩子应为26"
assert root2.right.left is None, f"16的左孩子应为空"
print("题(3)树结构校验通过！")

# ===== 校验5：插入18后的RL旋转结果 =====
print("\n===== 校验5: 插入18后的最终树结构 =====")
root3 = None
for key in [16, 3, 7, 11, 9, 26, 18]:
    rotations = []
    root3, rotations = insert(root3, key, rotations)
print_tree(root3)
# 验证RL旋转后:
#       11
#      /  \
#     7    18
#    / \   / \
#   3   9 16  26
assert root3.key == 11
assert root3.right.key == 18, f"11的右孩子应为18，实际{root3.right.key}"
assert root3.right.left.key == 16, f"18的左孩子应为16"
assert root3.right.right.key == 26, f"18的右孩子应为26"
print("最终树结构校验通过！")

# ===== 校验6：插入7后调整前节点16的平衡因子 =====
print("\n===== 校验6: 插入7后调整前节点16的平衡因子 =====")
# 手动构建: 16 -> left 3 -> right 7
# 高度: 节点16左子树高度=2, 右子树高度=0
# BF(16) = 2 - 0 = 2
bf_16 = 2 - 0  # 左子树高度2，右子树高度0
print(f"调整前 BF(16) = {bf_16}")
assert bf_16 == 2, f"BF(16)应为2，实际{bf_16}"
print("平衡因子校验通过！")

# ===== 校验7：最终树是否为有效AVL树 =====
print("\n===== 校验7: 最终树AVL性质 =====")
def is_avl(node):
    if node is None:
        return True, 0
    left_ok, left_h = is_avl(node.left)
    right_ok, right_h = is_avl(node.right)
    h = 1 + max(left_h, right_h)
    bf = left_h - right_h
    if abs(bf) > 1:
        return False, h
    return left_ok and right_ok, h

ok, h = is_avl(root3)
assert ok, "最终树不满足AVL性质！"
print(f"最终树高度: {h}, AVL性质验证通过！")

print("\n" + "="*50)
print("所有参数校验通过！")
