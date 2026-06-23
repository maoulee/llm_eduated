## 题目

已知单链表节点类型定义如下：

```c
typedef struct LNode {
    int data;
    struct LNode *next;
} LNode, *LinkList;
```

阅读以下递归函数 `PrintReverse`，完成代码填空并简述其功能。

```c
void PrintReverse(LinkList p) {
    if (p == NULL)
        return;
    /* 空白① */
    printf("%d ", p->data);
}
```

### 问题

（1）【代码填空】（3分）在 `/* 空白① */` 处填入正确的语句，使函数能正确执行。

（2）【功能简述】（2分）简述函数 `PrintReverse` 的整体功能。

## 参考答案

（1）`PrintReverse(p->next);`

（2）逆序输出单链表各节点的数据域。

## 解析

### 递归执行过程分析

以链表 `1 → 2 → 3 → 4 → 5` 为例，函数执行过程如下：

**递归深入阶段（先递归）：**
```
PrintReverse(1) → PrintReverse(2) → PrintReverse(3) → PrintReverse(4) → PrintReverse(5) → PrintReverse(NULL)
```
当 `p == NULL` 时触发终止条件 `return`，开始逐层返回。

**逐层返回阶段（后输出）：**
```
PrintReverse(NULL) 返回
  → 输出 5
PrintReverse(5) 返回
  → 输出 4
PrintReverse(4) 返回
  → 输出 3
PrintReverse(3) 返回
  → 输出 2
PrintReverse(2) 返回
  → 输出 1
PrintReverse(1) 返回
```

**最终输出：** `5 4 3 2 1`

### 关键机制

递归函数先调用 `PrintReverse(p->next)` 再输出 `p->data`，即**先深入递归到链表尾部，再逐层返回时输出**，实现逆序。

- **先递归、后输出** = 逆序输出（后入先出）
- **先输出、后递归** = 正序输出（先入先出）

### 验证

对链表 `[1, 2, 3, 4, 5]` 执行 `PrintReverse(head)`：
- 输出结果：`5 4 3 2 1`
- 验证通过：递归调用在输出之前，输出为逆序，终止条件正确
