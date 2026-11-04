## 题目

循环队列是一种常用的数据结构，它用一维数组实现，通过取模运算使队列在逻辑上"循环"。阅读以下循环队列的 C 语言实现，补充 4 处代码（①~④），使入队和出队操作正确完成。

```c
#define MAXSIZE 13  /* 队列最大容量（数组大小），实际最多存储 MAXSIZE-1 个元素 */

typedef struct {
    int data[MAXSIZE];  /* 存储队列元素的数组 */
    int front;          /* 队头指针，指向队头元素 */
    int rear;           /* 队尾指针，指向队尾元素的下一个位置（即下一个入队位置） */
} CirQueue;

/* 初始化循环队列为空 */
void InitQueue(CirQueue *Q) {
    Q->front = 0;
    Q->rear = 0;
}

/* 判断队列是否为空：空时返回 1，非空时返回 0 */
int IsEmpty(CirQueue *Q) {
    if (/* ① */) return 1;
    else return 0;
}

/* 判断队列是否已满：满时返回 1，未满时返回 0 */
int IsFull(CirQueue *Q) {
    if (/* ② */) return 1;
    else return 0;
}

/* 入队操作：将元素 x 加入队尾，成功返回 1，队列满返回 0 */
int EnQueue(CirQueue *Q, int x) {
    if (IsFull(Q)) return 0;
    Q->data[Q->rear] = x;
    Q->rear = /* ③ */;
    return 1;
}

/* 出队操作：删除队头元素并将其值通过 x 返回，成功返回 1，队列空返回 0 */
int DeQueue(CirQueue *Q, int *x) {
    if (IsEmpty(Q)) return 0;
    *x = Q->data[Q->front];
    Q->front = /* ④ */;
    return 1;
}
```

**请补充上述代码中的 4 处空白（①~④），使循环队列的入队和出队操作正确实现。**

---

## 参考答案

| 填空 | 答案 |
|------|------|
| ① | `Q->front == Q->rear` |
| ② | `(Q->rear + 1) % MAXSIZE == Q->front` |
| ③ | `(Q->rear + 1) % MAXSIZE` |
| ④ | `(Q->front + 1) % MAXSIZE` |

---

## 解析

### 填空①：判空条件 `Q->front == Q->rear`

**原理**：循环队列初始化时 `front = rear = 0`，此时队列为空。在入队和出队操作中，front 和 rear 同步移动，当两者再次相等时，说明队列中所有元素已被取出，队列为空。

**验证**：
- 初始化后 `front == rear == 0`，`IsEmpty()` 返回 1（空）。
- 入队一个元素后 `rear` 前进，`front != rear`，`IsEmpty()` 返回 0（非空）。

---

### 填空②：判满条件 `(Q->rear + 1) % MAXSIZE == Q->front`

**原理**：循环队列采用**牺牲一个存储单元**的方法区分队空和队满。当 `rear` 再前进一位就追上 `front` 时，判定为满。取模运算确保 `rear` 在数组边界处回绕。

**为什么牺牲一个单元**：若不使用此方法，`front == rear` 既可能表示空也可能表示满，无法区分。牺牲一个单元后：
- 空：`front == rear`
- 满：`(rear + 1) % MAXSIZE == front`

**验证**（MAXSIZE=13）：
- 入队 MAXSIZE-1=12 个元素后，`IsFull()` 返回 1。
- 此时再入队返回 0（失败），说明判满条件生效。
- 遍历所有 front、rear 组合（0~12），不存在同时满足判空和判满的状态，两者兼容。

---

### 填空③：入队指针更新 `(Q->rear + 1) % MAXSIZE`

**原理**：入队后，`rear` 指针前进一位。取模 `% MAXSIZE` 确保当 `rear` 到达数组末尾（索引 MAXSIZE-1）时，下一次入队后 `rear` 回绕到 0，实现循环。

**验证**：
- 入队 1 个元素：`rear` 从 0 → 1。
- 入队 2 个元素：`rear` 从 1 → 2。
- 入队 MAXSIZE-1=12 个元素后，`rear = 12`（即 MAXSIZE-1）。
- 出队 MAXSIZE-2=11 个元素后，`front = 11`，此时再入队一个元素，`rear` 从 12 回绕到 0（取模生效）。

---

### 填空④：出队指针更新 `(Q->front + 1) % MAXSIZE`

**原理**：出队后，`front` 指针前进一位。取模 `% MAXSIZE` 确保当 `front` 到达数组末尾时回绕到 0，实现循环。

**验证**：
- 入队两个元素后出队 1 个：`front` 从 0 → 1。
- 再出队 1 个：`front` 从 1 → 2。
- 在回绕测试中，`front` 从 MAXSIZE-1 出队后回绕到 0（取模生效）。

---

## 完整代码

```c
#define MAXSIZE 13

typedef struct {
    int data[MAXSIZE];
    int front;
    int rear;
} CirQueue;

void InitQueue(CirQueue *Q) {
    Q->front = 0;
    Q->rear = 0;
}

int IsEmpty(CirQueue *Q) {
    if (Q->front == Q->rear) return 1;
    else return 0;
}

int IsFull(CirQueue *Q) {
    if ((Q->rear + 1) % MAXSIZE == Q->front) return 1;
    else return 0;
}

int EnQueue(CirQueue *Q, int x) {
    if (IsFull(Q)) return 0;
    Q->data[Q->rear] = x;
    Q->rear = (Q->rear + 1) % MAXSIZE;
    return 1;
}

int DeQueue(CirQueue *Q, int *x) {
    if (IsEmpty(Q)) return 0;
    *x = Q->data[Q->front];
    Q->front = (Q->front + 1) % MAXSIZE;
    return 1;
}
```

---

## 关键总结

| 操作 | 核心公式 | 要点 |
|------|----------|------|
| 判空 | `front == rear` | 初始化时相等，出队追上入队时相等 |
| 判满 | `(rear + 1) % MAXSIZE == front` | 牺牲一个单元区分空满 |
| 入队更新 | `rear = (rear + 1) % MAXSIZE` | 取模实现循环回绕 |
| 出队更新 | `front = (front + 1) % MAXSIZE` | 取模实现循环回绕 |

**核心思想**：循环队列通过取模运算 `% MAXSIZE` 使指针在数组边界处回绕，通过牺牲一个存储单元（判满条件）解决空满状态歧义。
