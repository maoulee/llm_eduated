## 题目

某Cache命中率为95%，Cache访问时间为10ns，主存访问时间为100ns；若Cache缺失则先访问Cache再访问主存。平均访问时间为（）。

## 选项

A. 14.5ns  
B. 15ns  
C. 20ns  
D. 105ns  

## 求解过程

**已知参数**：
- Cache命中率 $H = 95\% = 0.95$
- Cache缺失率 $M = 1 - H = 5\% = 0.05$
- Cache访问时间 $T_c = 10\text{ns}$
- 主存访问时间 $T_m = 100\text{ns}$

**访问策略**：若Cache缺失则先访问Cache再访问主存（即每次访问都先查Cache，命中则结束，缺失则再访问主存）。

**方法1：按命中/缺失分类计算**

- 命中时：只访问Cache，耗时 $T_c = 10\text{ns}$
- 缺失时：先访问Cache再访问主存，耗时 $T_c + T_m = 10 + 100 = 110\text{ns}$

$$
\begin{aligned}
T_{avg} &= H \times T_c + M \times (T_c + T_m) \\
&= 0.95 \times 10 + 0.05 \times (10 + 100) \\
&= 9.5 + 0.05 \times 110 \\
&= 9.5 + 5.5 \\
&= 15\text{ns}
\end{aligned}
$$

**方法2：等价公式（每次必访Cache + 缺失时额外访主存）**

$$
\begin{aligned}
T_{avg} &= T_c + M \times T_m \\
&= 10 + 0.05 \times 100 \\
&= 10 + 5 \\
&= 15\text{ns}
\end{aligned}
$$

两种方法结果一致，平均访问时间为 **15ns**。

**选项分析**：
- A. 14.5ns — 错误。对应 $T_{avg} = H \times T_c + M \times T_m = 0.95 \times 10 + 0.05 \times 100 = 14.5\text{ns}$，即缺失时漏算了Cache访问时间。
- B. 15ns — **正确**。
- C. 20ns — 错误。对应命中率/缺失率代入关系处理不当形成的偏大估计。
- D. 105ns — 错误。对应 $T_{avg} = T_c + H \times T_m = 10 + 0.95 \times 100 = 105\text{ns}$，即误将命中率用于主存访问惩罚项（应使用缺失率）。

## 答案

**B. 15ns**

## 设计说明

- 考察模式：计算型——公式应用与指标换算
- 知识点：Cache平均访问时间
- 难度：K2-K3公式应用型，带轻度语义辨析
- 核心考点：正确区分命中访问与缺失访问的时间构成，掌握 $T_{avg} = T_c + M \times T_m$ 公式
- 干扰项策略：A项针对漏算缺失时Cache访问时间的错误；D项针对误用命中率代替缺失率的错误
