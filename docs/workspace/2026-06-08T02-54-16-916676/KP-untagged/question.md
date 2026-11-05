# AVL树插入与旋转操作

## 题干

给定一组互不相同的正整数关键码序列 {40, 20, 30, 10, 25, 5, 35, 15, 28, 32, 12}，初始时 AVL 平衡二叉树为空。依次将序列中的关键码插入 AVL 树，每次插入后立即检查平衡性，若发现失衡则执行相应的旋转调整，使树重新平衡。

约定：
- 空树高度为 0，只有一个结点的树高度为 1；
- 平衡因子 BF = 左子树高度 − 右子树高度；
- 当某结点的 |BF| > 1 时，该子树失衡，需从**最先**失衡的最小子树开始调整。

## 子问题

**（1）** 全部关键码插入完成后，AVL 树的根结点关键码是多少？此时树的高度是多少？

**（2）** 在整个插入过程中，共发生了几次旋转调整？请按发生顺序，逐一列出每次旋转的类型（LL / LR / RL / RR）以及旋转后该子树新根的关键码。

**（3）** 全部插入完成后，关键码 ⟨P3⟩ 的左孩子和右孩子分别是哪个关键码？（若对应孩子不存在，请回答"空"。）

**（4）** 下面是 AVL 树中 LR 型失衡的双旋调整函数（C 语言），请填写标号 ①～④ 处的空缺，使函数正确完成旋转操作。

```c
typedef struct AVLNode {
    int key;
    struct AVLNode *lchild, *rchild;
    int height;          // 以该结点为根的子树高度
} AVLNode;

void update_height(AVLNode *p);   // 重新计算 p->height

// LR 型双旋调整：A 为最小不平衡子树的根
AVLNode* lr_rotate(AVLNode *A) {
    AVLNode *B = A->lchild;       // A 的左孩子
    AVLNode *C = B->rchild;       // B 的右孩子

    B->rchild = ①;               // C 的左子树挂到 B 的右侧
    A->lchild = ②;               // C 的右子树挂到 A 的左侧
    C->lchild = ③;               // B 成为 C 的左孩子
    C->rchild = ④;               // A 成为 C 的右孩子

    update_height(B);
    update_height(A);
    update_height(C);
    return C;
}
```

## 参数槽位

⟨P1⟩:
  role: seed
  type: sequence[int]
  seed_hint: positive_unique_ints
  used_by: 依次插入 AVL 树的关键码序列，驱动整道题的树构建与旋转过程
  checks:
    - unique
    - length_range_7_to_12
    - triggers_at_least_one_LR_rotation
    - triggers_multiple_rotation_types

⟨P3⟩:
  role: seed
  type: int
  seed_hint: element_of_P1
  used_by: 子问题(3) 中要求查询左右孩子的关键码
  checks:
    - in_P1
    - has_both_children_in_final_tree

## 设计说明

- **考察结构模式**：过程追踪与代码/伪代码实现混合。子问(1)~(3) 为过程追踪——要求考生逐步模拟插入与旋转，追踪树的形态变化；子问(4) 为伪代码填空——考察对 LR 双旋指针调整的底层理解。
- **子问依赖关系**：(1) 是基础（确定最终树根与高度）；(2) 是核心（完整追踪旋转历史，区分度最高）；(3) 依赖 (1) 的最终树形态；(4) 独立考察旋转机制的代码实现，但与 (2) 中实际发生的 LR 旋转形成呼应。
- **should_be**：题目覆盖 AVL 插入、失衡判定、四种旋转类型识别、双旋指针操作，属于 K4 深理解层级；过程追踪需要维持动态状态更新（K3=4~5），伪代码需理解旋转的本质指针重连（K4=4）。
- **should_not_be**：不考察 AVL 删除操作；不考察红黑树或其他平衡树；不要求画图（用结构属性设问代替）。
- **K 值对齐**：目标 K4-K5。K1=3（需准确记忆平衡因子定义与四种旋转判据），K2=2（仅简单高度比较），K3=4~5（多次插入+旋转的动态追踪），K4=4（LR 旋转的隐含指针调整逻辑），K5=1（单一知识点内部）。
- **槽位用途**：P1 为种子序列，其长度和内容决定题目难度——需保证至少 7 个元素以触发足够多的旋转，且必须包含 LR 型旋转以与子问(4)呼应；P3 从最终树中选取一个拥有两个孩子的内部结点，使子问(3)具有实际区分度。
