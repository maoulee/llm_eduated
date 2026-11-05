# ===== 初始参数（凭经验给定）=====
P1 = 1                            # AVL 平衡因子绝对值上限

# 插入序列：手选，目标是触发 LR 双旋 + LL 单旋
# 思路：先建一棵左右各有一层的树，再在右子树的左子树右侧插入→触发LR；
#       接着在左子树的左子树的左侧插入→触发LL
P2 = [6, 4, 9, 3, 5, 7, 2, 8, 1, 10]

P3 = 7                            # 子问题(1)分值
P4 = 4                            # 子问题(2)分值
P5 = -1                           # 空树高度
P6 = 4                            # 子问题(3)分值
# 派生参数
P7 = P5 + 1                       # 单节点树高度

# ===== AVL 树实现（标准库） =====
class AVLNode:
    def __init__(self, key):
        self.key = key
        self.lchild = None
        self.rchild = None
        self.height = 0   # 叶子节点高度=0，空树=-1

def get_height(node):
    if node is None:
        return -1
    return node.height

def get_bf(node):
    if node is None:
        return 0
    return get_height(node.lchild) - get_height(node.rchild)

def update_height(node):
    node.height = max(get_height(node.lchild), get_height(node.rchild)) + 1

rotation_log = []   # 记录 (失衡节点key, 旋转类型)

def right_rotate(z):
    """LL 型：右旋"""
    y = z.lchild
    z.lchild = y.rchild
    y.rchild = z
    update_height(z)
    update_height(y)
    return y

def left_rotate(z):
    """RR 型：左旋"""
    y = z.rchild
    z.rchild = y.lchild
    y.lchild = z
    update_height(z)
    update_height(y)
    return y

def insert(node, key):
    if node is None:
        return AVLNode(key)
    if key < node.key:
        node.lchild = insert(node.lchild, key)
    else:
        node.rchild = insert(node.rchild, key)
    update_height(node)
    bf = get_bf(node)
    # LL
    if bf > 1 and key < node.lchild.key:
        rotation_log.append((node.key, 'LL'))
        return right_rotate(node)
    # RR
    if bf < -1 and key > node.rchild.key:
        rotation_log.append((node.key, 'RR'))
        return left_rotate(node)
    # LR
    if bf > 1 and key > node.lchild.key:
        rotation_log.append((node.key, 'LR'))
        node.lchild = left_rotate(node.lchild)
        return right_rotate(node)
    # RL
    if bf < -1 and key < node.rchild.key:
        rotation_log.append((node.key, 'RL'))
        node.rchild = right_rotate(node.rchild)
        return left_rotate(node)
    return node

# ===== 构建 AVL 树并记录旋转 =====
root = None
for k in P2:
    root = insert(root, k)

# ===== 层序遍历辅助 =====
from collections import deque
def level_order(node):
    if node is None:
        return []
    result = []
    q = deque([node])
    while q:
        cur = q.popleft()
        result.append(cur.key)
        if cur.lchild:
            q.append(cur.lchild)
        if cur.rchild:
            q.append(cur.rchild)
    return result

# ===== 约束验证 =====
# 约束1: 序列长度 9-11
assert 9 <= len(P2) <= 11, f"序列长度 {len(P2)} 不在 9-11"

# 约束2: 互不相同
assert len(set(P2)) == len(P2), "序列中有重复元素"

# 约束3: 至少一次 LR 或 RL 双旋
double_rotations = [r for r in rotation_log if r[1] in ('LR', 'RL')]
assert len(double_rotations) >= 1, f"无 LR/RL 双旋，旋转记录: {rotation_log}"

# 约束4: 旋转总数 >= 2
assert len(rotation_log) >= 2, f"旋转次数 {len(rotation_log)} < 2"

# 约束5: 首次失衡不是第一个元素
assert len(rotation_log) > 0, "无旋转"

# 约束6: 所有元素为正整数
assert all(isinstance(k, int) and k > 0 for k in P2), "存在非正整数"

# ===== 自洽性校验 =====
assert P1 == 1
assert P7 == P5 + 1
assert 5 <= P3 <= 7
assert 4 <= P4 <= 5
assert 4 <= P6 <= 5

# 验证最终树是合法 AVL
def is_avl(node):
    if node is None:
        return True, -1
    lok, lh = is_avl(node.lchild)
    rok, rh = is_avl(node.rchild)
    if not lok or not rok:
        return False, 0
    if abs(lh - rh) > 1:
        return False, 0
    # BST 性质
    if node.lchild and node.lchild.key >= node.key:
        return False, 0
    if node.rchild and node.rchild.key <= node.key:
        return False, 0
    return True, max(lh, rh) + 1

ok, h = is_avl(root)
assert ok, "最终树不是合法 AVL"

# ===== 输出 =====
print(f"P1={P1}")
print(f"P2={P2}")
print(f"P3={P3}")
print(f"P4={P4}")
print(f"P5={P5}")
print(f"P6={P6}")
print(f"P7={P7}")
print(f"--- 验证信息 ---")
print(f"序列长度: {len(P2)}")
print(f"旋转记录: {rotation_log}")
print(f"双旋次数: {len(double_rotations)}")
print(f"旋转总数: {len(rotation_log)}")
print(f"最终根节点: {root.key}")
print(f"最终树高度: {root.height}")
print(f"最终根节点BF: {get_bf(root)}")
print(f"最终层序遍历: {level_order(root)}")
print(f"AVL合法: {ok}")
print(f"总分: {P3 + P4 + P6}")
