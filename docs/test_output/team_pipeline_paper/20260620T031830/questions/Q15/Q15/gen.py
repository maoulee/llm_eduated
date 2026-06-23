# gen.py - 循环队列代码填空验证

MAXSIZE = 6

class SqQueue:
    """循环队列实现"""
    def __init__(self):
        self.data = [0] * MAXSIZE
        self.front = self.rear = 0  # 空5：初始化 front = rear = 0
    
    def is_full(self):
        """判满条件"""
        return (self.rear + 1) % MAXSIZE == self.front  # 空1
    
    def is_empty(self):
        """判空条件"""
        return self.front == self.rear  # 空3
    
    def en_queue(self, e):
        """入队操作"""
        if self.is_full():
            return 0
        self.data[self.rear] = e
        self.rear = (self.rear + 1) % MAXSIZE  # 空2
        return 1
    
    def de_queue(self):
        """出队操作"""
        if self.is_empty():
            return 0, None
        e = self.data[self.front]
        self.front = (self.front + 1) % MAXSIZE  # 空4
        return 1, e

# ========== 验证段（通过条件 → assert）==========

# 验证空5：初始化后 front == rear == 0
Q = SqQueue()
assert Q.front == 0 and Q.rear == 0, "空5验证失败：初始化后 front 和 rear 应为 0"

# 验证空3：空队列判空（front == rear）
assert Q.is_empty(), "空3验证失败：空队列应判空"

# 验证空1：判满条件 (rear+1)%MAXSIZE == front
# 入队 MAXSIZE-1 个元素后队列满
for i in range(MAXSIZE - 1):
    assert Q.en_queue(i) == 1, f"入队 {i} 失败"
assert Q.is_full(), "空1验证失败：队列满时应判满"
assert Q.en_queue(99) == 0, "空1验证失败：满队列入队应失败"

# 验证空2：rear 更新使用取模
Q2 = SqQueue()
Q2.en_queue(1)
assert Q2.rear == 1, "空2验证失败：rear 更新错误"
Q2.en_queue(2)
assert Q2.rear == 2, "空2验证失败：rear 更新错误"

# 验证空4：front 更新使用取模
Q3 = SqQueue()
Q3.en_queue(10)
Q3.en_queue(20)
ret, val = Q3.de_queue()
assert ret == 1 and val == 10, "出队失败"
assert Q3.front == 1, "空4验证失败：front 更新错误"

# 验证循环特性：front 和 rear 能绕回
Q4 = SqQueue()
for i in range(MAXSIZE - 1):
    Q4.en_queue(i)
for i in range(MAXSIZE - 1):
    ret, val = Q4.de_queue()
    assert ret == 1 and val == i
assert Q4.front == Q4.rear, "循环后 front 应等于 rear"
assert Q4.is_empty(), "循环后队列应判空"

# 验证判满与判空不混淆（核心考点）
# 空队列时 front==rear，但 is_full 应返回 False
Q5 = SqQueue()
assert Q5.is_empty() == True, "空队列应判空"
assert Q5.is_full() == False, "空队列不应判满"
# 满队列时 (rear+1)%MAXSIZE==front，但 is_empty 应返回 False
for i in range(MAXSIZE - 1):
    Q5.en_queue(i)
assert Q5.is_full() == True, "满队列应判满"
assert Q5.is_empty() == False, "满队列不应判空"

print("所有验证通过")
