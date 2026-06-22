## status
draft

## 题干
某计算机的主频为 2 GHz。程序 P 在该计算机上运行时共执行 \(4 \times 10^6\) 条指令，其中 50% 的指令平均 CPI 为 1，25% 的指令平均 CPI 为 2，25% 的指令平均 CPI 为 4。程序 P 的 CPU 执行时间是（ ）。

## 选项
- A: 2 ms
- B: 4 ms
- C: 8 ms
- D: 16 ms

## 答案
正确答案：B

平均 CPI 为：

\[
CPI = 50\% \times 1 + 25\% \times 2 + 25\% \times 4
\]

\[
=0.5+0.5+1=2
\]

CPU 执行时间公式为：

\[
T_{CPU}=\frac{IC \times CPI}{f}
\]

其中，指令条数 \(IC=4 \times 10^6\)，平均 CPI 为 2，主频 \(f=2 \times 10^9 Hz\)。

\[
T_{CPU}=\frac{4 \times 10^6 \times 2}{2 \times 10^9}
=4 \times 10^{-3}s
=4ms
\]

因此，程序 P 的 CPU 执行时间为 4 ms，选 B。

## 设计说明
- 知识点选取理由：本题围绕 CPU 执行时间公式、平均 CPI 和主频之间的关系展开，符合"计算机系统概述"中计算机性能指标的核心考点。
- 参数选择理由：主频选用 2 GHz，指令条数选用 \(4 \times 10^6\)，比例选用 50%、25%、25%，便于考生进行心算，同时能体现加权平均 CPI 的必要性。
- 干扰策略：A 项对应只考虑部分周期或低估 CPI 的错误；C 项对应单位换算或总周期计算偏大的错误；D 项对应将各类 CPI 简单累加后再代入的错误。
- 难度自评：本题需要准确掌握 \(T_{CPU}=IC \times CPI / f\)，并能计算加权平均 CPI，属于 K1-K2 平衡型、标准难度计算题。
- examination_mode: 计算型——公式应用与单位换算
- difficulty_level: 3
- target_family: 计算机系统概述

## needs_coding
true
