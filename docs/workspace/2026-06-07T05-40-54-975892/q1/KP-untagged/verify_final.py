"""
最终验证脚本：详细跟踪AVL插入过程
"""

class Node:
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

def insert(root, key):
    rotations = []
    if not root:
        return Node(key), rotations
    
    if key < root.key:
        root.left, r = insert(root.left, key)
        rotations.extend(r)
    elif key > root.key:
        root.right, r = insert(root.right, key)
        rotations.extend(r)
    else:
        return root, rotations
    
    update_height(root)
    balance = get_balance(root)
    
    if balance > 1 and key < root.left.key:
        rotations.append(("LL", root.key))
        return right_rotate(root), rotations
    if balance < -1 and key > root.right.key:
        rotations.append(("RR", root.key))
        return left_rotate(root), rotations
    if balance > 1 and key > root.left.key:
        rotations.append(("LR", root.key))
        root.left = left_rotate(root.left)
        return right_rotate(root), rotations
    if balance < -1 and key < root.right.key:
        rotations.append(("RL", root.key))
        root.right = right_rotate(root.right)
        return left_rotate(root), rotations
    
    return root, rotations

def inorder(node, result=None):
    if result is None:
        result = []
    if node:
        inorder(node.left, result)
        result.append(node.key)
        inorder(node.right, result)
    return result

def get_root_key(node):
    return node.key if node else None

def get_tree_height(node):
    return get_height(node)

# 使用序列1: [28, 13, 25, 14, 2, 9, 17, 16, 29, 10]
seq = [28, 13, 25, 14, 2, 9, 17, 16, 29, 10]

print("=== 逐步插入过程 ===")
root = None
all_rotations = []

for i, key in enumerate(seq):
    root, rotations = insert(root, key)
    step_rotations = [(r[0], r[1]) for r in rotations]
    all_rotations.extend([(key, r[0], r[1]) for r in rotations])
    
    print(f"\n插入第{i+1}个关键字 {key}:")
    print(f"  旋转: {step_rotations if step_rotations else '无'}")
    print(f"  根节点: {get_root_key(root)}")
    print(f"  树高: {get_tree_height(root)}")
    print(f"  中序: {inorder(root)}")

print(f"\n=== 总结 ===")
print(f"插入序列: {seq}")
print(f"所有旋转: {all_rotations}")
rot_types = set(r[1] for r in all_rotations)
print(f"旋转类型: {rot_types}")
print(f"最终根节点: {get_root_key(root)}")
print(f"最终树高: {get_tree_height(root)}")
print(f"最终中序: {inorder(root)}")

# 验证：最终中序应该等于排序后的序列
assert inorder(root) == sorted(seq), "中序遍历不等于排序序列！"
print("\n✓ 中序遍历验证通过")

# 验证：包含四种旋转
assert rot_types == {"LL", "RR", "LR", "RL"}, f"未覆盖四种旋转: {rot_types}"
print("✓ 四种旋转覆盖验证通过")

# 验证：AVL平衡性
def check_avl(node):
    if not node:
        return True, 0
    lh, ok_l = check_avl(node.left)
    rh, ok_r = check_avl(node.right)
    if not ok_l or not ok_r:
        return 0, False
    if abs(lh - rh) > 1:
        return 0, False
    return 1 + max(lh, rh), True

height, is_balanced = check_avl(root)
assert is_balanced, "最终树不是AVL树！"
print(f"✓ AVL平衡性验证通过 (树高={height})")

print("\n=== 参数验证通过 ===")
print(f"序列长度: {len(seq)}")
print(f"旋转次数: {len(all_rotations)}")
print(f"旋转类型: {sorted(rot_types)}")

# 检查每个子问题所需参数
print("\n=== 子问题参数检查 ===")
print("(1) 插入第5个关键字后根节点: 需要跟踪前5步")
print("(2) 插入过程中所有旋转: 需要完整跟踪")
print("(3) 最终树的中序遍历: 需要最终状态")
print("所有参数均可从题干序列推导")

