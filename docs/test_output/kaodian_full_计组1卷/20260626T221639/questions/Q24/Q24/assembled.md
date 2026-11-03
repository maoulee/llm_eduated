## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: CO-6 > 总线 > 总线概述 > 总线性能指标
- primary_target_name: 总线带宽
- question_type: subjective
- examination_mode: 计算型——总线带宽

### 难度目标
- k_target: K1=2,K2=4,K3=2,K4=2,K5=1
- difficulty_level: 2
- difficulty_rationale: 核心考察点为代入总线带宽公式计算，含 bit→Byte、MHz→Hz、除以周期数等多级单位换算，K2=4 为主要难度来源；其余维度较低，整体难度 2

### 结构要求
- sub_question_count: 1（单问计算，6 分）
- question_form: 简答题，题干给总线参数，要求计算带宽（MB/s）
- condition_count: 3（总线数据宽度、时钟频率、每传输周期时钟周期数）
- distractor_strategy: 不适用（主观题，无选项干扰；难度通过参数选取和单位换算区分）

### 参数约束
- 总线数据宽度 W: 取值 {16, 32, 64} bit，建议取 32 或 64
- 总线时钟频率 f: 取值 100-500 MHz 范围内
- 每传输周期时钟周期数 n: 取值 1-4，建议 n≥2 以增加公式复杂度
- 一致性约束: B = (W / 8) × (f × 10⁶) / n (MB/s)，结果须为正数且在合理带宽量级（100-2000 MB/s）
- 避免退化: 参数组合应使最终结果非平凡整数（非整百整千），保证单位换算步骤不可跳过

### 参考经验摘要
- 历史模式: 计算型——给定总线参数（宽度、频率、周期数）求带宽，408 经典考法
- 难度锚点: K2=4 为主，集中在多级单位换算（bit→Byte / MHz→Hz / 除周期数）
- 典型陷阱: ①忘记除以周期数 n；②bit 与 Byte 混淆；③MHz 未转 Hz 直接代入
