"""
建模：删除单链表中所有值为 x 的结点
模拟 DeleteX 算法执行过程，验证通过条件
"""

class LinkNode:
    """单链表结点类型"""
    def __init__(self, data=0):
        self.data = data
        self.next = None

def build_linked_list(values):
    """构建带头结点的单链表"""
    head = LinkNode()  # 头结点，data 无意义
    curr = head
    for v in values:
        new_node = LinkNode(v)
        curr.next = new_node
        curr = new_node
    return head

def get_list_values(head):
    """获取链表中所有数据结点的值（跳过头结点）"""
    values = []
    curr = head.next
    while curr is not None:
        values.append(curr.data)
        curr = curr.next
    return values

def count_consecutive_x(values, x):
    """统计连续两个结点 data 值均为 x 的对数"""
    count = 0
    for i in range(len(values) - 1):
        if values[i] == x and values[i + 1] == x:
            count += 1
    return count

def DeleteX(head, x):
    """
    删除单链表中所有值为 x 的结点
    算法思想：
    1. 从头结点开始遍历，用 p 指向当前结点，q 指向 p 的下一个结点
    2. 若 q 的 data 等于 x，则删除 q（p->next = q->next，释放 q）
    3. 若 q 的 data 不等于 x，则 p 后移（p = q）
    4. q 始终指向 p 的下一个结点，继续遍历
    5. 直到 q 为空
    """
    deleted_count = 0
    p = head  # p 始终指向已确认保留的最后一个结点
    
    while p.next is not None:
        q = p.next
        if q.data == x:
            # 删除 q 结点
            p.next = q.next
            # 模拟释放内存（Python 中通过断开引用实现）
            q.next = None
            deleted_count += 1
            # 注意：p 不后移，因为 p.next 现在是新的待检查结点
            # 这样可以正确处理连续删除的情况
        else:
            # q 不是目标结点，p 后移
            p = q
    
    return deleted_count

def main():
    # 参数
    initial_values = [12, 8, 8, 15, 23, 8, 31, 42]
    x = 8
    expected_remaining = [12, 15, 23, 31, 42]
    
    print("PARAMS")
    print(f"初始链表: {initial_values}")
    print(f"待删除值 x: {x}")
    print(f"链表长度: {len(initial_values)}")
    print()
    
    # 验证条件2：连续删除场景触发
    consecutive_pairs = count_consecutive_x(initial_values, x)
    print(f"REASONING")
    print(f"初始链表中连续两个结点 data 值均为 {x} 的对数: {consecutive_pairs}")
    
    # 构建链表
    head = build_linked_list(initial_values)
    
    # 执行删除
    deleted_count = DeleteX(head, x)
    
    # 获取删除后的链表
    remaining_values = get_list_values(head)
    
    print(f"删除的结点数量: {deleted_count}")
    print(f"删除后的链表: {remaining_values}")
    print()
    
    # 验证通过条件
    print("ANSWER")
    print(f"删除后的链表数据依次为: {remaining_values}")
    print(f"共保留 {len(remaining_values)} 个结点")
    print(f"共删除 {deleted_count} 个结点")
    
    # === 验证段：将通过条件翻译为 assert ===
    
    # 条件1：删除完整性 —— 链表中不存在 data=8 的结点
    assert x not in remaining_values, f"条件1失败：链表中仍存在值为 {x} 的结点"
    
    # 条件2：连续删除场景触发 —— 初始链表存在至少连续两个结点 data=x
    assert consecutive_pairs >= 1, f"条件2失败：初始链表中不存在连续两个结点 data 值均为 {x}"
    
    # 条件3：非目标结点保留 —— 保留结点为 [12, 15, 23, 31, 42]，顺序不变，共5个
    assert remaining_values == expected_remaining, f"条件3失败：期望 {expected_remaining}，实际 {remaining_values}"
    assert len(remaining_values) == 5, f"条件3失败：期望保留5个结点，实际 {len(remaining_values)}"
    
    # 条件4：内存释放 —— 被删除的3个结点均被正确释放
    assert deleted_count == 3, f"条件4失败：期望删除3个结点，实际删除 {deleted_count} 个"
    
    print()
    print("所有通过条件验证通过 ✓")

if __name__ == "__main__":
    main()
