## status
solved

## 求解过程

本题为数值计算题，考察扩展操作码下指令字长的最小位数。

设指令字长为 \(L\) 位，每个地址字段为 6 位。

三地址指令需要 3 个地址字段，因此地址字段共占：

\[
3 \times 6 = 18 \text{ 位}
\]

所以三地址指令中操作码字段长度为：

\[
L - 18
\]

若操作码字段为 \(k\) 位，则三地址格式最多提供：

\[
2^k
\]

种一级操作码。

题目要求有 30 条三地址指令，因此至少要占用 30 个一级操作码。

对于扩展操作码，未用于三地址指令的一级操作码可以作为二地址指令的扩展入口。二地址指令只需要 2 个地址字段，占：

\[
2 \times 6 = 12 \text{ 位}
\]

相比三地址格式少用 1 个地址字段，即多出 6 位可作为扩展操作码。因此，每保留 1 个一级操作码，可扩展出：

\[
2^6 = 64
\]

条二地址指令。

题目要求二地址指令 130 条，所以需要保留的一级操作码个数为：

\[
\left\lceil \frac{130}{64} \right\rceil = 3
\]

因此一级操作码总数至少要满足：

\[
30 + 3 = 33
\]

即：

\[
2^k \ge 33
\]

因为：

\[
2^5 = 32 < 33
\]

\[
2^6 = 64 \ge 33
\]

所以：

\[
k = 6
\]

于是指令字长至少为：

\[
L = 18 + 6 = 24 \text{ 位}
\]

代码验证思路如下：

```python
import math

three_address_instruction_count = 30
two_address_instruction_count = 130
address_field_bits = 6
address_field_count_for_three_address = 3

three_address_bits = address_field_count_for_three_address * address_field_bits

extension_capacity_per_reserved_opcode = 2 ** address_field_bits
reserved_opcode_count = math.ceil(
    two_address_instruction_count / extension_capacity_per_reserved_opcode
)

required_primary_opcode_count = (
    three_address_instruction_count + reserved_opcode_count
)

primary_opcode_bits = math.ceil(math.log2(required_primary_opcode_count))
instruction_length_bits = three_address_bits + primary_opcode_bits

print("三地址字段位数:", three_address_bits)
print("每个保留一级操作码可扩展二地址指令数:", extension_capacity_per_reserved_opcode)
print("二地址指令需要保留一级操作码数:", reserved_opcode_count)
print("一级操作码总需求:", required_primary_opcode_count)
print("一级操作码位数:", primary_opcode_bits)
print("ANSWER:", instruction_length_bits)
```

运行结果对应：

\[
ANSWER: 24
\]

### 选项分析

A. 23位  
若指令字长为 23 位，则三地址指令操作码位数为：

\[
23 - 18 = 5
\]

只能提供：

\[
2^5 = 32
\]

个一级操作码。但三地址指令需要 30 个，二地址指令还至少需要保留 3 个扩展入口，总需求为 33 个，32 个不够，因此错误。

B. 24位  
若指令字长为 24 位，则三地址指令操作码位数为：

\[
24 - 18 = 6
\]

可提供：

\[
2^6 = 64
\]

个一级操作码。用 30 个表示三地址指令，保留 3 个扩展为二地址指令，可表示：

\[
3 \times 64 = 192
\]

条二地址指令，满足 130 条要求。因此正确。

C. 25位  
25 位也能满足要求，但题目问“至少”，24 位已经满足，因此 25 位不是最小值，错误。

D. 32位  
32 位也能满足要求，但远大于最小所需位数，错误。

## 最终答案

- 正确答案：B
  - 理由：三地址指令地址字段共 18 位，一级操作码至少需要满足 \(2^k \ge 30 + \lceil 130/64 \rceil = 33\)，故 \(k=6\)，指令字长至少为 \(18+6=24\) 位。
