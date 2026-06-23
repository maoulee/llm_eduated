# 单链表递归函数分析

## 题干

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

---

## 通过条件（成功判据）

本题成立 ⇔ 以下可机检特征满足：

1. **空白①为递归调用语句**：填入的语句必须是对 `PrintReverse` 的递归调用，且参数为 `p->next`（即 `PrintReverse(p->next)`）。
2. **递归调用在输出语句之前**：代码执行顺序为"先递归、后输出"，这是实现逆序输出的关键。
3. **功能描述包含"逆序"与"输出"语义**：功能简述中需体现"逆序/倒序/反向"和"输出/打印/显示"两个核心语义。
4. **递归终止条件已给出**：`if (p == NULL) return` 已在代码中提供，不作为填空内容。
