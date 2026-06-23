# WPL = sum(weight * path_length) for each leaf
# G(5): A->B->D->G = 3 edges
# H(8): A->B->D->H = 3 edges
# E(10): A->B->E = 2 edges
# F(12): A->C->F = 2 edges

leaves = [
    ("G", 5, 3),
    ("H", 8, 3),
    ("E", 10, 2),
    ("F", 12, 2),
]

wpl = sum(w * d for _, w, d in leaves)
print(f"WPL: {wpl}")
