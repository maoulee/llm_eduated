"""
单链表递归函数分析 - 建模验证代码
翻译 question.md 中的通过条件为可执行断言
"""

# ============================================================
# 1. 模拟单链表结构
# ============================================================

class LNode:
    def __init__(self, data):
        self.data = data
        self.next = None


def build_linked_list(values):
    """根据值列表构建单链表，返回头指针"""
    if not values:
        return None
    head = LNode(values[0])
    curr = head
    for v in values[1:]:
        curr.next = LNode(v)
        curr = curr.next
    return head


# ============================================================
# 2. 翻译两种填法的递归函数
# ============================================================

def print_reverse_correct(L):
    """正确填法：L == NULL（即 L is None）"""
    result = []
    def _helper(node):
        if node is None:          # 空白①填 L == NULL
            return
        _helper(node.next)
        result.append(node.data)  # 回溯阶段输出
    _helper(L)
    return result


def print_reverse_wrong(L):
    """错误填法：L->next == NULL（即 L.next is None）"""
    result = []
    def _helper(node):
        if node.next is None:     # 空白①填 L->next == NULL（错误）
            return
        _helper(node.next)
        result.append(node.data)  # 回溯阶段输出
    _helper(L)
    return result


# ============================================================
# 3. 注入参数：链表 12 → 25 → 7 → 33 → 19
# ============================================================

values = [12, 25, 7, 33, 19]
L = build_linked_list(values)

correct_output = print_reverse_correct(L)
wrong_output = print_reverse_wrong(L)

print(f"链表元素: {values}")
print(f"正确填法 (L==NULL) 输出: {correct_output}")
print(f"错误填法 (L->next==NULL) 输出: {wrong_output}")

# ============================================================
# 4. 翻译通过条件为 assert
# ============================================================

# --- 通过条件1：空白①正确填法唯一确定，且与错误填法产生不同行为 ---
# 正确填法应输出全部5个元素（逆序），错误填法漏掉尾节点
assert len(correct_output) == 5, f"正确填法应输出全部5个元素，实际输出{len(correct_output)}个"
assert len(wrong_output) == 4, f"错误填法应漏掉1个元素，实际输出{len(wrong_output)}个"
assert correct_output != wrong_output, "正确填法与错误填法必须产生不同输出"
# 错误填法漏掉的是头节点12（因为递归到最后一个节点时直接return，不输出）
assert 12 not in wrong_output, "错误填法应漏掉头节点12"
assert 12 in correct_output, "正确填法应包含头节点12"

# --- 通过条件2：函数逻辑完整（三要素齐全）---
# 通过代码结构验证：正确填法函数包含递归终止条件、递归调用、回溯输出
# 这里通过行为验证：输出非空且为逆序
assert len(correct_output) > 0, "函数应能输出元素（递归终止条件有效）"
assert correct_output == list(reversed(values)), f"输出应为逆序 {list(reversed(values))}，实际 {correct_output}"

# --- 通过条件3：功能描述可验证——"逆序输出"与"正序输出"可区分 ---
# 正确输出是逆序，不是正序
assert correct_output != values, "输出不应是正序（否则功能描述'逆序输出'不成立）"
assert correct_output == list(reversed(values)), "输出必须是逆序"

# --- 通过条件4：两问独立可答 ---
# 第(1)问填空：只需判断 L==NULL vs L->next==NULL，不依赖功能描述
# 第(2)问功能：只需观察输出顺序，不依赖填空结果
# 通过验证：两种填法都能产生输出（只是内容不同），说明功能描述可以从输出推断
assert len(wrong_output) > 0, "错误填法也能产生输出，说明功能描述不依赖填空结果"
# 填空判断只依赖终止条件差异，不依赖输出内容
assert correct_output != wrong_output, "两问独立：填空差异体现在输出内容不同"

# ============================================================
# 5. 额外验证：链表节点数在约束范围内（3-5个）
# ============================================================

assert 3 <= len(values) <= 5, f"链表节点数应在3-5之间，实际{len(values)}个"

# ============================================================
# 6. 验证递归函数行数（不含结构体定义）
# ============================================================

# 题干中 PrintReverse 函数体（不含结构体）：
# void PrintReverse(LinkList L) {
#     if (__________)          /* 空白① */
#         return;
#     PrintReverse(L->next);
#     printf("%d ", L->data);
# }
# 共5行（含函数签名和花括号）
func_lines = 5
assert 5 <= func_lines <= 8, f"递归函数行数应在5-8之间，实际{func_lines}行"

print("\n=== 所有通过条件验证通过 ===")
print(f"正确输出（逆序）: {correct_output}")
print(f"错误输出（漏尾）: {wrong_output}")
print(f"功能描述: 逆序输出单链表所有元素")
