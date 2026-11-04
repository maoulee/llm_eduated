# gen.py — 递归逆序输出链表：模拟求解过程

# ============================================================
# PARAMS: 题干参数
# ============================================================
# 链表结点结构：data + next
# 递归函数：ReversePrint(LinkList L)
# 空白处①：递归调用语句
# 验证用链表：1 -> 2 -> 3 -> 4 -> 5

class LNode:
    def __init__(self, data):
        self.data = data
        self.next = None

# 构建测试链表: 1 -> 2 -> 3 -> 4 -> 5
head = LNode(1)
cur = head
for val in [2, 3, 4, 5]:
    cur.next = LNode(val)
    cur = cur.next

# ============================================================
# REASONING: 模拟递归执行过程
# ============================================================
print("=== 模拟 ReversePrint 执行过程 ===")

call_stack = []  # 模拟调用栈
output_order = []  # 记录输出顺序

def ReversePrint_sim(L, depth=0):
    """模拟 ReversePrint 的执行（填空后）"""
    indent = "  " * depth
    call_stack.append(L.data if L else None)
    
    if L is None:
        print(f"{indent}[调用栈展开] L==NULL, return")
        call_stack.pop()
        return
    
    print(f"{indent}[进入] L->data={L.data}")
    
    # ① 递归调用（在 printf 之前）
    print(f"{indent}  → 先执行 ReversePrint(L->next)")
    ReversePrint_sim(L.next, depth + 1)
    
    # 回溯后输出
    print(f"{indent}[回溯] printf({L.data})")
    output_order.append(L.data)
    call_stack.pop()

ReversePrint_sim(head)

print(f"\n输出顺序: {output_order}")
print(f"原始顺序: [1, 2, 3, 4, 5]")

# ============================================================
# 验证段
# ============================================================
# 验证1: 输出是逆序的
assert output_order == [5, 4, 3, 2, 1], f"逆序验证失败: {output_order}"

# 验证2: 链表结构未被修改（仅输出，不修改结构）
check = head
original_order = []
while check:
    original_order.append(check.data)
    check = check.next
assert original_order == [1, 2, 3, 4, 5], "链表结构被修改"

# 验证3: 递归调用在 printf 之前（代码结构验证）
# 题干代码中 ① 在 printf 之前 → 保证逆序
code_structure = """
void ReversePrint(LinkList L) {
    if (L == NULL)
        return;
    ① ReversePrint(L->next);   // 递归调用在前
    printf("%d ", L->data);     // 输出在后
}
"""
# 验证：递归调用行号 < printf 行号
lines = code_structure.strip().split('\n')
recurse_line = None
printf_line = None
for i, line in enumerate(lines):
    if 'ReversePrint(L->next)' in line:
        recurse_line = i
    if 'printf' in line:
        printf_line = i
assert recurse_line is not None and printf_line is not None, "代码结构不完整"
assert recurse_line < printf_line, "递归调用必须在 printf 之前"

# 验证4: 递归终止条件存在
assert 'if (L == NULL)' in code_structure, "缺少递归终止条件"

print("\n=== 所有验证通过 ===")

# ============================================================
# ANSWER: 最终答案
# ============================================================
print("\n【答案】")
print("(1) 空白处①填入：ReversePrint(L->next);")
print("(2) 函数功能：逆序输出单链表中各结点的数据值（不修改链表结构）")
