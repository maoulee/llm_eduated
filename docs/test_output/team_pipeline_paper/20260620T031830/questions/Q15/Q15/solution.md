# 循环队列操作实现——解析

## 题目回顾

补全循环队列的入队（EnQueue）、出队（DeQueue）和初始化（InitQueue）函数中的 5 个关键语句。

## 逐步解析

### 空1：判满条件

**答案：** `(Q->rear + 1) % MAXSIZE == Q->front`

**解析：** 循环队列采用"少用一个存储单元"的策略来区分队列满和队列空。当队尾指针 rear 再前进一个位置（取模后）就与队头指针 front 重合时，说明队列已满。表达式 `(Q->rear + 1) % MAXSIZE == Q->front` 即为此判满条件。

> ⚠️ 注意：判满条件 `(rear+1)%MAXSIZE == front` 与判空条件 `front == rear` 不同，二者不可混淆。

---

### 空2：rear 指针更新

**答案：** `Q->rear = (Q->rear + 1) % MAXSIZE`

**解析：** 元素入队后，队尾指针 rear 需要向前移动一位。由于是循环队列，当 rear 到达数组末尾时需要绕回开头，因此使用取模运算 `(Q->rear + 1) % MAXSIZE` 实现循环移动。

---

### 空3：判空条件

**答案：** `Q->front == Q->rear`

**解析：** 当队头指针 front 与队尾指针 rear 相等时，队列为空。这是循环队列的判空条件，与判满条件 `(rear+1)%MAXSIZE == front` 形成对比——判空时 front 与 rear 直接相等，判满时 rear 再走一步才追上 front。

---

### 空4：front 指针更新

**答案：** `Q->front = (Q->front + 1) % MAXSIZE`

**解析：** 元素出队后，队头指针 front 需要向前移动一位。同样使用取模运算 `(Q->front + 1) % MAXSIZE` 实现循环移动，确保 front 到达数组末尾后能绕回开头。

---

### 空5：初始化 front 和 rear

**答案：** `Q->front = Q->rear = 0`

**解析：** 初始化空队列时，队头指针和队尾指针均置为 0。此时 `front == rear`，满足判空条件，队列为空状态。

## 答案汇总

| 空号 | 位置 | 答案 |
|------|------|------|
| 空1 | 判满条件 | `(Q->rear + 1) % MAXSIZE == Q->front` |
| 空2 | rear 指针更新 | `Q->rear = (Q->rear + 1) % MAXSIZE` |
| 空3 | 判空条件 | `Q->front == Q->rear` |
| 空4 | front 指针更新 | `Q->front = (Q->front + 1) % MAXSIZE` |
| 空5 | 初始化 | `Q->front = Q->rear = 0` |

## 核心考点总结

1. **判满 vs 判空**：判满为 `(rear+1)%MAXSIZE == front`（少用一个单元），判空为 `front == rear`，二者不可混淆。
2. **指针取模更新**：rear 和 front 的移动均需 `% MAXSIZE` 取模，实现循环效果。
3. **初始化**：front 和 rear 均初始化为 0，使队列处于空状态。
