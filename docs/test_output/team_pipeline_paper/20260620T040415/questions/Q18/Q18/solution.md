# 求二叉树中所有叶子结点到根的路径 — 参考答案与解析

## 一、参考答案

### （1）二叉树结点的数据类型定义

```c
typedef struct BiTNode {
    ElemType data;
    struct BiTNode *lchild, *rchild;
} BiTNode, *BiTree;
```

### （2）算法的基本设计思想

采用先序遍历框架，递归过程中用数组 `path[]` 保存从根到当前结点的路径。到达叶子结点（左右子树均为空）时，将 `path` 中保存的路径逆序输出（叶子→根）。递归返回时 `depth--` 撤销当前结点，实现回溯，避免路径污染。

### （3）算法的 C/C++ 代码实现

```c
void LeafToRootPath(BiTree root) {
    ElemType path[MAX_DEPTH];
    int depth = 0;
    DFS_Path(root, path, &depth);
}

void DFS_Path(BiTree node, ElemType path[], int *depth) {
    if (node == NULL) return;

    path[*depth] = node->data;
    (*depth)++;

    if (node->lchild == NULL && node->rchild == NULL) {
        // 叶子结点：逆序输出 path[*depth-1] ... path[0]
        for (int i = *depth - 1; i >= 0; i--) {
            printf("%c", path[i]);
            if (i > 0) printf(" -> ");
        }
        printf("\n");
    } else {
        DFS_Path(node->lchild, path, depth);
        DFS_Path(node->rchild, path, depth);
    }

    (*depth)--;  // 回溯：撤销当前结点
}
```

---

## 二、算法执行过程详解

### 算法核心机制

算法采用**先序遍历 + 回溯法**：

1. **递归深入时**：`path[depth++] = node->data` 保存当前结点到路径数组
2. **叶子判定**：`lchild == NULL && rchild == NULL`（左右子树同时为空）
3. **到达叶子时**：`reversed(path[:depth])` 逆序输出，实现叶子→根方向
4. **递归返回时**：`depth--` 撤销当前结点（回溯），避免路径污染

### 测试用例执行结果

#### 测试树 1：普通二叉树

```
        A
       / \
      B   C
     / \   \
    D   E   F
```

执行结果（3条路径，对应3个叶子 D、E、F）：

```
D -> B -> A
E -> B -> A
F -> C -> A
```

#### 测试树 2：单结点树

```
X
```

执行结果（1条路径）：

```
X
```

#### 测试树 3：空树

执行结果：路径数量 = 0（无输出）

#### 测试树 4：退化左链

```
A -> B -> C -> D
```

执行结果（1条路径，对应唯一叶子 D）：

```
D -> C -> B -> A
```

---

## 三、通过条件验证

| 条件 | 验证内容 | 结果 |
|------|---------|------|
| 条件1：叶子结点判定 | 判定条件为 `lchild == NULL && rchild == NULL`，树1有3个叶子→3条路径，退化树有1个叶子→1条路径 | ✓ 通过 |
| 条件2：回溯撤销路径 | 递归返回时 `(*depth)--` 撤销当前结点，每条路径长度等于对应叶子深度（树1中3条路径长度均为3） | ✓ 通过 |
| 条件3：路径输出方向 | 每条路径首元素为叶子结点（D/E/F），末元素为根结点（A），方向为叶子→根 | ✓ 通过 |
| 条件4：边界条件 | 空树无路径输出；单结点树输出该结点自身作为路径 | ✓ 通过 |
| 条件5：路径完整性 | 路径数 = 叶子数；每条路径包含从叶子到根的所有结点，不含非法结点 | ✓ 通过 |

---

## 四、常见错误分析

1. **叶子结点判定错误**：仅判单侧为空（如 `lchild == NULL`），会误将只有右孩子的结点判为叶子。正确做法是同时判左右子树为空。

2. **忘记回溯撤销**：递归返回时未执行 `depth--`，导致后续路径被之前路径污染，输出结果错误。

3. **路径输出方向错误**：直接正序输出 `path[0] → path[depth-1]`，得到的是根→叶子方向，与题目要求的叶子→根方向相反。

4. **递归终止条件遗漏**：未处理 `node == NULL` 的情况，空树或空子树会导致程序崩溃。
