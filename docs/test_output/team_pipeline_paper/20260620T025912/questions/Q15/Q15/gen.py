"""
循环队列操作代码填空 — gen.py
将 question.md 的「通过条件」翻译为 assert 验证。
"""

# 题干参数
MAXSIZE = 6

# 5个空的正确答案（翻译题干规则）
blank1 = "(Q->rear + 1) % MAXSIZE == Q->front"   # 判满
blank2 = "Q->data[Q->rear] = x"                    # 赋值
blank3 = "Q->rear = (Q->rear + 1) % MAXSIZE"       # rear更新
blank4 = "Q->front == Q->rear"                     # 判空
blank5 = "Q->front = (Q->front + 1) % MAXSIZE"     # front更新

# ========== 通过条件 → assert ==========

# 条件1：判满条件正确
assert blank1 == "(Q->rear + 1) % MAXSIZE == Q->front", "空1判满条件错误"

# 条件2：判空条件正确
assert blank4 == "Q->front == Q->rear", "空4判空条件错误"

# 条件3：赋值语句正确
assert blank2 == "Q->data[Q->rear] = x", "空2赋值语句错误"

# 条件4：rear更新正确
assert blank3 == "Q->rear = (Q->rear + 1) % MAXSIZE", "空3rear更新错误"

# 条件5：front更新正确
assert blank5 == "Q->front = (Q->front + 1) % MAXSIZE", "空5front更新错误"

# 条件6：5个空位互异
blanks = [blank1, blank2, blank3, blank4, blank5]
assert len(set(blanks)) == 5, "5个空位不互异"

# 条件7：MAXSIZE=6 使题目成立
# 牺牲一个单元后实际可存5个元素
# 验证：入队6次后判满条件触发
# 模拟：front=0, rear从0开始，入队6次后 rear=0（循环回来）
# 第6次入队前：rear=5, (5+1)%6=0==front → 判满触发
front_sim = 0
rear_sim = 0
enqueue_count = 0
for i in range(MAXSIZE + 1):  # 尝试入队 MAXSIZE+1 次
    # 判满检查
    if (rear_sim + 1) % MAXSIZE == front_sim:
        break
    rear_sim = (rear_sim + 1) % MAXSIZE
    enqueue_count += 1

assert enqueue_count == MAXSIZE - 1, f"实际可存元素数应为{MAXSIZE-1}，实际为{enqueue_count}"
# 验证判满在第6次尝试时触发（即入队5次后第6次被拒）
assert (rear_sim + 1) % MAXSIZE == front_sim, "入队5次后判满条件应触发"

# ========== 模拟完整入队/出队流程验证正确性 ==========

class SqQueue:
    def __init__(self, maxsize):
        self.maxsize = maxsize
        self.data = [0] * maxsize
        self.front = 0
        self.rear = 0

    def is_full(self):
        return (self.rear + 1) % self.maxsize == self.front

    def is_empty(self):
        return self.front == self.rear

    def en_queue(self, x):
        if self.is_full():
            return False
        self.data[self.rear] = x
        self.rear = (self.rear + 1) % self.maxsize
        return True

    def de_queue(self):
        if self.is_empty():
            return None
        e = self.data[self.front]
        self.front = (self.front + 1) % self.maxsize
        return e

# 模拟入队5个元素，出队5个元素
q = SqQueue(MAXSIZE)
elements = [10, 20, 30, 40, 50]

# 入队5个
for e in elements:
    assert q.en_queue(e), f"入队{e}失败"

# 第6个应被拒绝（队满）
assert not q.en_queue(60), "第6个元素应入队失败（队满）"

# 出队5个，顺序应一致
for expected in elements:
    result = q.de_queue()
    assert result == expected, f"出队期望{expected}，实际{result}"

# 出队后应为空
assert q.is_empty(), "出队5个后队列应为空"

# 再入队应成功
assert q.en_queue(99), "空队列应能入队"
assert q.de_queue() == 99, "再入队再出队应正确"

print("PASS: 所有通过条件验证通过")
print(f"  空1(判满): {blank1}")
print(f"  空2(赋值): {blank2}")
print(f"  空3(rear更新): {blank3}")
print(f"  空4(判空): {blank4}")
print(f"  空5(front更新): {blank5}")
print(f"  MAXSIZE={MAXSIZE}, 实际可存{MAXSIZE-1}个元素")
print(f"  5空互异: {len(set(blanks)) == 5}")
