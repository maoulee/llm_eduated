"""
循环队列入队/出队操作代码填空 —— gen.py
题干规则翻译为 Python 模拟，通过条件翻译为 assert。

约定：
  front 指向队头元素位置
  rear  指向队尾元素的下一个位置（待插入位置）
  牺牲一个存储单元区分队空/队满
  MaxSize = 8
"""

MaxSize = 8

# ============================================================
# 正确答案（逐空）
# ============================================================
ANS = {
    1: "(Q->rear + 1) % MaxSize == Q->front",
    2: "Q->rear = (Q->rear + 1) % MaxSize",
    3: "Q->front == Q->rear",
    4: "Q->front = (Q->front + 1) % MaxSize",
}

# ============================================================
# 循环队列模拟（把 C 代码逐行翻译为 Python）
# ============================================================
class SqQueue:
    def __init__(self):
        self.data = [0] * MaxSize
        self.front = 0
        self.rear  = 0

    def is_full(self):
        # 翻译空(1): (Q->rear + 1) % MaxSize == Q->front
        return (self.rear + 1) % MaxSize == self.front

    def is_empty(self):
        # 翻译空(3): Q->front == Q->rear
        return self.front == self.rear

    def EnQueue(self, x):
        # 翻译：if (rear+1)%MaxSize == front  -> 队满
        if self.is_full():
            return False
        self.data[self.rear] = x            # Q->data[Q->rear] = x
        # 翻译空(2): Q->rear = (Q->rear + 1) % MaxSize
        self.rear = (self.rear + 1) % MaxSize
        return True

    def DeQueue(self):
        # 翻译：if front == rear -> 队空
        if self.is_empty():
            return None
        x = self.data[self.front]           # *x = Q->data[Q->front]
        # 翻译空(4): Q->front = (Q->front + 1) % MaxSize
        self.front = (self.front + 1) % MaxSize
        return x

# ============================================================
# 辅助：计算队列中有效元素个数
# ============================================================
def queue_length(q):
    return (q.rear - q.front + MaxSize) % MaxSize

# ============================================================
# 通过条件 5：逻辑自洽
#   连续 8 次 EnQueue，前 7 次返回 True，第 8 次返回 False
#   有效容量 == MaxSize - 1
# ============================================================
def test_logic_consistency():
    q = SqQueue()
    results = [q.EnQueue(i) for i in range(MaxSize)]   # 入队 0..7，共 8 次

    # 前 7 次成功
    for i in range(MaxSize - 1):
        assert results[i] == True, f"第{i+1}次EnQueue应成功，实际={results[i]}"
    # 第 8 次失败（队满）
    assert results[MaxSize - 1] == False, \
        f"第{MaxSize}次EnQueue应返回False（队满），实际={results[MaxSize-1]}"

    # 有效元素个数 == MaxSize - 1
    assert queue_length(q) == MaxSize - 1, \
        f"队列有效容量应为{MaxSize-1}，实际={queue_length(q)}"

    print("[条件5] 逻辑自洽：前7次True、第8次False、容量=%d  ✓" % queue_length(q))

# ============================================================
# 通过条件 6：判空判满可区分
#   初始：front==rear -> 判空为真、判满为假
#   装满7个后 -> 判满为真、判空为假
# ============================================================
def test_empty_full_distinct():
    q = SqQueue()
    # 初始状态
    assert q.is_empty() == True, "初始状态应判空=True"
    assert q.is_full()  == False, "初始状态应判满=False"

    # 装满 7 个
    for i in range(MaxSize - 1):
        q.EnQueue(i)
    assert q.is_full()  == True, "装满7个后应判满=True"
    assert q.is_empty() == False, "装满7个后应判空=False"

    print("[条件6] 判空判满可区分：初始(空=T,满=F)，满7(空=F,满=T)  ✓")

# ============================================================
# 出队正确性验证（附加自洽检查）
#   FIFO：先入先出，全部出队后队空
# ============================================================
def test_dequeue_fifo():
    q = SqQueue()
    for i in range(MaxSize - 1):
        q.EnQueue(i)
    out = [q.DeQueue() for _ in range(MaxSize - 1)]
    expected = list(range(MaxSize - 1))
    assert out == expected, f"FIFO出队顺序错：期望{expected}，实际{out}"
    assert q.is_empty() == True, "全部出队后应判空=True"
    # 再出队应失败（返回 None）
    assert q.DeQueue() is None, "空队出队应返回None"
    print("[附加] FIFO正确、空队出队返回None  ✓")

# ============================================================
# 循环回绕验证（rear/front 跨越 MaxSize 边界）
# ============================================================
def test_wrap_around():
    q = SqQueue()
    # 入队3个
    for i in range(3):
        q.EnQueue(i)
    # 出队3个
    for i in range(3):
        q.DeQueue()
    # 现在 front=rear=3，队空
    assert q.is_empty() == True
    # 再入队到满（从位置3开始，绕回）
    cnt = 0
    while q.EnQueue(99):
        cnt += 1
    assert cnt == MaxSize - 1, f"回绕后应能再装{MaxSize-1}个，实际{cnt}"
    assert q.is_full() == True
    # front 应在 3，rear 应绕回到 2（(3+7)%8=2? rear=3+7=10%8=2）
    assert q.front == 3, f"front应为3，实际{q.front}"
    assert q.rear  == (3 + MaxSize - 1) % MaxSize, f"rear回绕值不符"
    print("[附加] 循环回绕正确：front=%d, rear=%d  ✓" % (q.front, q.rear))

# ============================================================
# PARAMS / REASONING / ANSWER 标签输出
# ============================================================
print("=" * 60)
print("PARAMS")
print(f"  MaxSize = {MaxSize}")
print(f"  front_init = 0, rear_init = 0")
print(f"  约定: rear 指向队尾元素下一位置, 牺牲一个单元")
print()
print("REASONING")
print(f"  空(1) 判满: (Q->rear + 1) % MaxSize == Q->front")
print(f"      —— rear 的下一个位置若等于 front，说明只剩一个空位（牺牲该位），队满")
print(f"  空(2) rear更新: Q->rear = (Q->rear + 1) % MaxSize")
print(f"      —— 先+1再取模，实现循环回绕")
print(f"  空(3) 判空: Q->front == Q->rear")
print(f"      —— 无需取模，front==rear 即队空（牺牲单元方案下判空与判满不同）")
print(f"  空(4) front更新: Q->front = (Q->front + 1) % MaxSize")
print(f"      —— 先+1再取模，实现循环回绕")
print()

print("ANSWER")
for k in [1, 2, 3, 4]:
    print(f"  ({k})  {ANS[k]}")
print()

# ============================================================
# 运行全部验证
# ============================================================
print("=" * 60)
test_logic_consistency()
test_empty_full_distinct()
test_dequeue_fifo()
test_wrap_around()

print()
print(">>> 全部 assert 通过，题目成立。")
