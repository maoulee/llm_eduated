"""
gen.py — 求二叉树中所有叶子结点到根的路径
建模：用 Python 模拟 C/C++ 二叉链表 + 递归回溯算法
验证：对照通过条件逐条 assert
"""

# ========== 1. 二叉树结点定义（对应 Q1）==========
class BiTNode:
    def __init__(self, data):
        self.data = data
        self.lchild = None
        self.rchild = None

# ========== 2. 算法实现（对应 Q3）==========
# 全局路径数组（模拟 C 中定长数组）
MAX_DEPTH = 100
path = [None] * MAX_DEPTH
depth = 0  # 当前路径深度（C 中用 int depth 传参）

def collect_leaf_to_root_paths(root):
    """
    算法思想（对应 Q2）：
    采用先序遍历框架，递归深入时把当前结点加入 path[depth]，
    到达叶子结点时从 path[depth] 倒序输出到 path[0]（叶子→根方向），
    递归返回时 depth-- 实现回溯撤销。
    """
    results = []

    def dfs(node):
        nonlocal depth
        if node is None:
            return

        # 将当前结点加入路径
        path[depth] = node.data
        depth += 1

        # 叶子结点判定：左右子树同时为空
        if node.lchild is None and node.rchild is None:
            # 叶子→根方向输出：path[depth-1] ... path[0]
            leaf_to_root = list(reversed(path[:depth]))
            results.append(leaf_to_root)
        else:
            # 递归遍历左右子树
            dfs(node.lchild)
            dfs(node.rchild)

        # 回溯：撤销当前结点
        depth -= 1

    dfs(root)
    return results

# ========== 3. 测试用例构建 ==========

# 测试树 1：普通二叉树
#        A
#       / \
#      B   C
#     / \   \
#    D   E   F
root1 = BiTNode('A')
root1.lchild = BiTNode('B')
root1.rchild = BiTNode('C')
root1.lchild.lchild = BiTNode('D')
root1.lchild.rchild = BiTNode('E')
root1.rchild.rchild = BiTNode('F')

# 测试树 2：单结点树
root2 = BiTNode('X')

# 测试树 3：空树
root3 = None

# 测试树 4：退化树（只有左孩子链）
# A -> B -> C -> D
root4 = BiTNode('A')
root4.lchild = BiTNode('B')
root4.lchild.lchild = BiTNode('C')
root4.lchild.lchild.lchild = BiTNode('D')

# ========== 4. 执行与输出 ==========

print("=== PARAMS ===")
print("树1: A(B(D,E),C(,F))")
print("树2: 单结点 X")
print("树3: 空树")
print("树4: 退化左链 A->B->C->D")

print("\n=== REASONING ===")
print("算法采用先序遍历 + 回溯法：")
print("1. 递归深入时 path[depth++]=node.data 保存路径")
print("2. 叶子判定: lchild==NULL && rchild==NULL")
print("3. 到达叶子时 reversed(path[:depth]) 输出叶子→根")
print("4. 递归返回时 depth-- 撤销路径（回溯）")

print("\n=== 树1 结果 ===")
results1 = collect_leaf_to_root_paths(root1)
for p in results1:
    print(" -> ".join(p))

print("\n=== 树2 结果 ===")
results2 = collect_leaf_to_root_paths(root2)
for p in results2:
    print(" -> ".join(p))

print("\n=== 树3 结果 ===")
results3 = collect_leaf_to_root_paths(root3)
print(f"路径数量: {len(results3)}")

print("\n=== 树4 结果 ===")
results4 = collect_leaf_to_root_paths(root4)
for p in results4:
    print(" -> ".join(p))

print("\n=== ANSWER ===")
print("(1) 结点类型定义:")
print("""
typedef struct BiTNode {
    ElemType data;
    struct BiTNode *lchild, *rchild;
} BiTNode, *BiTree;
""")

print("(2) 算法基本设计思想:")
print("采用先序遍历框架，递归过程中用数组 path[] 保存从根到当前结点的路径。")
print("到达叶子结点（左右子树均为空）时，将 path 中保存的路径逆序输出（叶子→根）。")
print("递归返回时 depth-- 撤销当前结点，实现回溯，避免路径污染。")

print("(3) 算法代码实现:")
print("""
void LeafToRootPath(BiTree root) {
    ElemType path[MAX_DEPTH];
    int depth = 0;
    DFS_Path(root, path, &depth);
}

void DFS_Path(BiTree node, ElemType path[], int *depth) {
    if (node == NULL) return;

    path[*depth] = node->data;
    (*depth)++;

    if (node->lchild == NULL && node->rchild == NULL) {
        // 叶子结点：逆序输出 path[*depth-1] ... path[0]
        for (int i = *depth - 1; i >= 0; i--) {
            printf("%c", path[i]);
            if (i > 0) printf(" -> ");
        }
        printf("\\n");
    } else {
        DFS_Path(node->lchild, path, depth);
        DFS_Path(node->rchild, path, depth);
    }

    (*depth)--;  // 回溯：撤销当前结点
}
""")

# ========== 5. 验证段（对照通过条件）==========
print("\n=== 验证 ===")

# 条件1: 叶子结点判定正确（lchild==NULL && rchild==NULL）
# 树1中叶子为 D, E, F（3个），退化树中叶子为 D（1个）
assert len(results1) == 3, f"条件1失败: 树1应有3条路径，实际{len(results1)}"
assert len(results4) == 1, f"条件1失败: 退化树应有1条路径，实际{len(results4)}"
print("✓ 条件1: 叶子结点判定正确（路径数=叶子数）")

# 条件2: 回溯撤销路径（通过路径长度验证——每条路径长度应等于对应叶子深度）
# 树1: D深度3, E深度3, F深度3
for p in results1:
    assert len(p) == 3, f"条件2失败: 路径长度异常 {p}"
print("✓ 条件2: 回溯正确（路径长度=结点深度）")

# 条件3: 路径输出方向（叶子→根）
assert results1[0][0] in ('D', 'E', 'F'), f"条件3失败: 首元素应为叶子 {results1[0]}"
assert results1[0][-1] == 'A', f"条件3失败: 末元素应为根 {results1[0]}"
print("✓ 条件3: 路径方向正确（叶子→根）")

# 条件4: 边界条件
assert len(results3) == 0, "条件4失败: 空树应无路径"
assert len(results2) == 1, "条件4失败: 单结点树应有1条路径"
assert results2[0] == ['X'], f"条件4失败: 单结点路径应为['X']，实际{results2[0]}"
print("✓ 条件4: 边界条件处理正确（空树/单结点）")

# 条件5: 路径完整性（路径数=叶子数，每条路径包含所有结点）
# 树1: 3个叶子→3条路径，每条3个结点
assert len(results1) == 3, "条件5失败: 路径数≠叶子数"
for p in results1:
    assert set(p) <= {'A', 'B', 'C', 'D', 'E', 'F'}, f"条件5失败: 路径含非法结点 {p}"
    assert 'A' in p, f"条件5失败: 路径不含根 {p}"
print("✓ 条件5: 路径完整性正确")

print("\n所有验证通过 ✓")
