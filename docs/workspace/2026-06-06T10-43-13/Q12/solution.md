## status
solved

## 求解过程

### 第一步：计算加权平均 CPI

题干给出三类指令的占比与 CPI：
- 40% 的指令 CPI = 1
- 40% 的指令 CPI = 2
- 20% 的指令 CPI = 4

加权平均 CPI：

$$CPI = 0.4 \times 1 + 0.4 \times 2 + 0.2 \times 4 = 0.4 + 0.8 + 0.8 = 2.0$$

### 第二步：计算总周期数

$$\text{总周期数} = IC \times CPI = 4 \times 10^6 \times 2 = 8 \times 10^6$$

### 第三步：计算执行时间

$$T = \frac{\text{总周期数}}{f} = \frac{8 \times 10^6}{2 \times 10^9} = 4 \times 10^{-3} \text{ s} = 4 \text{ ms}$$

### 第四步：计算 MIPS

$$MIPS = \frac{f}{CPI \times 10^6} = \frac{2 \times 10^9}{2 \times 10^6} = 1000 \text{ MIPS}$$

### 选项分析

- **A（2 ms, 2000 MIPS）**：假设所有指令 CPI=1，忽略指令 CPI 差异，时间偏低、MIPS 偏高，错误。
- **B（4 ms, 1000 MIPS）**：与计算结果完全吻合，正确。
- **C（8 ms, 500 MIPS）**：假设所有指令 CPI=4（取最大 CPI），时间偏高、MIPS 偏低，错误。
- **D（4 ms, 2000 MIPS）**：执行时间正确但 MIPS 计算遗漏了 CPI（直接用 f/10⁶），错误。

## 最终答案

**B: 4 ms，1000 MIPS**
