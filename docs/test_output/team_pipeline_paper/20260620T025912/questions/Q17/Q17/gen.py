"""
删除单链表中所有值为 x 的结点 - 建模验证代码
"""

class LinkNode:
    """单链表结点"""
    def __init__(self, data=0):
        self.data = data
        self.next = None

class LinkedList:
    """带头结点的单链表"""
    def __init__(self):
        self.head = LinkNode()  # 头结点，data 无意义
    
    def append(self, data):
        """尾插法添加结点"""
        p = self.head
        while p.next:
            p = p.next
        p.next = LinkNode(data)
    
    def to_list(self):
        """将链表转为 Python list（不含头结点）"""
        result = []
        p = self.head.next
        while p:
            result.append(p.data)
            p = p.next
        return result
    
    def __repr__(self):
        return f"LinkedList({self.to_list()})"


def DeleteAll(L, x):
    """
    删除带头结点单链表 L 中所有 data == x 的结点
    模拟 C/C++ 实现逻辑
    """
    # 用 prev 指向当前结点的前驱
    prev = L.head
    curr = L.head.next
    freed_count = 0
    
    while curr:
        if curr.data == x:
            # 删除 curr 结点
            prev.next = curr.next
            # 模拟 free(curr)
            freed_count += 1
            curr = prev.next  # curr 移到下一个结点
        else:
            prev = curr
            curr = curr.next
    
    return freed_count


def test_correctness():
    """通过条件1：正确性 - 执行后链表中不存在 data == x 的结点"""
    print("=" * 60)
    print("测试1：正确性 - 执行后链表中不存在 data == x 的结点")
    print("=" * 60)
    
    # 测试用例1：普通链表
    ll = LinkedList()
    for val in [1, 2, 3, 2, 4, 2, 5]:
        ll.append(val)
    print(f"删除前: {ll.to_list()}")
    freed = DeleteAll(ll, 2)
    result = ll.to_list()
    print(f"删除后: {result}")
    assert 2 not in result, f"正确性失败：链表中仍存在值为2的结点: {result}"
    assert freed == 3, f"应删除3个结点，实际删除{freed}个"
    print("✓ 测试用例1通过\n")
    
    # 测试用例2：不同值
    ll = LinkedList()
    for val in [10, 20, 30, 40, 50]:
        ll.append(val)
    freed = DeleteAll(ll, 30)
    result = ll.to_list()
    assert 30 not in result, f"正确性失败：链表中仍存在值为30的结点"
    print("✓ 测试用例2通过\n")


def test_head_protection():
    """通过条件2：头结点保护 - 头结点始终保留"""
    print("=" * 60)
    print("测试2：头结点保护 - 头结点始终保留")
    print("=" * 60)
    
    ll = LinkedList()
    for val in [1, 2, 3]:
        ll.append(val)
    
    # 头结点存在
    assert ll.head is not None, "头结点不存在"
    head_id = id(ll.head)
    
    freed = DeleteAll(ll, 2)
    
    # 删除后头结点仍存在且是同一个对象
    assert ll.head is not None, "删除后头结点不存在"
    assert id(ll.head) == head_id, "头结点被替换了"
    print(f"删除后链表: {ll.to_list()}")
    print("✓ 头结点保护测试通过\n")


def test_consecutive_values():
    """通过条件3：连续值处理 - 连续多个值为 x 的结点全部被正确删除"""
    print("=" * 60)
    print("测试3：连续值处理 - 连续多个值为 x 的结点全部被正确删除")
    print("=" * 60)
    
    # 测试用例1：连续多个 x
    ll = LinkedList()
    for val in [1, 2, 2, 2, 2, 3]:
        ll.append(val)
    print(f"删除前: {ll.to_list()}")
    freed = DeleteAll(ll, 2)
    result = ll.to_list()
    print(f"删除后: {result}")
    assert 2 not in result, f"连续值处理失败：链表中仍存在值为2的结点: {result}"
    assert freed == 4, f"应删除4个结点，实际删除{freed}个"
    print("✓ 测试用例1通过\n")
    
    # 测试用例2：开头连续
    ll = LinkedList()
    for val in [5, 5, 5, 1, 2]:
        ll.append(val)
    freed = DeleteAll(ll, 5)
    result = ll.to_list()
    assert 5 not in result, f"开头连续值处理失败"
    assert freed == 3, f"应删除3个结点，实际删除{freed}个"
    print("✓ 测试用例2通过\n")
    
    # 测试用例3：结尾连续
    ll = LinkedList()
    for val in [1, 2, 3, 7, 7, 7]:
        ll.append(val)
    freed = DeleteAll(ll, 7)
    result = ll.to_list()
    assert 7 not in result, f"结尾连续值处理失败"
    assert freed == 3, f"应删除3个结点，实际删除{freed}个"
    print("✓ 测试用例3通过\n")


def test_memory_free():
    """通过条件4：内存释放 - 每个被删除的结点均调用 free() 释放内存"""
    print("=" * 60)
    print("测试4：内存释放 - 每个被删除的结点均调用 free() 释放内存")
    print("=" * 60)
    
    # 通过 freed_count 统计删除的结点数量
    ll = LinkedList()
    for val in [1, 2, 3, 2, 4, 2]:
        ll.append(val)
    
    # 统计链表中值为2的结点数量
    count_x = ll.to_list().count(2)
    print(f"链表中值为2的结点数量: {count_x}")
    
    freed = DeleteAll(ll, 2)
    print(f"DeleteAll 返回的 freed_count: {freed}")
    
    # freed_count 应等于链表中值为 x 的结点数量
    assert freed == count_x, f"内存释放失败：应释放{count_x}个结点，实际释放{freed}个"
    print("✓ 内存释放测试通过\n")


def test_boundary_cases():
    """通过条件5：边界情况 - 空链表、全为 x 的链表、无 x 的链表均能正确处理"""
    print("=" * 60)
    print("测试5：边界情况处理")
    print("=" * 60)
    
    # 边界1：空链表（仅头结点）
    ll = LinkedList()
    print(f"空链表删除前: {ll.to_list()}")
    freed = DeleteAll(ll, 5)
    result = ll.to_list()
    print(f"空链表删除后: {result}")
    assert result == [], f"空链表处理失败：期望[]，得到{result}"
    assert freed == 0, f"空链表应删除0个结点，实际删除{freed}个"
    assert ll.head is not None, "空链表头结点丢失"
    print("✓ 边界1：空链表通过\n")
    
    # 边界2：全为 x 的链表
    ll = LinkedList()
    for val in [3, 3, 3, 3]:
        ll.append(val)
    print(f"全为x链表删除前: {ll.to_list()}")
    freed = DeleteAll(ll, 3)
    result = ll.to_list()
    print(f"全为x链表删除后: {result}")
    assert result == [], f"全为x链表处理失败：期望[]，得到{result}"
    assert freed == 4, f"应删除4个结点，实际删除{freed}个"
    assert ll.head is not None, "全为x链表头结点丢失"
    print("✓ 边界2：全为x链表通过\n")
    
    # 边界3：无 x 的链表
    ll = LinkedList()
    for val in [1, 2, 3, 4, 5]:
        ll.append(val)
    print(f"无x链表删除前: {ll.to_list()}")
    freed = DeleteAll(ll, 99)
    result = ll.to_list()
    print(f"无x链表删除后: {result}")
    assert result == [1, 2, 3, 4, 5], f"无x链表处理失败：期望[1,2,3,4,5]，得到{result}"
    assert freed == 0, f"应删除0个结点，实际删除{freed}个"
    print("✓ 边界3：无x链表通过\n")


def main():
    print("\n" + "=" * 60)
    print("删除单链表中所有值为 x 的结点 - 算法验证")
    print("=" * 60 + "\n")
    
    test_correctness()
    test_head_protection()
    test_consecutive_values()
    test_memory_free()
    test_boundary_cases()
    
    print("=" * 60)
    print("所有测试通过！算法实现满足所有通过条件。")
    print("=" * 60)


if __name__ == "__main__":
    main()
