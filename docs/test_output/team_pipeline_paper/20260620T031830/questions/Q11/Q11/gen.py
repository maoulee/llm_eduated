def solve(postorder, inorder):
    """
    根据后序遍历和中序遍历还原二叉树，返回先序遍历序列
    """
    inorder_map = {val: i for i, val in enumerate(inorder)}

    def build(post_start, post_end, in_start, in_end, depth=1):
        if post_start > post_end or in_start > in_end:
            return [], 0, 0

        root = postorder[post_end]
        in_root = inorder_map[root]
        left_size = in_root - in_start

        left_preorder, left_height, left_depth = build(
            post_start, post_start + left_size - 1,
            in_start, in_root - 1,
            depth + 1
        )
        right_preorder, right_height, right_depth = build(
            post_start + left_size, post_end - 1,
            in_root + 1, in_end,
            depth + 1
        )

        preorder = [root] + left_preorder + right_preorder
        height = 1 + max(left_height, right_height)
        max_depth = max(depth, left_depth, right_depth)

        return preorder, height, max_depth

    preorder, height, max_depth = build(0, len(postorder) - 1, 0, len(inorder) - 1)
    return preorder, height, max_depth


# ==================== 注入参数 ====================
postorder = ['A', 'C', 'B', 'E', 'G', 'F', 'D']
inorder = ['A', 'B', 'C', 'D', 'E', 'F', 'G']

preorder, height, max_depth = solve(postorder, inorder)

# 计算根节点及左右子树节点数
root = postorder[-1]
in_root = inorder.index(root)
left_count = in_root
right_count = len(inorder) - in_root - 1

# ==================== 打印结果 ====================
print(f"后序遍历: {' '.join(postorder)}")
print(f"中序遍历: {' '.join(inorder)}")
print(f"先序遍历: {' '.join(preorder)}")
print(f"树高: {height}")
print(f"递归深度: {max_depth}")
print(f"根节点: {root}")
print(f"左子树节点数: {left_count}")
print(f"右子树节点数: {right_count}")

# ==================== 通过条件验证（assert） ====================

# 1. 唯一确定性：后序和中序能唯一确定一棵二叉树
assert len(postorder) == len(inorder), "后序和中序长度不同"
assert set(postorder) == set(inorder), "后序和中序元素集合不同"

# 2. 结构非退化：树高 H ∈ [3, 4]，左右子树均非空
assert 3 <= height <= 4, f"树高 {height} 不在 [3, 4] 范围内"
assert left_count > 0 and right_count > 0, "左右子树应均非空"
assert left_count == 3, f"左子树应有3个节点，实际为{left_count}"
assert right_count == 3, f"右子树应有3个节点，实际为{right_count}"

# 3. 先序序列可机检：长度为7、包含全部7个节点各一次
assert len(preorder) == 7, f"先序序列长度应为7，实际为{len(preorder)}"
assert len(set(preorder)) == 7, "先序序列应包含全部7个节点各一次"

# 4. 考点被触发：至少涉及3层递归
assert max_depth >= 3, f"递归深度应为至少3层，实际为{max_depth}层"

print("\n所有通过条件验证通过！")
