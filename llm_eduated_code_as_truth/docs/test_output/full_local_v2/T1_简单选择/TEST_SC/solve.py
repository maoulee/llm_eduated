# 二叉树带权路径长度 WPL 计算
# 叶子节点：D(5), E(10), G(20), H(15)
# 路径长度（根到叶子的边数）：
#   D: A->B->D = 2
#   E: A->B->E = 2
#   G: A->C->F->G = 3
#   H: A->C->F->H = 3

leaves = [
    ("D", 5, 2),
    ("E", 10, 2),
    ("G", 20, 3),
    ("H", 15, 3),
]

wpl = sum(weight * path_len for _, weight, path_len in leaves)
print(f"WPL: {wpl}")
