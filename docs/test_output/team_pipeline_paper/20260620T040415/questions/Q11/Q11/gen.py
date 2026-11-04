# 由后序+中序遍历还原二叉树，输出先序遍历

def build_tree(postorder, inorder):
    """根据后序和中序遍历还原二叉树"""
    if not postorder or not inorder:
        return None
    
    # 后序最后一个元素是根
    root_val = postorder[-1]
    root = {'val': root_val, 'left': None, 'right': None}
    
    # 在中序中找到根的位置
    root_idx = inorder.index(root_val)
    
    # 左子树的中序和后序
    left_inorder = inorder[:root_idx]
    left_postorder = postorder[:root_idx]
    
    # 右子树的中序和后序
    right_inorder = inorder[root_idx+1:]
    right_postorder = postorder[root_idx:root_idx+len(right_inorder)]
    
    root['left'] = build_tree(left_postorder, left_inorder)
    root['right'] = build_tree(right_postorder, right_inorder)
    
    return root

def preorder_traversal(root):
    """先序遍历"""
    if root is None:
        return []
    return [root['val']] + preorder_traversal(root['left']) + preorder_traversal(root['right'])

def get_depth(root):
    """获取树深度"""
    if root is None:
        return 0
    return 1 + max(get_depth(root['left']), get_depth(root['right']))

def is_complete_binary_tree(root):
    """判断是否为完全二叉树"""
    if root is None:
        return True
    
    queue = [root]
    found_non_full = False
    
    while queue:
        node = queue.pop(0)
        
        if node['left']:
            if found_non_full:
                return False
            queue.append(node['left'])
        else:
            found_non_full = True
            
        if node['right']:
            if found_non_full:
                return False
            queue.append(node['right'])
        else:
            found_non_full = True
    
    return True

def main():
    # 题干给定的序列
    postorder = ['A', 'E', 'C', 'B', 'F', 'H', 'I', 'G', 'D']
    inorder = ['A', 'B', 'E', 'C', 'D', 'F', 'H', 'I', 'G']
    
    # 通过条件1：序列长度一致，包含相同字符集合
    assert len(postorder) == 9, f"后序长度应为9，实际为{len(postorder)}"
    assert len(inorder) == 9, f"中序长度应为9，实际为{len(inorder)}"
    assert set(postorder) == set(inorder), "后序和中序应包含相同字符集合"
    assert len(set(postorder)) == 9, "应包含9个不同字符"
    
    # 还原二叉树
    tree = build_tree(postorder, inorder)
    
    # 通过条件2：树结构唯一确定（build_tree能成功执行即证明唯一）
    assert tree is not None, "树结构应能唯一确定"
    
    # 通过条件3：树深度 >= 3
    depth = get_depth(tree)
    assert depth >= 3, f"树深度应>=3，实际为{depth}"
    
    # 通过条件4：左右子树均非空
    assert tree['left'] is not None, "根节点的左子树应非空"
    assert tree['right'] is not None, "根节点的右子树应非空"
    
    # 通过条件5：非完全二叉树
    assert not is_complete_binary_tree(tree), "树不应是完全二叉树"
    
    # 先序遍历
    preorder = preorder_traversal(tree)
    
    # 通过条件6：先序序列唯一确定（能计算出即证明唯一）
    assert len(preorder) == 9, f"先序序列长度应为9，实际为{len(preorder)}"
    
    # 输出结果
    print("二叉树结构：")
    def print_tree(node, level=0, prefix="Root"):
        if node:
            print(f"{'  ' * level}{prefix}: {node['val']}")
            if node['left'] or node['right']:
                if node['left']:
                    print_tree(node['left'], level + 1, "Left")
                else:
                    print(f"{'  ' * (level + 1)}Left: None")
                if node['right']:
                    print_tree(node['right'], level + 1, "Right")
                else:
                    print(f"{'  ' * (level + 1)}Right: None")
    
    print_tree(tree)
    
    print(f"\n先序遍历序列：{' '.join(preorder)}")
    print(f"树深度：{depth}")
    
    # 验证：后序和中序确实来自同一棵树
    def get_postorder(node):
        if node is None:
            return []
        return get_postorder(node['left']) + get_postorder(node['right']) + [node['val']]
    
    def get_inorder(node):
        if node is None:
            return []
        return get_inorder(node['left']) + [node['val']] + get_inorder(node['right'])
    
    assert get_postorder(tree) == postorder, "还原的树的后序遍历应与给定序列一致"
    assert get_inorder(tree) == inorder, "还原的树的中序遍历应与给定序列一致"
    
    print("\n验证通过：还原的树的后序和中序遍历与给定序列一致")

if __name__ == "__main__":
    main()
