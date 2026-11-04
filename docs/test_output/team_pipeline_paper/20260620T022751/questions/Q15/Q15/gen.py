"""
循环队列入队操作代码填空 - 验证脚本
模拟循环队列入队操作，验证填空答案的正确性
"""

MAXSIZE = 7

class SqQueue:
    def __init__(self):
        self.data = [0] * MAXSIZE
        self.front = 0  # 队头指针，指向队头元素
        self.rear = 0   # 队尾指针，指向队尾元素的下一个位置

def EnQueue(Q, e):
    """
    循环队列入队操作
    填空答案：
    ① (Q.rear + 1) % MAXSIZE == Q.front  （判满条件）
    ③ (Q.rear + 1) % MAXSIZE             （更新队尾指针）
    ④ 1                                   （返回成功标志）
    """
    # ① 判满条件
    if (Q.rear + 1) % MAXSIZE == Q.front:
        return 0
    
    # ② 将元素 e 存入队尾
    Q.data[Q.rear] = e
    
    # ③ 更新队尾指针（注意循环特性）
    Q.rear = (Q.rear + 1) % MAXSIZE
    
    # ④ 返回成功标志
    return 1

def main():
    # 验证条件 4：MAXSIZE 非 2 的幂
    assert MAXSIZE & (MAXSIZE - 1) != 0, "MAXSIZE 应为非 2 的幂"
    assert MAXSIZE == 7, "MAXSIZE 应为 7"
    
    # 创建队列并测试入队
    Q = SqQueue()
    
    # 测试入队成功（队列未满）
    result = EnQueue(Q, 10)
    assert result == 1, "入队成功应返回 1"  # 验证条件 3
    
    # 验证 rear 更新使用了取模（在 [0, MAXSIZE-1] 范围内）
    assert 0 <= Q.rear < MAXSIZE, "rear 应在 [0, MAXSIZE-1] 范围内"  # 验证条件 2
    
    # 连续入队直到队列满（少用一个单元，最多入 MAXSIZE-1 个元素）
    for i in range(2, MAXSIZE):  # 已入 1 个，再入 MAXSIZE-2 个
        result = EnQueue(Q, i * 10)
        assert result == 1, f"第 {i} 次入队应成功"
    
    # 此时队列已满（front=0, rear=6, (rear+1)%7 == front）
    # 验证条件 1：判满条件正确
    result = EnQueue(Q, 999)
    assert result == 0, "队列满时应返回 0"
    
    # 验证条件 5：判满与更新策略一致
    # 判满使用 (rear+1)%MAXSIZE == front，更新使用 (rear+1)%MAXSIZE
    # 两者都使用取模运算，策略一致
    # 通过实际行为验证：rear 从 0 到 6 循环，判满在 rear=6 时触发
    assert Q.rear == 6, "队列满时 rear 应为 6"
    assert (Q.rear + 1) % MAXSIZE == Q.front, "判满条件应成立"
    
    # 验证取模不退化为位运算（MAXSIZE=7 非 2 的幂）
    # 如果 MAXSIZE 是 2 的幂，% MAXSIZE 等价于 & (MAXSIZE-1)
    # 这里 MAXSIZE=7，取模不退化
    assert (Q.rear + 1) % MAXSIZE != (Q.rear + 1) & (MAXSIZE - 1), \
        "取模运算不应退化为位运算"
    
    print("所有验证通过！")
    print(f"MAXSIZE = {MAXSIZE}")
    print(f"填空①: (Q->rear + 1) % MAXSIZE == Q->front")
    print(f"填空③: (Q->rear + 1) % MAXSIZE")
    print(f"填空④: 1")

if __name__ == "__main__":
    main()
