# WPL = sum of (weight * path_length) for all leaf nodes
# Path length = number of edges from root to leaf

# Leaf nodes and their path lengths:
# E(6): A->B->E, depth=2
# F(8): A->C->F, depth=2
# G(10): A->C->G, depth=2
# H(5): A->B->D->H, depth=3

leaves = [
    ("E", 6, 2),
    ("F", 8, 2),
    ("G", 10, 2),
    ("H", 5, 3),
]

wpl = sum(weight * depth for _, weight, depth in leaves)
print(f"WPL: {wpl}")
