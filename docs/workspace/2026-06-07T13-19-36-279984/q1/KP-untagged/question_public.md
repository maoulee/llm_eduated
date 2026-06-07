## status
draft


## 题干
# 408考研数据结构综合应用题

## 题目

已知一棵初始为空的AVL树（平衡二叉搜索树），依次插入以下关键字序列：10, 20, 30, 5, 15, 12, 25, 22, 30（最后一个30与已有节点重复，按BST规则不插入）。AVL树中每个节点的平衡因子定义为：左子树高度减去右子树高度。当某节点的平衡因子绝对值大于1时，需进行旋转操作恢复平衡。

AVL树插入操作的伪代码如下（部分代码缺失，用下划线标注）：

```
AVL_Insert(T, key):
    if T == NULL:
        T = new Node(key)
        return T
    if key < T.key:
        T.left = AVL_Insert(T.left, key)
    else if key > T.key:
        T.right = AVL_Insert(T.right, key)
    else:
        return T  // 重复关键字不插入
    
    update_height(T)
    balance_factor = get_balance(T)
    
    // LL型：左左旋转
    if balance_factor > 1 and key < T.left.key:
        return right_rotate(T)
    
    // RR型：右右旋转
    if balance_factor < -1 and key > T.right.key:
        return left_rotate(T)
    
    // LR型：左右旋转
    if balance_factor > 1 and key > T.left.key:
        T.left = left_rotate(T.left)
        return right_rotate(T)
    
    // RL型：右左旋转
    if balance_factor < -1 and key < T.right.key:
        T.right = right_rotate(T.right)
        return left_rotate(T)
    
    return T

right_rotate(y):
    x = y.left
    T3 = x.right
    x.right = y
    y.left = T3
    update_height(y)
    update_height(x)
    return x

left_rotate(x):
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    update_height(x)
    update_height(y)
    return y
```

请回答下列问题：

### (1) （3分）

依次插入关键字10、20、30后，画出此时的AVL树结构，并计算根节点的平衡因子。说明插入30后是否需要进行旋转操作，若需要，指出旋转类型及旋转中心节点。

### (2) （4分）

基于(1)中得到的AVL树，继续依次插入关键字5、15。画出插入15完成（含必要的旋转操作）后的AVL树结构，并列出此时树中所有非叶子节点的平衡因子值。

### (3) （3分）

基于(2)中得到的AVL树，继续插入关键字12、25、22。画出插入22完成（含必要的旋转操作）后的AVL树结构，并说明插入22过程中是否触发了旋转操作，若触发，指出失衡节点、旋转类型及旋转后的根节点关键字。

### (4) （3分）

基于(3)中得到的最终AVL树，完成以下任务：
- 计算该树的高度（根节点所在层为第1层），并给出该树的中序遍历序列。
- 补全上述伪代码中 `update_height(T)` 函数的实现（用伪代码描述，不超过3行）。
- 说明AVL树旋转操作为何不会破坏二叉搜索树的有序性。

---