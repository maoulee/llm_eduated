MAXSIZE = 13

class CirQueue:
    def __init__(self):
        self.data = [0] * MAXSIZE
        self.front = 0
        self.rear = 0
    
    def is_empty(self):
        # 填空①: Q->front == Q->rear
        return self.front == self.rear
    
    def is_full(self):
        # 填空②: (Q->rear + 1) % MAXSIZE == Q->front
        return (self.rear + 1) % MAXSIZE == self.front
    
    def en_queue(self, x):
        if self.is_full():
            return 0
        self.data[self.rear] = x
        # 填空③: (Q->rear + 1) % MAXSIZE
        self.rear = (self.rear + 1) % MAXSIZE
        return 1
    
    def de_queue(self):
        if self.is_empty():
            return None
        x = self.data[self.front]
        # 填空④: (Q->front + 1) % MAXSIZE
        self.front = (self.front + 1) % MAXSIZE
        return x


# ========== 通过条件验证 ==========

# 1. 判空条件正确：填空①实现 front == rear 的等价判断
Q = CirQueue()
assert Q.is_empty() == True, "空队列应判空"
Q.en_queue(1)
assert Q.is_empty() == False, "非空队列应判非空"

# 2. 判满条件正确：填空②实现 (rear + 1) % MAXSIZE == front 的等价判断
for i in range(MAXSIZE - 1):
    assert Q.en_queue(i) == 1, f"入队第{i+1}个元素应成功"
assert Q.is_full() == True, "入队 MAXSIZE-1 个元素后应判满"
assert Q.en_queue(999) == 0, "满队列入队应失败"

# 3. 入队指针更新正确：填空③实现 rear = (rear + 1) % MAXSIZE
Q2 = CirQueue()
Q2.en_queue(1)
assert Q2.rear == 1, "入队1个元素后 rear 应为 1"
Q2.en_queue(2)
assert Q2.rear == 2, "入队2个元素后 rear 应为 2"

# 4. 出队指针更新正确：填空④实现 front = (front + 1) % MAXSIZE
Q3 = CirQueue()
Q3.en_queue(10)
Q3.en_queue(20)
Q3.de_queue()
assert Q3.front == 1, "出队1个元素后 front 应为 1"
Q3.de_queue()
assert Q3.front == 2, "出队2个元素后 front 应为 2"

# 5. 判满与判空兼容：不存在同时为空和满的状态
def check_compatibility():
    for front in range(MAXSIZE):
        for rear in range(MAXSIZE):
            is_empty = (front == rear)
            is_full = ((rear + 1) % MAXSIZE == front)
            assert not (is_empty and is_full), f"Conflict at front={front}, rear={rear}"
check_compatibility()

# 6. 指针更新使用取模：填空③和④必须包含对 MAXSIZE 的取模运算
# 通过循环回绕测试验证取模生效
Q4 = CirQueue()
# 入队 MAXSIZE-1 个元素，rear 从 0 走到 MAXSIZE-1
for i in range(MAXSIZE - 1):
    Q4.en_queue(i)
assert Q4.rear == MAXSIZE - 1, f"入队 MAXSIZE-1 个元素后 rear 应为 {MAXSIZE-1}"
# 出队 MAXSIZE-2 个元素，front 从 0 走到 MAXSIZE-2
for i in range(MAXSIZE - 2):
    Q4.de_queue()
assert Q4.front == MAXSIZE - 2, f"出队 MAXSIZE-2 个元素后 front 应为 {MAXSIZE-2}"
# 再入队一个元素，rear 应从 MAXSIZE-1 回绕到 0（取模生效）
assert Q4.en_queue(999) == 1, "应能入队"
assert Q4.rear == 0, "rear 应回绕到 0（取模验证）"
# 再出队一个元素，front 应从 MAXSIZE-2 走到 MAXSIZE-1
Q4.de_queue()
assert Q4.front == MAXSIZE - 1, f"front 应为 {MAXSIZE-1}"
# 再出队一个元素，front 应从 MAXSIZE-1 回绕到 0（取模生效）
Q4.de_queue()
assert Q4.front == 0, "front 应回绕到 0（取模验证）"

print("所有通过条件验证通过！")
print("填空①: Q->front == Q->rear")
print("填空②: (Q->rear + 1) % MAXSIZE == Q->front")
print("填空③: (Q->rear + 1) % MAXSIZE")
print("填空④: (Q->front + 1) % MAXSIZE")
