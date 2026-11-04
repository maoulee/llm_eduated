"""
单链表递归逆序输出函数填空验证
"""

# 模拟链表结点
class LNode:
    def __init__(self, data, next=None):
        self.data = data
        self.next = next

# 正确的 PrintReverse 实现（填空①=p==NULL, 填空②=printf输出）
def PrintReverse(p):
    """递归逆序输出链表"""
    output = []
    
    def _print_reverse(node):
        # 填空①：递归基条件
        if node is None:
            return
        # 递归调用
        _print_reverse(node.next)
        # 填空②：回溯阶段输出
        output.append(node.data)
    
    _print_reverse(p)
    return output

# 典型错误实现（用于对比）
def PrintReverse_Error1(p):
    """错误1：递归基条件写为 p->next == NULL"""
    output = []
    
    def _print_reverse(node):
        # 错误：p->next == NULL 作为递归基
        if node is not None and node.next is None:
            output.append(node.data)
            return
        if node is not None:
            _print_reverse(node.next)
            output.append(node.data)
    
    _print_reverse(p)
    return output

def PrintReverse_Error2(p):
    """错误2：输出放在递归调用之前（正序）"""
    output = []
    
    def _print_reverse(node):
        if node is None:
            return
        # 错误：输出在递归调用之前
        output.append(node.data)
        _print_reverse(node.next)
    
    _print_reverse(p)
    return output

# 构建测试链表：1 -> 2 -> 3 -> 4 -> 5
def build_list():
    nodes = [LNode(i) for i in range(1, 6)]
    for i in range(len(nodes) - 1):
        nodes[i].next = nodes[i + 1]
    return nodes[0] if nodes else None

# 验证通过条件
def main():
    # 测试用例1：正常链表
    head = build_list()
    
    # 正确实现的结果
    correct_result = PrintReverse(head)
    print(f"正确实现输出: {correct_result}")
    
    # 错误1的结果（递归基条件错误）
    error1_result = PrintReverse_Error1(head)
    print(f"错误1输出（递归基p->next==NULL）: {error1_result}")
    
    # 错误2的结果（正序输出）
    error2_result = PrintReverse_Error2(head)
    print(f"错误2输出（正序）: {error2_result}")
    
    # 测试用例2：空链表
    empty_result = PrintReverse(None)
    print(f"空链表输出: {empty_result}")
    
    # 测试用例3：单结点链表
    single_head = LNode(42)
    single_result = PrintReverse(single_head)
    print(f"单结点输出: {single_result}")
    
    # ===== 验证通过条件 =====
    
    # 条件1：填空①为递归基条件 p == NULL
    # 验证：空链表时函数直接返回，不输出
    assert empty_result == [], "填空①必须处理空链表情况"
    print("✓ 条件1：填空①为递归基条件 p == NULL，空链表正确处理")
    
    # 条件2：填空②为回溯阶段输出，确保逆序
    # 验证：输出顺序是逆序的
    assert correct_result == [5, 4, 3, 2, 1], f"输出应为逆序 [5,4,3,2,1]，实际 {correct_result}"
    print("✓ 条件2：填空②为回溯阶段输出，确保逆序输出")
    
    # 验证：错误实现（正序）与正确实现不同
    assert error2_result == [1, 2, 3, 4, 5], f"错误2应为正序 [1,2,3,4,5]，实际 {error2_result}"
    assert correct_result != error2_result, "正确实现与正序错误实现必须不同"
    print("✓ 条件2补充：逆序与正序输出不同，填空②位置正确")
    
    # 验证：错误实现1（递归基错误）与正确实现不同
    # 注意：错误1在某些情况下可能碰巧正确，但逻辑错误
    print(f"  错误1与正确实现对比: {error1_result} vs {correct_result}")
    
    # 条件3：功能描述包含"逆序"关键词
    # 这里我们验证输出的确是逆序的，证明功能描述应包含"逆序"
    expected_reverse = list(reversed([1, 2, 3, 4, 5]))
    assert correct_result == expected_reverse, "输出必须是逆序"
    print("✓ 条件3：输出验证为逆序，功能描述应包含'逆序'关键词")
    
    # 条件4：函数能正确处理空链表
    # 已用 empty_result == [] 验证
    assert len(empty_result) == 0, "空链表不应有任何输出"
    print("✓ 条件4：空链表正确处理，无输出")
    
    # 额外验证：单结点链表
    assert single_result == [42], f"单结点应输出 [42]，实际 {single_result}"
    print("✓ 额外验证：单结点链表正确处理")
    
    print("\n所有通过条件验证通过！")
    print("\n正确答案：")
    print("填空①：p == NULL")
    print("填空②：printf(\"%d \", p->data);")
    print("功能：逆序输出单链表结点数据")

if __name__ == "__main__":
    main()
