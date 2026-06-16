"""
AVL树插入15后的旋转操作分析
"""

# 初始树结构
#         30
#        /  \
#      10    50
#        \
#        20

# 插入15：15<30→左，15>10→右，15<20→左，插入为20的左孩子
# 插入后（旋转前）：
#         30
#        /  \
#      10    50
#        \
#        20
#       /
#     15

# 计算各节点平衡因子（左高-右高）
# 节点15: 叶子，高=1，BF=0
# 节点20: 左子高=1(节点15)，右子高=0，高=2，BF=1-0=1
# 节点10: 左子高=0，右子高=2(节点20)，高=3，BF=0-2=-2 ← 失衡！
# 节点50: 叶子，高=1，BF=0
# 节点30: 左子高=3，右子高=1，高=4，BF=3-1=2

# 从插入路径自底向上，第一个失衡节点是10
# 插入位置：10的右孩子(20)的左子树 → LR型
# 需要：先对20左旋，再对10右旋

# 左旋20：
#       15
#         \
#         20
# 替换原来10的右子树

# 右旋10：
#       15
#      /  \
#    10    20
# 替换原来30的左子树

# 最终树：
#         30
#        /  \
#      15    50
#     /  \
#   10    20

# 验证平衡因子
# 节点10: 高=1, BF=0 ✓
# 节点20: 高=1, BF=0 ✓
# 节点15: 左高=1, 右高=1, 高=2, BF=0 ✓
# 节点50: 高=1, BF=0 ✓
# 节点30: 左高=2, 右高=1, 高=3, BF=1 ✓

# 层序遍历
from collections import deque

# 构建最终树
class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

root = Node(30)
root.left = Node(15)
root.right = Node(50)
root.left.left = Node(10)
root.left.right = Node(20)

# 层序遍历
def level_order(root):
    if not root:
        return []
    result = []
    queue = deque([root])
    while queue:
        node = queue.popleft()
        result.append(node.val)
        if node.left:
            queue.append(node.left)
        if node.right:
            queue.append(node.right)
    return result

lo = level_order(root)
print(f"层序遍历: {lo}")
print(f"旋转类型: LR型（先左旋后右旋）")
print(f"旋转节点: 对节点20左旋，对节点10右旋")
print(f"最终根节点: 30")
