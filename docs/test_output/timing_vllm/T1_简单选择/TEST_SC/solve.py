# 带权路径长度 WPL = sum(叶子权值 × 从根到该叶子的路径长度)
# 路径长度从根节点开始为 0
# A(0) -> B(1) -> D(2), E(2)
# A(0) -> C(1) -> F(2), G(2)

leaves = {
    'D': (3, 2),
    'E': (5, 2),
    'F': (8, 2),
    'G': (12, 2),
}

wpl = sum(weight * depth for weight, depth in leaves.values())
print(f"WPL: {wpl}")
