# 二叉树 WPL 计算
# 树结构：
#       A
#     /   \
#    B     C
#   / \   / \
#  D   E F   G
#     / \
#    H   I

# 叶子节点及其权值和路径长度（边数）
leaves = {
    'D': {'weight': 3, 'path_length': 2},  # A->B->D
    'F': {'weight': 5, 'path_length': 2},  # A->C->F
    'G': {'weight': 7, 'path_length': 2},  # A->C->G
    'H': {'weight': 2, 'path_length': 3},  # A->B->E->H
    'I': {'weight': 4, 'path_length': 3},  # A->B->E->I
}

wpl = 0
for node, info in leaves.items():
    contribution = info['weight'] * info['path_length']
    print(f"节点 {node}: 权值={info['weight']}, 路径长度={info['path_length']}, 贡献={contribution}")
    wpl += contribution

print(f"正确: {wpl}")
