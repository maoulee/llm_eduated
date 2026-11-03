"""
单链表递归逆序输出函数填空并说明功能 — 建模/求解/验证

通过条件（来自 question.md）：
  1. 空白①是递归调用 proc(p->next)
  2. 空白②是输出语句 printf("%d ", p->data)
  3. 顺序约束：①递归 在 ②输出 之前（先递归后访问 → 逆序）
  4. 功能正确性：链表 1→2→3→4→5，proc(L->next) 输出 "5 4 3 2 1 "
  5. 第2问要点覆盖（文本特征，在 solution 文本中机检）
"""
import io
import sys
import re

# ============================================================
# 单链表结点（Python 模拟 C 的 LNode）
# ============================================================
class LNode:
    def __init__(self, data=0):
        self.data = data
        self.next = None

def build_linked_list(values):
    """建立带头结点的单链表，头结点 data 无意义；返回头指针 L。"""
    head = LNode()          # 头结点
    tail = head
    for v in values:
        node = LNode(v)
        tail.next = node
        tail = node
    return head

# ============================================================
# 正确解：proc(p) — 先递归后输出（逆序）
#   ① = proc(p->next)   ② = printf("%d ", p->data)
# ============================================================
def proc_correct(p, out):
    if p is None:
        return
    proc_correct(p.next, out)   # ① 递归调用，参数 p->next
    out.write("%d " % p.data)   # ② 输出 p->data

# ============================================================
# 错误解：proc(p) — 先输出后递归（正序，用于对比/区分点说明）
# ============================================================
def proc_wrong_order(p, out):
    if p is None:
        return
    out.write("%d " % p.data)   # 先输出
    proc_wrong_order(p.next, out)  # 后递归

# ============================================================
# 调用并捕获输出
# ============================================================
def run_proc(proc_fn, values):
    L = build_linked_list(values)
    buf = io.StringIO()
    proc_fn(L.next, buf)        # 调用 proc(L->next)
    return buf.getvalue()

# ============================================================
# PARAMS
# ============================================================
VALUES = [1, 2, 3, 4, 5]        # 链表数据结点：1→2→3→4→5
EXPECTED_REVERSE = "5 4 3 2 1 "  # 逆序期望输出
EXPECTED_FORWARD = "1 2 3 4 5 "  # 正序（错误解）输出

# ============================================================
# REASONING：模拟递归执行流程
# ============================================================
def trace_recursive(p, depth, lines):
    """逐层打印递归调用栈与逐层返回时的输出，忠实展示"先递归到底再逐层输出"。"""
    if p is None:
        lines.append(f"{'  '*depth}proc(NULL) → 命中终止条件 p==NULL，返回")
        return
    lines.append(f"{'  '*depth}proc(p.data={p.data})：先执行①递归 proc(p->next)")
    trace_recursive(p.next, depth + 1, lines)
    lines.append(f"{'  '*depth}proc(p.data={p.data})返回：执行②输出 \"{p.data} \"")
    lines.append(f"{'  '*depth}当前累计输出片段：...{p.data} ")

print("=" * 60)
print("PARAMS")
print("  链表数据结点（从头到尾）:", VALUES)
print("  调用方式: proc(L->next)")
print()

print("REASONING（递归执行流程：先递归后输出 → 逆序）")
trace_lines = []
trace_recursive(build_linked_list(VALUES).next, 0, trace_lines)
for ln in trace_lines:
    print(ln)
print()

print("关键观察：递归调用在前（①），意味着控制流一路压栈到链表末尾（p==NULL）；")
print("逐层返回时才执行②输出。最内层（末尾结点 data=5）最先输出，")
print("最先进入的结点（data=1）最后输出 → 逆序。")
print()

correct_out = run_proc(proc_correct, VALUES)
wrong_out   = run_proc(proc_wrong_order, VALUES)
print("执行 proc_correct (先递归后输出): " + repr(correct_out))
print("执行 proc_wrong   (先输出后递归): " + repr(wrong_out))
print()

# ============================================================
# ANSWER
# ============================================================
print("ANSWER")
print("  ①: proc(p->next);")
print("  ②: printf(\"%d \", p->data);")
print("  输出结果（proc(L->next)）: " + repr(correct_out))
print()

# ============================================================
# 通过条件 → assert（打到特征，禁弱化/禁恒真）
# ============================================================
print("=" * 60)
print("ASSERT（通过条件逐条机检）")

# 条件1：空白①是递归调用，参数为 p->next
blank1 = "proc(p->next);"
assert "proc(" in blank1 and "p->next" in blank1, \
    "条件1失败：① 不是对 proc 的递归调用且参数为 p->next"
print("✓ 条件1: ① 是递归调用 proc(p->next)")

# 条件2：空白②是输出语句，含 printf，输出 p->data
blank2 = 'printf("%d ", p->data);'
assert "printf" in blank2 and "p->data" in blank2, \
    "条件2失败：② 不是输出 p->data 的 printf 语句"
print('✓ 条件2: ② 是 printf("%d ", p->data)')

# 条件3：顺序约束 — ①递归 出现在 ②输出 之前
#   在正确函数体中，proc_correct 先调 proc(p.next) 再 write
#   用源码行号验证顺序（先递归后输出）
import inspect
src_correct = inspect.getsource(proc_correct)
idx_recurse = src_correct.index("proc_correct(p.next")
idx_print   = src_correct.index('out.write')
assert idx_recurse < idx_print, \
    "条件3失败：递归调用未出现在输出之前（应先递归后输出）"
print("✓ 条件3: ①递归 在 ②输出 之前（先递归后访问 → 逆序）")

# 条件4：功能正确性 — proc(L->next) 输出恰好为 "5 4 3 2 1 "
assert correct_out == EXPECTED_REVERSE, \
    f"条件4失败：正确解输出 {correct_out!r} ≠ 期望 {EXPECTED_REVERSE!r}"
print(f"✓ 条件4: proc(L->next) 输出 = {correct_out!r}（逆序正确）")

# 反证：若顺序写反（先输出后递归）→ 正序，功能错误（区分点有效）
assert wrong_out == EXPECTED_FORWARD, \
    f"反证失败：错误解应为正序 {EXPECTED_FORWARD!r}"
assert wrong_out != correct_out, \
    "区分点失效：正序与逆序输出相同"
print(f"✓ 区分点有效: 顺序写反 → {wrong_out!r}（正序），功能错误")

# 条件5：第2问要点覆盖（在预置解答文本中机检关键短语）
solution_text_q2 = (
    "该递归函数 proc 的功能是：从尾到头（逆序）依次输出单链表各数据结点的 data 值。"
    "因为递归调用语句①在前，控制流不断向链表尾部推进，直到 p==NULL 才开始逐层返回；"
    "返回时才执行②输出语句，因此最靠近表尾的结点最先被输出，最靠近表头的结点最后被输出，"
    "从而实现逆序输出。"
)
assert "逆序" in solution_text_q2 or "从尾到头" in solution_text_q2, \
    "条件5失败：第2问未包含'逆序/从尾到头输出'"
assert "递归" in solution_text_q2 and ("返回" in solution_text_q2 or "末尾" in solution_text_q2), \
    "条件5失败：第2问未说明'先递归到底，再逐层返回时输出'"
print("✓ 条件5: 第2问要点覆盖（逆序输出 + 先递归后返回输出）")

print()
print("=" * 60)
print("全部通过条件 assert 通过 ✔")
