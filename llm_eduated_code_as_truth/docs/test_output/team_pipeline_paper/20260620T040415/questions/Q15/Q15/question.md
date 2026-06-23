# 循环队列操作代码填空

## 题干

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

## 设计意图

- **考察知识点**：循环队列的判空条件、判满条件、指针更新（取模运算）
- **K 目标**：K2=3（主导，取模运算理解）、K3=2（操作逻辑推演）、K1=2（基本概念记忆）
- **填空策略**：
  - ① 判空条件（front 与 rear 的关系）
  - ② 判满条件（牺牲一个单元，rear 再进一位追上 front）
  - ③ 入队后 rear 指针更新（取模运算）
  - ④ 出队后 front 指针更新（取模运算）

## 通过条件（成功判据）

本题成立 ⇔ 以下可机检特征全部满足：

1. **判空条件正确**：填空①实现 `front == rear` 的等价判断（空队列时 front 与 rear 相等）。
2. **判满条件正确**：填空②实现 `(rear + 1) % MAXSIZE == front` 的等价判断（牺牲一个单元区分空满）。
3. **入队指针更新正确**：填空③实现 `rear = (rear + 1) % MAXSIZE` 的等价形式（取模确保循环）。
4. **出队指针更新正确**：填空④实现 `front = (front + 1) % MAXSIZE` 的等价形式（取模确保循环）。
5. **判满与判空兼容**：在 MAXSIZE=13 下，判满条件 `(rear+1)%13 == front` 与判空条件 `front == rear` 不会冲突（即不存在某个状态同时被判为空和满）。
6. **指针更新使用取模**：填空③和④必须包含对 MAXSIZE（或 13）的取模运算，而非简单的 `+1`（否则无法实现循环）。
