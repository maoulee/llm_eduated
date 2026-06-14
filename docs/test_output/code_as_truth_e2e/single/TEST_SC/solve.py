# ====== 二叉树带权路径长度(WPL)计算 ======
# 树结构（根为第 0 层）：
#           A(9)
#          / \
#       B(2)  C(4)
#             / \
#          D(5) E(6)
#              / \
#           F(3) G(7)
#
# 叶子节点：B, D, F, G
# 内部节点：A, C, E

# ====== 参数定义 ======
# 每个节点：权值、从根到该节点的边数（路径长度）、是否为叶子
leaf_nodes = {
    'B': {'weight': 2, 'edges': 1},   # 根→B，1条边
    'D': {'weight': 5, 'edges': 2},   # 根→C→D，2条边
    'F': {'weight': 3, 'edges': 3},   # 根→C→E→F，3条边
    'G': {'weight': 7, 'edges': 3},   # 根→C→E→G，3条边
}

internal_nodes = {
    'A': {'weight': 9, 'edges': 0},   # 根节点
    'C': {'weight': 4, 'edges': 1},
    'E': {'weight': 6, 'edges': 2},
}

# ====== 正确算法：WPL = Σ(叶子权值 × 路径长度) ======
print("=" * 50)
print("正确算法：WPL = Σ(叶子权值 × 路径长度)")
print("=" * 50)
terms = []
for name, info in leaf_nodes.items():
    contrib = info['weight'] * info['edges']
    terms.append((name, info['weight'], info['edges'], contrib))
    print(f"  叶子{name}: 权值={info['weight']}, 路径长度={info['edges']}, 贡献={info['weight']}*{info['edges']}={contrib}")

WPL_correct = sum(info['weight'] * info['edges'] for info in leaf_nodes.values())
formula = " + ".join(f"{t[1]}*{t[2]}" for t in terms)
print(f"\n  WPL = {formula} = {WPL_correct}")

# ====== 干扰1：层数偏移（路径长度 = edges + 1）======
# 错误：将"层数"（根为第1层）代替"边数"作为路径长度，每个叶子路径长度偏移+1
print("\n" + "=" * 50)
print("干扰1：层数偏移（路径长度 = 边数 + 1）")
print("=" * 50)
WPL_d1 = sum(info['weight'] * (info['edges'] + 1) for info in leaf_nodes.values())
for name, info in leaf_nodes.items():
    wrong_edges = info['edges'] + 1
    print(f"  叶子{name}: {info['weight']}*{wrong_edges}={info['weight'] * wrong_edges}")
print(f"\n  WPL(干扰1) = {WPL_d1}")
print(f"  与正确值差 = {WPL_d1 - WPL_correct}")

# ====== 干扰2：遗漏叶子节点 D ======
# 错误：求和时遗漏叶子 D（权值5，路径长度2）
print("\n" + "=" * 50)
print("干扰2：遗漏叶子节点 D")
print("=" * 50)
omitted = 'D'
for name, info in leaf_nodes.items():
    if name != omitted:
        contrib = info['weight'] * info['edges']
        print(f"  叶子{name}: {info['weight']}*{info['edges']}={contrib}")
    else:
        print(f"  叶子{name}: *** 被遗漏 ***")
WPL_d2 = sum(info['weight'] * info['edges'] for name, info in leaf_nodes.items() if name != omitted)
print(f"\n  WPL(干扰2) = {WPL_d2}")
print(f"  与正确值差 = {WPL_correct - WPL_d2}")

# ====== 干扰3：内部节点 E 误计 ======
# 错误：将内部节点 E（权值6，路径长度2）也纳入 WPL 求和
print("\n" + "=" * 50)
print("干扰3：误计内部节点 E")
print("=" * 50)
miscounted = 'E'
extra = internal_nodes[miscounted]
extra_contrib = extra['weight'] * extra['edges']
print(f"  正常叶子求和 = {WPL_correct}")
print(f"  + 内部节点{miscounted}(误计): {extra['weight']}*{extra['edges']}={extra_contrib}")
WPL_d3 = WPL_correct + extra_contrib
print(f"\n  WPL(干扰3) = {WPL_d3}")
print(f"  与正确值差 = {WPL_d3 - WPL_correct}")

# ====== 汇总 ======
print("\n" + "=" * 50)
print("汇总")
print("=" * 50)
print(f"  正确答案:         {WPL_correct}")
print(f"  干扰1(层数偏移):  {WPL_d1}")
print(f"  干扰2(遗漏叶子D): {WPL_d2}")
print(f"  干扰3(节点E误计): {WPL_d3}")

# ====== 验证 ======
print("\n" + "=" * 50)
print("验证")
print("=" * 50)
values = [WPL_correct, WPL_d1, WPL_d2, WPL_d3]
labels = ['正确', '干扰1', '干扰2', '干扰3']
print(f"  所有值: {dict(zip(labels, values))}")
print(f"  互不相同: {len(set(values)) == 4}")

sorted_vals = sorted(values)
diffs = [sorted_vals[i + 1] - sorted_vals[i] for i in range(len(sorted_vals) - 1)]
print(f"  排序后: {sorted_vals}")
print(f"  相邻差值: {diffs}")
print(f"  最小差值: {min(diffs)}")

print(f"\n  各干扰与正确值差:")
for label, val in [('干扰1', WPL_d1), ('干扰2', WPL_d2), ('干扰3', WPL_d3)]:
    d = abs(val - WPL_correct)
    ok = "OK" if 5 <= d <= 20 else "FAIL"
    print(f"    {label}: |{val} - {WPL_correct}| = {d}  [{ok}]")
