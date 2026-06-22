## status
solved

## 求解过程

### 题型判断
本题包含具体数值参数（主频 2 GHz、指令数 16×10^6、CPI 1.5），需要公式代入计算和单位换算，属于**数值题**。

### 求解步骤

**1. 明确公式**
CPU 执行时间公式：$T_{CPU} = \frac{IC \times CPI}{f}$
- $IC$：指令数
- $CPI$：平均每条指令的时钟周期数
- $f$：主频（Hz）

**2. 参数代入**
- $f = 2 \text{ GHz} = 2 \times 10^9 \text{ Hz}$
- $IC = 16 \times 10^6$
- $CPI = 1.5$

**3. 计算**
$$T_{CPU} = \frac{16 \times 10^6 \times 1.5}{2 \times 10^9} = \frac{24 \times 10^6}{2 \times 10^9} = 12 \times 10^{-3} \text{ s} = 12 \text{ ms}$$

**4. 选项分析**
- A: 8 ms — 错误，遗漏了 CPI（$16 \times 10^6 / 2 \times 10^9 = 8$ ms）
- B: 12 μs — 错误，单位换算错误（应为 ms 而非 μs）
- C: 12 ms — **正确**
- D: 24 ms — 错误，未除以主频

## 最终答案
C: 12 ms