## status
solved

## 求解过程

本题包含具体 8 位补码、加法、减法和标志位计算，属于数值题。按 8 位补码封闭运算规则，所有 ALU 结果只保留低 8 位。

参数校验与代码验证要点如下：

- 8 位机器字长：模数为 \(2^8=256\)
- 带符号补码范围：\(-128 \sim 127\)
- 无符号范围：\(0 \sim 255\)
- R1 真值为 \(-72\)，在范围内
- R2 真值为 \(+95\)，在范围内
- 加法与减法均按模 256 低 8 位结果计算

可直接运行的 `solve.py` 验证逻辑如下：

```python
word_bits = 8
modulus = 1 << word_bits
max_unsigned = modulus - 1
signed_min = -(1 << (word_bits - 1))
signed_max = (1 << (word_bits - 1)) - 1

r1_signed = -72
r2_signed = 95

assert signed_min <= r1_signed <= signed_max
assert signed_min <= r2_signed <= signed_max

def to_u8(value):
    return value % modulus

def to_signed8(value):
    value = value % modulus
    if value >= (1 << (word_bits - 1)):
        return value - modulus
    return value

def bin8(value):
    return format(value % modulus, "08b")

def hex8(value):
    return format(value % modulus, "02X")

r1 = to_u8(r1_signed)
r2 = to_u8(r2_signed)

sum_full = r1 + r2
r3 = sum_full % modulus
cf_add = 1 if sum_full >= modulus else 0
of_add = 1 if ((r1 ^ r3) & (r2 ^ r3) & 0x80) != 0 else 0
zf_add = 1 if r3 == 0 else 0
sf_add = 1 if (r3 & 0x80) != 0 else 0

neg_r1 = to_u8(-to_signed8(r1))
sub_full = r3 + neg_r1
r4 = sub_full % modulus

print("R1:", bin8(r1), "0x" + hex8(r1))
print("R2:", bin8(r2), "0x" + hex8(r2))
print("R1 + R2 full:", sum_full, "low8:", bin8(r3), "0x" + hex8(r3))
print("CF:", cf_add, "OF:", of_add, "ZF:", zf_add, "SF:", sf_add)
print("[-R1]补:", bin8(neg_r1), "0x" + hex8(neg_r1))
print("R3 - R1 low8:", bin8(r4), "0x" + hex8(r4))
print("R4 signed:", to_signed8(r4))
print("R4 unsigned:", r4)
print("ANSWER: R1=10111000B=0xB8; R2=01011111B=0x5F; R3=00010111B=0x17, CF=1, OF=0, ZF=0, SF=0; R4=01011111B=0x5F, signed=95, unsigned=95")
```

代码验证输出结论：

```text
R1: 10111000 0xB8
R2: 01011111 0x5F
R1 + R2 full: 279 low8: 00010111 0x17
CF: 1 OF: 0 ZF: 0 SF: 0
[-R1]补: 01001000 0x48
R3 - R1 low8: 01011111 0x5F
R4 signed: 95
R4 unsigned: 95
ANSWER: R1=10111000B=0xB8; R2=01011111B=0x5F; R3=00010111B=0x17, CF=1, OF=0, ZF=0, SF=0; R4=01011111B=0x5F, signed=95, unsigned=95
```

### 子问题(1)

R1 的带符号真值为 \(-72\)。8 位补码负数的机器数可按模 \(256\) 求得：

\[
[-72]_{\text{补}} = 256 - 72 = 184
\]

184 的二进制表示为：

\[
184 = 10111000_2
\]

因此：

\[
R1 = 10111000_2 = B8H
\]

R2 的带符号真值为 \(+95\)，正数补码与原码相同：

\[
95 = 64 + 16 + 8 + 4 + 2 + 1
\]

所以二进制为：

\[
01011111_2
\]

因此：

\[
R2 = 01011111_2 = 5FH
\]

### 子问题(2)

第 1 步执行：

\[
R1 + R2
\]

代入机器数：

\[
10111000_2 + 01011111_2
\]

也就是：

\[
B8H + 5FH = 117H
\]

ALU 只保留低 8 位，因此：

\[
R3 = 17H = 00010111_2
\]

从无符号角度看：

\[
184 + 95 = 279
\]

由于 \(279 > 255\)，产生最高位进位，因此：

\[
CF = 1
\]

从带符号补码角度看：

\[
-72 + 95 = 23
\]

23 在 8 位带符号补码范围 \(-128 \sim 127\) 内，并且两个加数符号不同，补码加法不会发生带符号溢出，因此：

\[
OF = 0
\]

低 8 位结果为：

\[
00010111_2
\]

该结果不是 0，因此：

\[
ZF = 0
\]

该结果最高位为 0，因此符号位为正：

\[
SF = 0
\]

所以第 1 步结果为：

\[
R3 = 00010111_2 = 17H
\]

标志位为：

\[
CF=1,\ OF=0,\ ZF=0,\ SF=0
\]

### 子问题(3)

第 2 步执行：

\[
R3 - R1
\]

减法由：

\[
R3 + [-R1]_{\text{补}}
\]

实现。

已知：

\[
R3 = 00010111_2 = 17H
\]

R1 的带符号真值为 \(-72\)，所以：

\[
-R1 = +72
\]

\[
[+72]_{\text{补}} = 01001000_2 = 48H
\]

因此 ALU 实际执行：

\[
17H + 48H = 5FH
\]

即：

\[
00010111_2 + 01001000_2 = 01011111_2
\]

所以：

\[
R4 = 01011111_2 = 5FH
\]

在带符号补码语义下，最高位为 0，表示正数：

\[
R4 = +95
\]

在无符号语义下：

\[
01011111_2 = 95
\]

因此 R4 的解释为：

- 带符号补码语义：\(+95\)
- 无符号语义：\(95\)

### 子问题(4)

同一个 8 位加法器能够同时用于带符号整数和无符号整数加减运算，是因为底层硬件只对 8 位位模式进行模 \(2^8\) 的二进制加法。无论操作数被上层解释为带符号数还是无符号数，加法器执行的低 8 位运算规则都是相同的。

例如第 1 步中，硬件实际计算的是：

\[
B8H + 5FH = 117H
\]

保留低 8 位后得到：

\[
17H
\]

这个位模式从带符号角度解释为：

\[
-72 + 95 = 23
\]

从无符号角度解释则是：

\[
184 + 95 = 279
\]

低 8 位同样为 23，但无符号运算产生进位，因此 CF=1；带符号运算结果没有超出 \(-128 \sim 127\)，因此 OF=0。

这说明硬件结果本身只是一个 8 位位模式，硬件不会天然区分“有符号”或“无符号”。带符号语义和无符号语义是上层程序或指令解释方式决定的。对应地，CF 主要服务于无符号加减法的进位或借位判断，OF 主要服务于带符号补码加减法的溢出判断。

## 最终答案

- (1)  
  - \(R1 = 10111000_2 = B8H\)
  - \(R2 = 01011111_2 = 5FH\)

- (2)  
  - \(R1 +
