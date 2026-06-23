# 递归逆序输出链表 — 解析

## 答案

**(1)** 空白处①填入：`ReversePrint(L->next);`

**(2)** 函数功能：逆序输出单链表中各结点的数据值（不修改链表结构）

---

## 解析

### 一、填空分析

函数 `ReversePrint` 采用递归方式处理链表。要使输出为**逆序**，核心逻辑是：

> **先递归到链表尾部，再在回溯过程中输出结点数据。**

因此，递归调用 `ReversePrint(L->next)` 必须放在 `printf` 语句**之前**，这样执行流程为：

1. 进入函数 → 递归调用下一个结点（继续深入）
2. 直到 `L == NULL` 时终止递归
3. 从尾部开始回溯，逐层执行 `printf` 输出

```c
void ReversePrint(LinkList L) {
    if (L == NULL)
        return;
    ReversePrint(L->next);   // ① 递归调用在前 → 先深入
    printf("%d ", L->data);   // 回溯后输出 → 逆序
}
```

### 二、执行过程模拟

以链表 `1 → 2 → 3 → 4 → 5` 为例，模拟 `ReversePrint` 的执行过程：

```
[进入] L->data=1
  → 先执行 ReversePrint(L->next)
  [进入] L->data=2
    → 先执行 ReversePrint(L->next)
    [进入] L->data=3
      → 先执行 ReversePrint(L->next)
      [进入] L->data=4
        → 先执行 ReversePrint(L->next)
        [进入] L->data=5
          → 先执行 ReversePrint(L->next)
          [调用栈展开] L==NULL, return
        [回溯] printf(5)
      [回溯] printf(4)
    [回溯] printf(3)
  [回溯] printf(2)
[回溯] printf(1)
```

**输出顺序**：`5 4 3 2 1`（逆序）

**原始顺序**：`1 2 3 4 5`

### 三、关键验证

1. **输出为逆序**：`[5, 4, 3, 2, 1]` ✓
2. **链表结构未被修改**：遍历链表仍为 `[1, 2, 3, 4, 5]` ✓
3. **递归调用在 printf 之前**：代码结构中 `ReversePrint(L->next)` 行号 < `printf` 行号 ✓
4. **递归终止条件存在**：`if (L == NULL) return;` ✓

### 四、易错点

- **递归调用与 printf 的顺序**：若将 `printf` 放在递归调用之前，则输出为正序（`1 2 3 4 5`），而非逆序。
- **功能描述**：该函数仅**输出**数据，**不修改**链表结构。应描述为"逆序输出"，而非"逆序链表"或"反转链表"。
