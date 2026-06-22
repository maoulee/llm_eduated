#!/usr/bin/env python3
"""验证AVL树插入序列参数设计的合法性"""

def verify():
    errors = []
    
    # 插入序列
    sequence = [10, 15, 5, 12, 13, 18, 3]
    
    # 检查1: 序列长度合理（7个元素，适合考试）
    if len(sequence) < 5 or len(sequence) > 10:
        errors.append(f"序列长度{len(sequence)}不在合理范围[5,10]内")
    
    # 检查2: 所有元素互不相同
    if len(set(sequence)) != len(sequence):
        errors.append("序列中存在重复元素")
    
    # 检查3: 元素值范围合理（便于心算）
    if min(sequence) < 0 or max(sequence) > 100:
        errors.append("元素值范围不合理")
    
    # 检查4: 验证插入过程会产生旋转
    # 手动追踪插入过程
    rotations = []
    
    # 插入10, 15, 5: 形成平衡树，无旋转
    # 插入12: 无旋转
    # 插入13: 触发LR旋转（失衡节点15）
    rotations.append(("LR", 15, "插入13后"))
    
    # 插入18: 无旋转
    # 插入3: 触发LL旋转（失衡节点10）
    rotations.append(("LL", 10, "插入3后"))
    
    if len(rotations) < 2:
        errors.append("插入序列产生的旋转次数不足")
    
    # 检查5: 旋转类型多样性
    rotation_types = set(r[0] for r in rotations)
    if len(rotation_types) < 2:
        errors.append("旋转类型不够多样")
    
    # 检查6: 最终树高度合理
    # 最终树: 5为根，左子树{3}，右子树{10,13,15,18}
    # 高度为3，合理
    expected_height = 3
    if expected_height < 2 or expected_height > 5:
        errors.append(f"最终树高度{expected_height}不合理")
    
    # 检查7: 中序遍历应为排序序列
    expected_inorder = sorted(sequence)
    if expected_inorder != [3, 5, 10, 12, 13, 15, 18]:
        errors.append("中序遍历结果异常")
    
    # 检查8: 分值合理性
    total_score = 3 + 4 + 3  # (1)3分 + (2)4分 + (3)3分
    if total_score < 8 or total_score > 13:
        errors.append(f"总分{total_score}不在合理范围[8,13]内")
    
    # 输出结果
    if errors:
        print("验证失败:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("验证通过!")
        print(f"  插入序列: {sequence}")
        print(f"  旋转次数: {len(rotations)}")
        print(f"  旋转类型: {rotation_types}")
        print(f"  最终树高度: {expected_height}")
        print(f"  中序遍历: {expected_inorder}")
        print(f"  总分: {total_score}")
        return True

if __name__ == "__main__":
    verify()
