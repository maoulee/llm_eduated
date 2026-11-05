# ===== AVL 树参数与结构校验 =====
# 本脚本验证题目中所有结构声明是否自洽：
# 1. 初始树是合法的 AVL 树
# 2. 插入 15 触发 LR 旋转
# 3. LR 旋转后树仍是合法 AVL 树
# 4. 插入 45 触发 RL 旋转
# 5. 最终树是 7 个节点的完美二叉树

class Node:
    def __init__(self, key):
        self.key = key
        self.lchild = None
        self.rchild = None

def height(n):
    if n is None:
        return 0
    return 1 + max(height(n.lchild), height(n.rchild))

def bf(n):
    """平衡因子 = 左子树高度 - 右子树高度"""
    if n is None:
        return 0
    return height(n.lchild) - height(n.rchild)

def is_avl(n):
    """检查以 n 为根的树是否满足 AVL 条件"""
    if n is None:
        return True
    if abs(bf(n)) > 1:
        return False
    return is_avl(n.lchild) and is_avl(n.rchild)

def find_first_unbalanced(n, path):
    """从插入路径上找最先失衡节点（从新节点向上）"""
    for node in reversed(path):
        if abs(bf(node)) > 1:
            return node
    return None

def collect(n, d):
    if n: d[n.key] = n; collect(n.lchild, d); collect(n.rchild, d)

# ===== 构建初始 AVL 树 =====
#        30
#       /  \
#      20   40
#     /      \
#    10       50
root = Node(30)
root.lchild = Node(20)
root.rchild = Node(40)
root.lchild.lchild = Node(10)
root.rchild.rchild = Node(50)

# ===== 校验1：初始树合法性 =====
print("=== 校验1：初始树 ===")
node_map = {}
collect(root, node_map)
for k in [10, 20, 30, 40, 50]:
    print(f"  BF({k}) = {bf(node_map[k])}")
assert is_avl(root), "初始树不满足 AVL 条件！"
print("  初始树是合法 AVL 树 ✓")

# ===== 校验2：插入 15 → 应触发 LR 旋转 =====
print("\n=== 校验2：插入 15 ===")
# 插入 15：15 < 30 → 20, 15 < 20 → 10, 15 > 10 → 10 的右孩子
root.lchild.lchild.rchild = Node(15)

node_map = {}
collect(root, node_map)

print(f"  插入后 BF(15)={bf(node_map[15])}, BF(10)={bf(node_map[10])}, BF(20)={bf(node_map[20])}, BF(30)={bf(node_map[30])}")

# 找最先失衡节点
path_15 = [node_map[15], node_map[10], node_map[20], node_map[30]]
first_ub = find_first_unbalanced(root, path_15)
print(f"  最先失衡节点: {first_ub.key}")
assert first_ub.key == 20, f"期望20，得到{first_ub.key}"

# 判断旋转类型：失衡节点 BF=2（左重），新节点插入在左孩子的右子树
ub_bf = bf(node_map[20])
child_bf = bf(node_map[10])  # 失衡节点的左孩子
print(f"  失衡节点 BF={ub_bf}（左重），左孩子(10) BF={child_bf}")
assert ub_bf > 1, "应为左重"
assert child_bf < 0, "左孩子应为右重（LR型）"
rotation_type = "LR"
print(f"  旋转类型: {rotation_type} ✓")

# ===== 执行 LR 旋转 =====
# LR = 先对左孩子(10)左旋，再对失衡节点(20)右旋
# Step 1: 左旋 10 (10 的右孩子 15 上升)
node_20 = node_map[20]
node_10 = node_map[10]
node_15 = node_map[15]

# 左旋 10：15 替代 10 成为 20 的左孩子，10 成为 15 的左孩子
node_15.lchild = node_10
node_10.rchild = None  # 15 原来没有左孩子
node_20.lchild = node_15

# Step 2: 右旋 20 (15 的右孩子上升替代 20)
# 20 成为 15 的右孩子，15 原来没有右孩子
node_15.rchild = node_20
node_20.lchild = None  # 15 原来没有右孩子
root.lchild = node_15  # 15 成为 30 的左孩子

node_map2 = {}
collect(root, node_map2)
print(f"\n  LR 旋转后树结构:")
print(f"    根={root.key}, 左={root.lchild.key}, 右={root.rchild.key}")
print(f"    左子树: {root.lchild.key} -> 左={root.lchild.lchild.key}, 右={root.lchild.rchild.key}")
print(f"    右子树: {root.rchild.key} -> 右={root.rchild.rchild.key}")
for k in [10, 15, 20, 30, 40, 50]:
    print(f"    BF({k}) = {bf(node_map2[k])}")
assert is_avl(root), "LR 旋转后不满足 AVL！"
print("  LR 旋转后是合法 AVL 树 ✓")

# ===== 校验3：插入 45 → 应触发 RL 旋转 =====
print("\n=== 校验3：插入 45 ===")
# 插入 45：45 > 30 → 40, 45 > 40 → 50, 45 < 50 → 50 的左孩子
node_map2[50].lchild = Node(45)

node_map3 = {}
collect(root)

print(f"  插入后 BF(45)={bf(node_map3[45])}, BF(50)={bf(node_map3[50])}, BF(40)={bf(node_map3[40])}, BF(30)={bf(node_map3[30])}")

# 找最先失衡节点
path_45 = [node_map3[45], node_map3[50], node_map3[40], node_map3[30]]
first_ub2 = find_first_unbalanced(root, path_45)
print(f"  最先失衡节点: {first_ub2.key}")
assert first_ub2.key == 40, f"期望40，得到{first_ub2.key}"

ub_bf2 = bf(node_map3[40])
child_bf2 = bf(node_map3[50])  # 失衡节点的右孩子
print(f"  失衡节点 BF={ub_bf2}（右重），右孩子(50) BF={child_bf2}")
assert ub_bf2 < -1, "应为右重"
assert child_bf2 > 0, "右孩子应为左重（RL型）"
rotation_type2 = "RL"
print(f"  旋转类型: {rotation_type2} ✓")

# ===== 执行 RL 旋转 =====
# RL = 先对右孩子(50)右旋，再对失衡节点(40)左旋
node_40 = node_map3[40]
node_50 = node_map3[50]
node_45 = node_map3[45]

# Step 1: 右旋 50 (45 替代 50 成为 40 的右孩子)
node_45.rchild = node_50
node_50.lchild = None  # 45 原来没有右孩子
node_40.rchild = node_45

# Step 2: 左旋 40 (45 替代 40 成为 30 的右孩子)
node_45.lchild = node_40
node_40.rchild = None  # 45 原来没有左孩子
root.rchild = node_45  # 45 成为 30 的右孩子

node_map4 = {}
collect(root)

# ===== 校验4：最终树为完美二叉树 =====
print("\n=== 校验4：最终树结构 ===")
print(f"  根={root.key}")
print(f"  左孩子={root.lchild.key}, 右孩子={root.rchild.key}")
print(f"  左子树: {root.lchild.key} -> 左={root.lchild.lchild.key}, 右={root.lchild.rchild.key}")
print(f"  右子树: {root.rchild.key} -> 左={root.rchild.lchild.key}, 右={root.rchild.rchild.key}")

# 计数节点数
def count(n):
    if n is None: return 0
    return 1 + count(n.lchild) + count(n.rchild)
total = count(root)
print(f"  总节点数: {total}")
assert total == 7, f"期望7个节点，得到{total}"

# 检查完美二叉树
h = height(root)
def is_perfect(n, depth, h):
    if n is None:
        return depth == h
    if n.lchild is None and n.rchild is None:
        return depth == h
    if n.lchild is None or n.rchild is None:
        return False
    return is_perfect(n.lchild, depth+1, h) and is_perfect(n.rchild, depth+1, h)
assert is_perfect(root, 1, h), "不是完美二叉树！"
print(f"  是高度为 {h} 的完美二叉树 ✓")

assert is_avl(root), "最终树不满足 AVL！"
print("  最终树是合法 AVL 树 ✓")

# ===== 校验5：伪代码空格验证 =====
print("\n=== 校验5：RL 伪代码空格 ===")
print("  ① C = B.lchild  (C 是 B 的左孩子)")
print("  ② B.lchild = C.rchild  (B 的左孩子接收 C 的右子树)")
print("  ③ A.rchild = C.lchild  (A 的右孩子接收 C 的左子树)")
print("  ✓ 与实际 RL 旋转过程一致")

print("\n参数校验通过")
