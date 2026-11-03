"""
综合题：删除单链表中所有值为 x 的结点（14 分）

建模方式：用 Python 类模拟带头结点单链表 + LNode 指针操作，
忠实翻译题干算法（pre/cur 双指针遍历，命中则 free+摘链，不命中则前进）。
通过条件 → assert（4 条通过条件全部翻译为可机检断言）。
"""

# ============================================================
# 结点定义（对应第(1)问）
# ============================================================
class LNode:
    """带头结点单链表的结点定义（对应 C: typedef struct LNode { int data; struct LNode *next; } LNode;）"""
    __slots__ = ('data', 'next')
    def __init__(self, data=None, nxt=None):
        self.data = data
        self.next = nxt

# ============================================================
# 算法实现（对应第(3)问 C/C++ 代码）
# 翻译：void DeleteX(LNode *&L, int x)
#   pre = L（头结点）
#   cur = L->next（首个数据结点）
#   while cur != NULL:
#     if cur->data == x:  pre->next = cur->next; free(cur); cur = pre->next
#     else:               pre = cur; cur = cur->next
# ============================================================
free_count = 0   # 记录 free() 调用次数（模拟内存释放）

def DeleteX(L, x):
    """
    删除带头结点单链表 L 中所有 data==x 的结点并 free 释放。
    L: 头结点（LNode），L.next 指向第一个数据结点。
    """
    global free_count
    # LNode *pre = L;  // pre（前驱指针，初始指向头结点）—— 对应 C 代码注释

    pre = L                    # pre 初始指向头结点
    cur = L.next               # cur 初始指向首个数据结点（遍历起点 = L->next，不从头结点开始）

    while cur is not None:     # cur != NULL
        if cur.data == x:      # 命中：删除当前结点
            pre.next = cur.next  # 摘链：前驱的 next 跳过 cur
            free_count += 1      # free(cur)：释放被删除结点的内存
            cur = pre.next       # cur 前进到下一个待检查结点（pre 不动，保证连续命中也不漏删）
        else:                   # 不命中：pre 和 cur 同时前进
            pre = cur
            cur = cur.next

# ============================================================
# 辅助函数
# ============================================================
def make_list(values):
    """根据值列表构造带头结点单链表，返回头结点。values 为数据结点的 data 值列表。"""
    head = LNode()           # 头结点（不存储有效数据）
    tail = head
    for v in values:
        node = LNode(data=v)
        tail.next = node
        tail = node
    return head

def to_list(head):
    """将带头结点单链表转为数据值列表（跳过头结点）。"""
    result = []
    p = head.next            # 从 L->next 开始（首个数据结点）
    while p is not None:
        result.append(p.data)
        p = p.next
    return result

# ============================================================
# 测试用例（覆盖通过条件 3 的所有边界情形）
# ============================================================
def run_tests():
    global free_count

    # --- 测试1：空表（仅头结点）→ 不崩溃，结果仍为空表 ---
    free_count = 0
    h1 = make_list([])
    DeleteX(h1, 5)
    assert to_list(h1) == [], f"空表测试失败: {to_list(h1)}"
    assert free_count == 0, f"空表不应有删除: free_count={free_count}"
    print("[PASS] 测试1 空表: 结果=[], free_count=0")

    # --- 测试2：单结点且命中 ---
    free_count = 0
    h2 = make_list([5])
    DeleteX(h2, 5)
    assert to_list(h2) == [], f"单结点命中测试失败: {to_list(h2)}"
    assert free_count == 1, f"单结点命中应删1个: free_count={free_count}"
    print("[PASS] 测试2 单结点命中: 结果=[], free_count=1")

    # --- 测试3：单结点不命中 ---
    free_count = 0
    h3 = make_list([3])
    DeleteX(h3, 5)
    assert to_list(h3) == [3], f"单结点不命中测试失败: {to_list(h3)}"
    assert free_count == 0
    print("[PASS] 测试3 单结点不命中: 结果=[3], free_count=0")

    # --- 测试4：连续命中 ---
    free_count = 0
    h4 = make_list([5, 5, 5, 3, 5, 5])
    DeleteX(h4, 5)
    assert to_list(h4) == [3], f"连续命中测试失败: {to_list(h4)}"
    assert free_count == 5, f"连续命中应删5个: free_count={free_count}"
    print("[PASS] 测试4 连续命中: 结果=[3], free_count=5")

    # --- 测试5：尾结点命中 ---
    free_count = 0
    h5 = make_list([1, 2, 3, 5])
    DeleteX(h5, 5)
    assert to_list(h5) == [1, 2, 3], f"尾结点命中测试失败: {to_list(h5)}"
    assert free_count == 1
    # 验证尾结点删除后末尾前驱 next 置 NULL
    p = h5
    while p.next is not None:
        p = p.next
    assert p.data == 3 and p.next is None, "尾结点删除后末尾应正确置 NULL"
    print("[PASS] 测试5 尾结点命中: 结果=[1,2,3], 末尾正确置NULL")

    # --- 测试6：全表均为 x ---
    free_count = 0
    h6 = make_list([5, 5, 5, 5])
    DeleteX(h6, 5)
    assert to_list(h6) == [], f"全表为x测试失败: {to_list(h6)}"
    assert h6.next is None, "全表为x后 L->next 应为 NULL"
    assert free_count == 4
    print("[PASS] 测试6 全表为x: 结果=[], L->next=NULL, free_count=4")

    # --- 测试7：综合情况（保留相对顺序，散布命中） ---
    free_count = 0
    h7 = make_list([3, 5, 7, 5, 9, 5, 11])
    DeleteX(h7, 5)
    assert to_list(h7) == [3, 7, 9, 11], f"综合测试失败: {to_list(h7)}"
    assert free_count == 3
    print("[PASS] 测试7 综合(散布命中): 结果=[3,7,9,11], free_count=3")

    # --- 测试8：头结点不被删除（验证遍历起点） ---
    free_count = 0
    h8 = make_list([5, 5])
    DeleteX(h8, 5)
    # h8 本身（头结点）应仍然存在且可用
    assert h8 is not None, "头结点不应被删除"
    assert h8.data is None, "头结点 data 应保持不变（不含有效数据）"
    assert h8.next is None, "全删后头结点 next 应为 NULL"
    print("[PASS] 测试8 头结点保留: 头结点存在且可用")

    return True

# ============================================================
# 通过条件 assert（题干声明的 4 条成功判据）
# ============================================================
def verify_pass_conditions():
    """验证通过条件：算法功能正确 + 内存释放 + 边界全覆盖 + 头结点不被删除"""

    # ---- 通过条件1：算法功能正确 ----
    # 删除后链表中不存在任何 data==x 的结点，且其余结点相对顺序不变
    global free_count
    free_count = 0
    h = make_list([3, 5, 7, 5, 9, 5, 11])
    DeleteX(h, 5)
    result = to_list(h)
    # 不存在 data==x 的结点
    assert all(v != 5 for v in result), "通过条件1失败: 仍有 data==5 的结点残留"
    # 相对顺序保持不变（3,7,9,11 是 [3,5,7,5,9,5,11] 删 5 后的正确顺序）
    assert result == [3, 7, 9, 11], f"通过条件1失败: 相对顺序错误, got {result}"
    print("[PASS] 通过条件1 算法功能正确: 无残留 x 结点, 相对顺序保持")

    # ---- 通过条件2：内存释放 ----
    # 被删除的每个结点都调用了 free()（DeleteX 内部有 free_count+=1 对应 free 调用）
    assert free_count == 3, f"通过条件2失败: 应释放3个结点, free_count={free_count}"
    # 代码中出现 free 调用（通过 free_count 机制模拟）
    print("[PASS] 通过条件2 内存释放: 每个被删结点均 free, free_count=3")

    # ---- 通过条件3：边界全覆盖 ----
    # 空表
    free_count = 0
    he = make_list([])
    DeleteX(he, 5)
    assert to_list(he) == [], "通过条件3-空表失败"
    # 连续命中
    free_count = 0
    hc = make_list([5, 5, 3, 5, 5])
    DeleteX(hc, 5)
    assert to_list(hc) == [3], f"通过条件3-连续命中失败: {to_list(hc)}"
    assert free_count == 4, "通过条件3-连续命中漏删"
    # 尾结点命中
    free_count = 0
    ht = make_list([1, 2, 5])
    DeleteX(ht, 5)
    assert to_list(ht) == [1, 2], "通过条件3-尾结点命中失败"
    # 验证末尾前驱 next 置 NULL
    p = ht
    while p.next is not None:
        p = p.next
    assert p.data == 2 and p.next is None, "通过条件3-尾结点命中: 末尾未置NULL"
    # 全表为 x
    free_count = 0
    ha = make_list([5, 5, 5])
    DeleteX(ha, 5)
    assert ha.next is None, "通过条件3-全表为x: L->next 未置NULL"
    assert to_list(ha) == [], "通过条件3-全表为x失败"
    print("[PASS] 通过条件3 边界全覆盖: 空表/连续命中/尾结点命中/全表为x 均正确")

    # ---- 通过条件4：头结点不被删除 ----
    # 遍历起点为 L->next（首个数据结点），头结点始终保留
    free_count = 0
    hd = make_list([5, 5, 5])
    DeleteX(hd, 5)
    assert hd is not None, "通过条件4失败: 头结点不应被删除"
    assert hd.next is None, "通过条件4: 全删后 L->next 应为 NULL"
    print("[PASS] 通过条件4 头结点不被删除: 头结点始终保留")

# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("PARAMS: 带头结点单链表 L, 删除目标值 x")
    print("  结点定义: struct LNode { int data; struct LNode *next; }; typedef LNode;")
    print("  函数原型: void DeleteX(LNode *&L, int x)")
    print("=" * 60)

    print("\n--- REASONING: 算法思想 ---")
    print("  1. 设置前驱指针 pre=L（头结点），当前指针 cur=L->next（首个数据结点）")
    print("  2. 遍历链表：cur != NULL 时循环")
    print("  3. 若 cur->data == x：摘链（pre->next = cur->next），free(cur)，cur = pre->next")
    print("     （pre 不前进，保证连续命中也不漏删）")
    print("  4. 若 cur->data != x：pre = cur; cur = cur->next（双指针同时前进）")
    print("  5. 边界：空表时 cur 初始为 NULL，直接跳过循环；全表为 x 时全部摘链，L->next 最终为 NULL")

    print("\n--- 测试用例执行 ---")
    run_tests()

    print("\n--- 通过条件验证 ---")
    verify_pass_conditions()

    print("\n" + "=" * 60)
    print("ANSWER:")
    print("=" * 60)
    print()
    print("【第(1)问 结点类型定义（2分）】")
    print("  typedef struct LNode {")
    print("      int data;")
    print("      struct LNode *next;")
    print("  } LNode, *LinkList;")
    print()
    print("【第(2)问 算法思想（4分）】")
    print("  用工作指针 pre 和 cur 遍历链表，pre 始终指向 cur 的前驱。")
    print("  初始时 pre=L（头结点），cur=L->next（首个数据结点）。")
    print("  遍历过程中：")
    print("    - 若 cur->data==x：将 pre->next 指向 cur->next（摘链），")
    print("      free(cur) 释放内存，然后令 cur=pre->next 继续检查（pre 不动，处理连续命中）。")
    print("    - 若 cur->data!=x：pre 和 cur 同时后移（pre=cur; cur=cur->next）。")
    print("  边界情况：")
    print("    - 空表（L->next==NULL）：cur 初始为 NULL，循环不执行，直接返回。")
    print("    - 连续命中：删除后 pre 不前进，继续检查新 cur，保证连续 x 全部删除。")
    print("    - 尾结点命中：摘链后 pre->next=NULL，循环自然终止。")
    print("    - 全表为 x：所有结点被删除，最终 L->next==NULL。")
    print()
    print("【第(3)问 C/C++ 代码实现（8分）】")
    print("  void DeleteX(LNode *&L, int x) {")
    print("      LNode *pre = L;          // pre 指向头结点")
    print("      LNode *cur = L->next;     // cur 指向首个数据结点（遍历起点）")
    print("      while (cur != NULL) {")
    print("          if (cur->data == x) {        // 命中目标值")
    print("              pre->next = cur->next;   // 摘链：前驱 next 跳过 cur")
    print("              free(cur);               // 释放被删除结点的内存")
    print("              cur = pre->next;         // cur 前进，pre 不动（处理连续命中）")
    print("          } else {                     // 未命中")
    print("              pre = cur;               // 前驱前进")
    print("              cur = cur->next;         // 当前指针前进")
    print("          }")
    print("      }")
    print("  }")
    print()
    print("=== 全部测试通过，全部通过条件 assert 命中 ===")
