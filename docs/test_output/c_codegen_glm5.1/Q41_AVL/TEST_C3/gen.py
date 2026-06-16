import sys
from collections import deque
from itertools import combinations

class AVLNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

class AVLTree:
    def __init__(self):
        self.root = None
        self.rotations = []

    def get_height(self, node):
        return node.height if node else 0

    def get_balance(self, node):
        return self.get_height(node.left) - self.get_height(node.right) if node else 0

    def update_height(self, node):
        node.height = 1 + max(self.get_height(node.left), self.get_height(node.right))

    def rotate_right(self, y):
        x = y.left
        T2 = x.right
        x.right = y
        y.left = T2
        self.update_height(y)
        self.update_height(x)
        return x

    def rotate_left(self, x):
        y = x.right
        T2 = y.left
        y.left = x
        x.right = T2
        self.update_height(x)
        self.update_height(y)
        return y

    def insert(self, key):
        rotation_info = {'key': key, 'type': '无旋转'}
        self.root = self._insert(self.root, key, rotation_info)
        self.rotations.append(rotation_info)

    def _insert(self, node, key, ri):
        if not node:
            return AVLNode(key)
        if key < node.key:
            node.left = self._insert(node.left, key, ri)
        else:
            node.right = self._insert(node.right, key, ri)

        self.update_height(node)
        balance = self.get_balance(node)

        if balance > 1 and key < node.left.key:
            if ri['type'] == '无旋转':
                ri['type'] = 'LL'
                ri['pivot'] = node.key
            return self.rotate_right(node)
        if balance < -1 and key > node.right.key:
            if ri['type'] == '无旋转':
                ri['type'] = 'RR'
                ri['pivot'] = node.key
            return self.rotate_left(node)
        if balance > 1 and key > node.left.key:
            if ri['type'] == '无旋转':
                ri['type'] = 'LR'
                ri['pivot'] = node.key
            node.left = self.rotate_left(node.left)
            return self.rotate_right(node)
        if balance < -1 and key < node.right.key:
            if ri['type'] == '无旋转':
                ri['type'] = 'RL'
                ri['pivot'] = node.key
            node.right = self.rotate_right(node.right)
            return self.rotate_left(node)
        return node

    def level_order(self):
        if not self.root:
            return []
        result = []
        q = deque([(self.root, 0)])
        while q:
            node, level = q.popleft()
            if len(result) <= level:
                result.append([])
            result[level].append(node.key)
            if node.left:
                q.append((node.left, level + 1))
            if node.right:
                q.append((node.right, level + 1))
        return result

    def inorder(self):
        result = []
        def _in(node):
            if node:
                _in(node.left)
                result.append(node.key)
                _in(node.right)
        _in(self.root)
        return result

    def get_bf(self, key):
        def _find(node):
            if not node:
                return None
            if key == node.key:
                return node
            elif key < node.key:
                return _find(node.left)
            else:
                return _find(node.right)
        node = _find(self.root)
        return self.get_balance(node) if node else None

    def get_depth(self):
        return self.get_height(self.root)

    def find_parent(self, key):
        def _find(node, parent):
            if not node:
                return None
            if key == node.key:
                return parent
            elif key < node.key:
                return _find(node.left, node)
            else:
                return _find(node.right, node)
        p = _find(self.root, None)
        return p.key if p else None

    def get_right_child(self, key):
        def _find(node):
            if not node:
                return None
            if key == node.key:
                return node
            elif key < node.key:
                return _find(node.left)
            else:
                return _find(node.right)
        node = _find(self.root)
        return node.right.key if node and node.right else None

# ========== 搜索好的插入序列 ==========
init_keys = [30, 10, 50, 5, 20, 40, 60]
# 候选插入节点（不与初始节点重复）
candidates = [1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 15, 16, 18, 19, 22, 25, 28, 29, 35, 45, 46, 48, 55, 65, 70]

best = None
best_count = 0
best_types = set()

# 尝试所有4元组排列（太多，改为尝试有序组合再排列）
from itertools import permutations
# 先找有潜力的组合
import random
random.seed(42)

found = None
# 尝试随机排列
for _ in range(200000):
    seq = random.sample(candidates, 4)
    tree = AVLTree()
    for k in init_keys:
        tree.insert(k)
    tree.rotations = []
    for k in seq:
        tree.insert(k)
    rot_types = set()
    for ri in tree.rotations:
        if ri['type'] != '无旋转':
            rot_types.add(ri['type'])
    if len(rot_types) >= 3:
        found = seq
        found_types = rot_types
        found_rotations = list(tree.rotations)
        break
    if len(rot_types) >= 2 and best_count < 2:
        best = seq
        best_count = 2
        best_types = rot_types
        best_rotations = list(tree.rotations)

if found is None and best is not None:
    found = best
    found_types = best_types
    found_rotations = best_rotations

assert found is not None, "没找到合适的序列！"

insert_keys = found
print(f"找到的插入序列: {insert_keys}")
print(f"触发的旋转类型: {found_types}")
print()

# ========== 正式输出 ==========
# 构建初始树
tree_init = AVLTree()
for k in init_keys:
    tree_init.insert(k)

def is_avl(node):
    if not node:
        return True, 0
    ok_l, h_l = is_avl(node.left)
    ok_r, h_r = is_avl(node.right)
    balanced = abs(h_l - h_r) <= 1
    return ok_l and ok_r and balanced, 1 + max(h_l, h_r)

ok, _ = is_avl(tree_init.root)
assert ok, "初始树不是AVL！"

print("===== 参数 =====")
print(f"初始AVL树节点（插入顺序）: {init_keys}")
print(f"初始树层序遍历:")
for i, level in enumerate(tree_init.level_order()):
    print(f"  第{i+1}层: {level}")
print(f"初始树中序遍历: {tree_init.inorder()}")
print(f"初始树深度: {tree_init.get_depth()}")
print()
print(f"依次插入节点: {insert_keys}")
print()

# ========== 题干描述 ==========
print("===== 题干描述 =====")
print()
print("已知一棵平衡二叉树（AVL树）的初始状态由关键字序列 {30, 10, 50, 5, 20, 40, 60}")
print("依次插入空树而得。现依次将关键字", "、".join(str(k) for k in insert_keys), "插入该平衡二叉树，")
print("每次插入后若出现不平衡则进行相应调整，使其始终保持平衡二叉树的性质。")
print()
print("请回答以下问题：")
print()
print("（1）依次插入上述4个关键字后，共触发了哪几种旋转调整？写出每次插入")
print("    触发的旋转类型（LL/RR/LR/RL）及失衡节点的关键字。")
print()
print("（2）插入关键字15并完成调整后，关键字15的父节点关键字是什么？关键字19的")
print("    左孩子和右孩子分别是哪个关键字？")
print()
print("（3）所有插入完成后，该平衡二叉树的根节点关键字是什么？树的深度是多少？")
print()
print("（4）所有插入完成后，关键字5的平衡因子是多少？关键字20的右孩子是哪个关键字？")
print()

# ========== 求解路径 ==========
print("===== 求解路径 =====")
print()

tree2 = AVLTree()
for k in init_keys:
    tree2.insert(k)
tree2.rotations = []

for idx, k in enumerate(insert_keys):
    tree2.insert(k)
    ri = tree2.rotations[-1]
    print(f"【第{idx+1}步】插入关键字 {k}：")
    levels = tree2.level_order()
    print(f"  旋转类型: {ri['type']}", end="")
    if 'pivot' in ri:
        print(f"，失衡节点: {ri['pivot']}")
    else:
        print()
    print(f"  调整后层序遍历:")
    for i, level in enumerate(levels):
        print(f"    第{i+1}层: {level}")
    print(f"  中序遍历: {tree2.inorder()}")
    print()

# ========== 答案 ==========
print("===== 答案 =====")
print()

print("（1）各次插入触发的旋转：")
rotation_types = set()
for idx, ri in enumerate(tree2.rotations):
    rtype = ri['type']
    if rtype != '无旋转':
        base = rtype
        rotation_types.add(base)
    pivot_str = f"，失衡节点为{ri['pivot']}" if 'pivot' in ri else ""
    print(f"  插入{insert_keys[idx]}: {rtype}{pivot_str}")
print(f"  共触发 {len(rotation_types)} 种旋转类型: {', '.join(sorted(rotation_types))}")
print()

# (2) 插入第2个后，insert_keys[1]的父节点
tree3 = AVLTree()
for k in init_keys:
    tree3.insert(k)
tree3.insert(insert_keys[0])
tree3.insert(insert_keys[1])
# (2) 插入15并调整后，15的父节点，19的左右孩子
parent_key2 = tree3.find_parent(insert_keys[1])
# 19的左右孩子（在tree3中，插入15后的状态）
lc_19 = tree3.get_right_child(19)  # 19的右孩子
# 需要获取19的左孩子
def get_left_child(tree, key):
    def _find(node):
        if not node:
            return None
        if key == node.key:
            return node
        elif key < node.key:
            return _find(node.left)
        else:
            return _find(node.right)
    node = _find(tree.root)
    return node.left.key if node and node.left else None

lc_19_val = get_left_child(tree3, 19)
rc_19_val = tree3.get_right_child(19)
print(f"（2）关键字15的父节点为 {parent_key2}。")
print(f"     关键字19的左孩子为 {lc_19_val}，右孩子为 {rc_19_val}。")
print()

# (3) 最终根和深度
final_root = tree2.root.key
final_depth = tree2.get_depth()
print(f"（3）最终根节点关键字: {final_root}，树的深度: {final_depth}。")
print()

# (4)
bf_5 = tree2.get_bf(5)
rc_20 = tree2.get_right_child(20)
rc_20_str = str(rc_20) if rc_20 is not None else "无"
print(f"（4）关键字5的平衡因子: {bf_5}，关键字20的右孩子: {rc_20_str}。")
print()

print("===== 最终树结构 =====")
levels_final = tree2.level_order()
for i, level in enumerate(levels_final):
    print(f"第{i+1}层: {level}")
print(f"中序遍历: {tree2.inorder()}")
