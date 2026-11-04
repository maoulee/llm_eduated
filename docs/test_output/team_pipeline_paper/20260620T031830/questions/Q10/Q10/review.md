## status
needs_fix

## stage
solution

## issue_type
adequacy_fail

## findings

### 问题：选项 D 与 A 序列值相同，违反通过条件5（4选项互异），assert 会失败

**证据：**

1. **gen.py 验证段**包含 `assert len(options) == 4`，要求4选项互异。

2. **gen.py 干扰项 D 的实现**（`two_passes_right_side`）：
   - 第一趟使用正确的 `hoare_partition`，与 A 路径完全相同 → p1=7，序列变为 `[2, 5, 4, 3, 9, 7, 10, 12, 15, 18]`
   - 第二趟对右侧子序列 `[8..9]` 即 `[15, 18]` 执行 partition，pivot=15
   - 在 `[15, 18]` 上：i=9, j=9 → i 右移 a[9]=18>15 停 i=9 → j 左移 a[9]=18≥15 j=8 → i=9≥j=8 结束 → a[8] 与 a[8] 交换（无变化）
   - **D 的最终序列 = `[2, 5, 4, 3, 9, 7, 10, 12, 15, 18]`，与 A 完全相同**

3. **solution.md 自身承认**：
   > "注意：本例中 D 与 A 的序列结果相同，但 pivot 位置不同（A 的 p2=0，D 的 p2=8）"

4. **solution.md 验证段声称**：
   > "✓ 4 选项互异"
   
   这与实际矛盾——A 和 D 序列相同，`len({tuple(A), tuple(B), tuple(C), tuple(D)})` = 3，assert 会抛出异常。

5. **通过条件5** 明确要求："4 选项互异：A/B/C/D 四个选项的序列值各不相同（exec 算出后无碰撞）"。当前参数下此条件不满足。

**影响：**
- `assert len(options) == 4` 会失败，gen.py 验证段无法通过
- 选项 D 与 A 序列值相同，考生无法区分，D 作为干扰项失效
- 通过条件5（可证伪的机检特征）未被满足

## fix_instructions

### 修复1：更换序列参数使 D 与 A 产生不同结果（routing=design_direct）

- **fail类型**：adequacy_fail（通过条件5不满足）
- **修改对象**：question.md 中的序列参数 + gen.py 中的 SEQ
- **修改位置**：question.md「参数说明」→ 序列；gen.py 顶部 `SEQ = [...]`
- **当前问题**：当前序列 `[12, 5, 18, 3, 9, 7, 15, 2, 10, 4]` 下，第一趟后右侧子序列 `[15, 18]` 的 partition 不改变序列（15已在正确位置），导致 D 与 A 结果相同
- **修改目标**：选择一个序列，使得第一趟 partition 后右侧子序列的 partition 会产生可见变化（即右侧子序列的 pivot 不在其最终位置），从而 D 与 A 序列值不同
- **最小修改指令**：
  1. 更换 SEQ 为一个新序列（仍保持10个互异正整数、范围1-20）
  2. 重新运行 gen.py 验证 `len(options)==4` 通过
  3. 同步更新 question.md 中的序列参数
  4. 重新生成 solution.md 的逐步推导

### 修复2：修正 solution.md 验证段（routing=write_solution，在修复1之后）

- **fail类型**：doc_unfaithful
- **修改对象**：solution.md 验证段
- **修改位置**：solution.md 末尾「验证」部分
- **当前问题**：声称"✓ 4 选项互异"但实际 A=D
- **修改目标**：修复1完成后，根据新的 exec 输出重写验证段
- **最小修改指令**：根据修复1后的新序列重新推导全部步骤和验证

## keep_unchanged

- gen.py 中 `hoare_partition` 的正确实现逻辑（双指针、先i后j、与a[j]交换）
- 干扰项 B（与a[i]交换）和 C（Lomuto方案）的设计思路
- 题干中 partition 规则的描述（双指针法、首元素基准、第二趟左侧子序列）
- 考察点设计（基准归位位置、指针移动顺序、第二趟范围）

## routing
design_direct
