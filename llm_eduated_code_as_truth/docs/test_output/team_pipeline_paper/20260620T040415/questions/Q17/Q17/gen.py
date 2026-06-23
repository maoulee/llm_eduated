"""
gen.py - 删除带头结点单链表中所有值为x的结点
模拟算法执行过程，验证通过条件
"""

# ========== PARAMS ==========
# 测试用例1：普通情况，含连续匹配
# 链表: 1 -> 3 -> 3 -> 2 -> 3 -> 4 -> 5, x = 3
# 期望: 1 -> 2 -> 4 -> 5
PARAMS = {
    "test_cases": [
        {
            "name": "空表",
            "data": [],
            "x": 3,
            "expected": []
        },
        {
            "name": "全匹配",
            "data": [3, 3, 3],
            "x": 3,
            "expected": []
        },
        {
            "name": "无匹配",
            "data": [1, 2, 4, 5],
            "x": 3,
            "expected": [1, 2, 4, 5]
        },
        {
            "name": "首元匹配",
            "data": [3, 1, 2],
            "x": 3,
            "expected": [1, 2]
        },
        {
            "name": "连续匹配",
            "data": [1, 3, 3, 2, 3, 4, 5],
            "x": 3,
            "expected": [1, 2, 4, 5]
        },
        {
            "name": "尾元匹配",
            "data": [1, 2, 3],
            "x": 3,
            "expected": [1, 2]
        },
        {
            "name": "单结点匹配",
            "data": [3],
            "x": 3,
            "expected": []
        },
        {
            "name": "单结点不匹配",
            "data": [1],
            "x": 3,
            "expected": [1]
        }
    ]
}

# ========== 结点定义 ==========
class LNode:
    """带头结点单链表的结点类型"""
    def __init__(self, data=0):
        self.data = data
        self.next = None

# ========== 工具函数 ==========
def create_list(data_list):
    """创建带头结点的单链表"""
    head = LNode()  # 头结点
    tail = head
    for d in data_list:
        new_node = LNode(d)
        tail.next = new_node
        tail = new_node
    return head

def get_list_data(L):
    """从带头结点链表提取data列表"""
    result = []
    p = L.next  # 跳过头结点
    while p is not None:
        result.append(p.data)
        p = p.next
    return result

def check_integrity(L):
    """检查链表结构完整性：从L->next能遍历到NULL，无断裂"""
    p = L.next
    visited = set()
    while p is not None:
        if id(p) in visited:
            return False  # 环
        visited.add(id(p))
        p = p.next
    return True

# ========== 算法实现 ==========
def delete_all_x(L, x):
    """
    删除带头结点单链表L中所有值为x的结点
    
    算法思想：
    使用双指针p和q，p指向当前待检查结点的前驱，q指向当前待检查结点。
    遍历链表，若q->data == x，则删除q结点（p->next = q->next，释放q），q指向p->next；
    否则p、q同时后移。
    头结点L本身不参与比较，始终保留。
    """
    freed_count = 0  # 记录释放的结点数（模拟内存释放）
    
    p = L  # p指向头结点（首元结点的前驱）
    q = L.next  # q指向首元结点
    
    while q is not None:
        if q.data == x:
            # 删除q结点
            p.next = q.next
            # free(q) - 模拟内存释放
            freed_count += 1
            q = p.next  # q指向下一个待检查结点
        else:
            p = q
            q = q.next
    
    return freed_count

# ========== REASONING ==========
print("=== REASONING ===")
print("算法核心思想：双指针遍历法")
print("p指向待检查结点的前驱，q指向待检查结点")
print("若q->data==x：删除q（p->next=q->next），q=p->next")
print("否则：p=q, q=q.next")
print("头结点L始终保留，不参与比较")
print()

# ========== 验证 ==========
print("=== 验证通过条件 ===")
all_pass = True

for tc in PARAMS["test_cases"]:
    name = tc["name"]
    data = tc["data"]
    x = tc["x"]
    expected = tc["expected"]
    
    # 创建链表
    L = create_list(data)
    
    # 条件1：空表处理（data为空时L->next==NULL）
    if len(data) == 0:
        assert L.next is None, f"[{name}] 空表条件1失败：L->next应为NULL"
    
    # 执行算法
    freed = delete_all_x(L, x)
    
    # 条件2：正确性 - 删除后不存在值为x的结点
    result = get_list_data(L)
    assert x not in result, f"[{name}] 条件2失败：结果中仍存在值为{x}的结点，结果={result}"
    
    # 条件3：结构完整性
    assert check_integrity(L), f"[{name}] 条件3失败：链表结构断裂"
    
    # 条件4：头结点保护 - L本身存在，L->next指向正确
    assert L is not None, f"[{name}] 条件4失败：头结点被删除"
    assert result == expected, f"[{name}] 条件4失败：期望{expected}，实际{result}"
    
    # 条件5：内存释放 - 被删除的结点数量正确
    expected_freed = len(data) - len(expected)
    assert freed == expected_freed, f"[{name}] 条件5失败：应释放{expected_freed}个结点，实际释放{freed}个"
    
    print(f"  [{name}] PASS: {data} -> {result} (x={x}, freed={freed})")

print()
print("所有测试用例通过 ✓")

# 额外验证：连续匹配场景（K4=3边界陷阱）
print("=== 边界条件验证 ===")
L = create_list([3, 3, 3, 1, 2])
freed = delete_all_x(L, 3)
result = get_list_data(L)
assert result == [1, 2], f"连续首元匹配失败：{result}"
assert freed == 3, f"连续释放计数失败：{freed}"
print("  连续首元匹配：PASS")

L = create_list([1, 3, 3, 3, 2])
freed = delete_all_x(L, 3)
result = get_list_data(L)
assert result == [1, 2], f"连续中间匹配失败：{result}"
assert freed == 3, f"连续释放计数失败：{freed}"
print("  连续中间匹配：PASS")

L = create_list([1, 2, 3, 3, 3])
freed = delete_all_x(L, 3)
result = get_list_data(L)
assert result == [1, 2], f"连续尾元匹配失败：{result}"
assert freed == 3, f"连续释放计数失败：{freed}"
print("  连续尾元匹配：PASS")

print()
print("边界条件验证通过 ✓")

# ========== ANSWER ==========
print("=== ANSWER ===")
print()
print("Q1 结点类型定义：")
print("""
typedef struct LNode {
    int data;              // 数据域
    struct LNode *next;    // 指针域
} LNode, *LinkList;
""")
print()
print("Q2 算法基本思想：")
print("""
使用双指针p和q遍历链表。p始终指向当前待检查结点的前驱，q指向当前待检查结点。
初始化p指向头结点L，q指向首元结点L->next。
遍历过程中：
  - 若q->data == x，则删除q结点：令p->next = q->next，释放q的内存，q指向p->next（p不动）；
  - 若q->data != x，则p和q同时后移一位。
遍历结束后，链表中所有值为x的结点均被删除。
头结点L本身不参与比较，始终保留。
""")
print()
print("Q3 算法代码：")
print("""
void DeleteX(LinkList L, int x) {
    LNode *p = L;        // p指向头结点（待检查结点的前驱）
    LNode *q = L->next;  // q指向首元结点（待检查结点）
    
    while (q != NULL) {
        if (q->data == x) {
            // 删除q结点
            p->next = q->next;  // 前驱指向q的下一个结点
            free(q);            // 释放q的内存
            q = p->next;        // q指向下一个待检查结点
        } else {
            // 不删除，双指针后移
            p = q;
            q = q->next;
        }
    }
}
""")
