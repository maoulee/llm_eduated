# 平衡二叉树（AVL）的插入与旋转

## 题干

已知一棵初始为空的平衡二叉树（AVL 树），依次插入关键字序列 ⟨P1⟩。插入过程中采用标准 AVL 平衡调整策略：平衡因子 BF = 左子树高度 − 右子树高度，当某节点的 |BF| > 1 时，对该失衡节点执行旋转调整（LL / LR / RL / RR 四种类型之一），使调整后以该节点为根的子树恢复平衡。

## 子问题

**(1)** 在依次插入上述序列的过程中，哪些插入操作触发了平衡调整？请按插入先后顺序，逐次列出：触发调整的关键字、失衡节点的关键字、以及旋转类型（LL / LR / RL / RR）。

**(2)** 所有关键字插入完毕后，关键字 ⟨P3⟩ 的左孩子和右孩子分别是哪个关键字？若无对应孩子，回答"无"。并求该节点的平衡因子。

**(3)** 下面是 AVL 树中 RR 型旋转（左单旋）调整的伪代码，其中结点 A 为失衡结点（BF = −2），B 为 A 的右孩子（BF = −1）。请填写 ①②③ 三处空白，使代码正确实现 RR 型旋转并返回调整后的子树根节点。

```
RR_Rotate(A):
    B = A.rchild
    A.rchild = ①
    ② = A
    update_height(A)
    update_height(B)
    return ③
```

**(4)** 已知在插入序列 ⟨P1⟩ 的过程中，关键字 ⟨P4⟩ 的插入触发了一次 LR 型双旋。请画出该次 LR 旋转**前后**，以失衡节点为根的子树结构（需标明所有涉及的结点关键字及其左右孩子指针的变化），并说明双旋的两次单旋分别是什么类型。

## 参数槽位

⟨P1⟩:
  role: seed
  type: sequence[int]
  seed_hint: distinct_ints_len_9_to_11
  used_by: 插入序列
  checks:
    - unique_values
    - triggers_at_least_3_rotation_types
    - triggers_at_least_one_LR
    - triggers_at_least_one_RL
    - triggers_at_least_one_LL_or_RR

⟨P2⟩:
  role: derived
  expr: len(P1)
  used_by: 序列长度

⟨P3⟩:
  role: derived
  expr: 按P1构建AVL后，选一棵中间层非叶节点的关键字
  used_by: 子问题(2)指定节点
  checks:
    - exists_in_final_avl
    - has_at_least_one_child

⟨P4⟩:
  role: derived
  expr: 按P1构建AVL过程中，触发LR旋转的那个被插入的关键字
  used_by: 子问题(4)指定关键字
  checks:
    - insertion_triggers_LR_rotation

## 设计说明

- **考察模式**：过程追踪（子问1、2、4）与代码/伪代码填空（子问3）混合
- **子问递进**：
  - (1) 基础——完整过程追踪，要求列出所有旋转事件（K3 机制推演 = 4-5）
  - (2) 标准——最终树结构查询，需从追踪结果中读取（K3 = 4）
  - (3) 代码——RR 旋转伪代码填空，考察指针调整逻辑（K4 条件路由 = 4，需理解旋转本质）
  - (4) 核心——LR 双旋的子树结构画图与两次单旋分解，区分度高（K4 = 4-5）
- **K 难度对齐**：
  - K1 = 3：需准确记忆 AVL 平衡因子定义、四种旋转类型命名规则
  - K2 = 2：高度计算为简单整数加减
  - K3 = 4：插入序列长度 9-11，多步串行推演且需维持动态状态
  - K4 = 4：LR/RL 双旋需识别"新插入节点在子树的哪一侧"才能路由到正确的旋转类型
  - K5 = 1：纯 AVL 单知识点内部解决
- **should_be**：考察 LL/LR/RL/RR 四种旋转的判定与操作、平衡因子计算、指针调整逻辑
- **should_not_be**：不涉及红黑树、不涉及删除操作、不涉及 B 树
