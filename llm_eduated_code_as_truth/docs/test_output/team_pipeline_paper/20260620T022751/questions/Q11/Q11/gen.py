def solve(postorder, inorder):
    """
    由后序+中序遍历序列还原二叉树，输出先序遍历序列。
    返回 (tree, preorder_seq, recursion_count)
    """
    recursion_count = [0]

    def build(post, ino):
        recursion_count[0] += 1
        if not post:
            return None
        root = post[-1]
        idx = ino.index(root)
        left_ino = ino[:idx]
        right_ino = ino[idx + 1:]
        left_post = post[:len(left_ino)]
        right_post = post[len(left_ino):-1]
        node = {
            'val': root,
            'left': build(left_post, left_ino),
            'right': build(right_post, right_ino),
        }
        return node

    tree = build(list(postorder), list(inorder))

    def preorder(node):
        if node is None:
            return []
        return [node['val']] + preorder(node['left']) + preorder(node['right'])

    def inorder_traverse(node):
        if node is None:
            return []
        return inorder_traverse(node['left']) + [node['val']] + inorder_traverse(node['right'])

    def postorder_traverse(node):
        if node is None:
            return []
        return postorder_traverse(node['left']) + postorder_traverse(node['right']) + [node['val']]

    pre_seq = preorder(tree)
    return tree, pre_seq, recursion_count[0]


# ==================== 注入参数 ====================
postorder = ['A', 'C', 'B', 'F', 'G', 'E', 'D']
inorder = ['A', 'B', 'C', 'D', 'E', 'F', 'G']

tree, preorder_seq, rec_count = solve(postorder, inorder)

# ==================== 输出推理过程 ====================
print("PARAMS")
print(f"后序: {' '.join(postorder)}")
print(f"中序: {' '.join(inorder)}")

print("\nREASONING")
print(f"根节点: {postorder[-1]}")
print(f"递归步数: {rec_count}")

# 打印树结构
def print_tree(node, indent=0):
    if node is None:
        return
    prefix = "  " * indent
    print(f"{prefix}[{node['val']}]")
    print(f"{prefix}  left -> ", end="")
    if node['left']:
        print(node['left']['val'])
        print_tree(node['left'], indent + 2)
    else:
        print("空")
    print(f"{prefix}  right -> ", end="")
    if node['right']:
        print(node['right']['val'])
        print_tree(node['right'], indent + 2)
    else:
        print("空")

print("\n二叉树结构:")
print_tree(tree)

# ==================== 输出答案 ====================
print("\nANSWER")
print(f"先序遍历序列: {' '.join(preorder_seq)}")

# ==================== 验证段（通过条件 → assert） ====================
print("\n--- 验证 ---")

# 条件1: 唯一还原 —— 算法对给定输入只产生一棵树（确定性算法，天然唯一）
# 条件2: 一致性 —— 还原出的树，其中序/后序遍历必须与输入一致
reconstructed_inorder = inorder_traverse(tree)
reconstructed_postorder = postorder_traverse(tree)
assert reconstructed_inorder == inorder, f"中序不一致: {reconstructed_inorder} != {inorder}"
assert reconstructed_postorder == postorder, f"后序不一致: {reconstructed_postorder} != {postorder}"
print(f"✓ 一致性: 中序={reconstructed_inorder}, 后序={reconstructed_postorder}")

# 条件3: 递归步数 > 5
assert rec_count > 5, f"递归步数 {rec_count} 未超过 5"
print(f"✓ 递归步数: {rec_count} > 5")

# 条件4: 先序序列唯一确定，长度7，包含A~G各恰好一次
assert len(preorder_seq) == 7, f"先序长度应为7，实际{len(preorder_seq)}"
assert len(set(preorder_seq)) == 7, f"先序应有7个不同节点"
assert set(preorder_seq) == set('ABCDEFG'), f"先序应包含A~G"
print(f"✓ 先序序列: {' '.join(preorder_seq)} (长度7, 含A~G各一次)")

# 条件5: 左右子树非空
assert tree['left'] is not None, "左子树为空"
assert tree['right'] is not None, "右子树为空"
print(f"✓ 左子树根={tree['left']['val']}, 右子树根={tree['right']['val']}")

print("\n所有通过条件验证通过。")
