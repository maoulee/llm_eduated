# gen.py — 单链表递归函数分析验证

# 模拟链表节点
class LNode:
    def __init__(self, data):
        self.data = data
        self.next = None

# 构建测试链表: 1 -> 2 -> 3 -> 4 -> 5
def build_list(values):
    if not values:
        return None
    head = LNode(values[0])
    cur = head
    for v in values[1:]:
        cur.next = LNode(v)
        cur = cur.next
    return head

# 翻译题干中的递归函数（空白①填入 PrintReverse(p->next)）
def PrintReverse(p):
    if p is None:
        return
    # 空白①：递归调用在输出之前
    PrintReverse(p.next)
    print(p.data, end=' ')

# 模拟执行
values = [1, 2, 3, 4, 5]
head = build_list(values)

# 捕获输出
import io, sys
old_stdout = sys.stdout
sys.stdout = buf = io.StringIO()
PrintReverse(head)
sys.stdout = old_stdout
output = buf.getvalue().strip()

print(f"\nPARAMS: 链表元素 = {values}")
print(f"REASONING: 递归函数先调用 PrintReverse(p->next) 再输出 p->data，即先深入递归到链表尾部，再逐层返回时输出，实现逆序")
print(f"ANSWER: 空白① = PrintReverse(p->next); 功能 = 逆序输出单链表各节点的数据域")

# 验证段
# 1. 输出应为逆序
expected_reverse = ' '.join(str(v) for v in reversed(values))
assert output == expected_reverse, f"输出应为逆序 '{expected_reverse}'，实际为 '{output}'"

# 2. 验证递归调用确实在输出之前（通过函数签名确认：PrintReverse(p.next) 在 print 之前）
# 检查函数源码中递归调用在 print 之前
import inspect
source = inspect.getsource(PrintReverse)
lines = source.split('\n')
recurse_line = None
print_line = None
for i, line in enumerate(lines):
    if 'PrintReverse(p.next)' in line:
        recurse_line = i
    if 'print(p.data' in line:
        print_line = i
assert recurse_line is not None, "函数中应包含 PrintReverse(p.next) 递归调用"
assert print_line is not None, "函数中应包含 print(p.data) 输出语句"
assert recurse_line < print_line, "递归调用必须在输出语句之前（先递归后输出 = 逆序）"

# 3. 验证 NULL 终止条件存在
assert 'if p is None' in source or 'if p == None' in source, "递归函数应包含 NULL 终止条件"

# 4. 验证逆序输出语义（输出序列与输入序列相反）
output_values = list(map(int, output.split()))
assert output_values == list(reversed(values)), "输出序列应与输入序列完全相反"

print("验证通过：递归调用在输出之前，输出为逆序，终止条件正确")
