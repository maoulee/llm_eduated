## status
solved

## 求解过程

本题涉及 CPU 执行时间公式及加权 CPI 计算，属于数值计算题。

### 已知参数
- 主频 f = 2 GHz = 2 × 10⁹ Hz
- 总指令数 IC = 8 × 10⁶
- 75% 的指令 CPI = 2
- 25% 的指令 CPI = 6

### 步骤1：计算加权平均 CPI

$$CPI_{avg} = 0.75 \times 2 + 0.25 \times 6 = 1.5 + 1.5 = 3.0$$

### 步骤2：计算总时钟周期数

$$\text{总周期数} = IC \times CPI_{avg} = 8 \times 10^6 \times 3 = 2.4 \times 10^7$$

### 步骤3：计算执行时间

$$T = \frac{\text{总周期数}}{f} = \frac{2.4 \times 10^7}{2 \times 10^9} = 1.2 \times 10^{-2} \text{ s} = 12 \text{ ms}$$

### 干扰项分析
- **A (8 ms)**：取低 CPI 类的值（CPI=2），$8\times10^6 \times 2 / (2\times10^9) = 8$ ms，错误地认为所有指令 CPI 都为 2。
- **C (16 ms)**：取算术平均 CPI=(2+6)/2=4，$8\times10^6 \times 4 / (2\times10^9) = 16$ ms，错误地使用简单平均而非加权平均。
- **D (24 ms)**：取高 CPI 类的值（CPI=6），$8\times10^6 \times 6 / (2\times10^9) = 24$ ms，错误地认为所有指令 CPI 都为 6。

## 最终答案

**B: 12 ms**
