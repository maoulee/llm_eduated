"""K1-K5 Cognitive Radar Scale — 1-5 scoring system for 408 exam question analysis.

Five dimensions of cognitive demand, each scored 1-5:
  K1: Base knowledge demand (concept/terminology/formula recall)
  K2: Single-step substitution demand (direct calculation/conversion)
  K3: Mechanism reasoning demand (multi-step sequential reasoning)
  K4: Condition routing demand (hidden premises, traps, mechanism switching)
  K5: Cross-domain linkage demand (crossing subsystem boundaries)

Design principle: floor=1 (any question consumes at least minimal cognitive resources).
"""

COGNITIVE_RADAR_SCALE = """\
### K1-K5 认知雷达 1-5 分评定标准

K1 基础认知需求（需要调用概念/术语/公式记忆的程度）:
  1=微弱: 仅需日常常识词汇，几乎不需要 408 专业记忆
  2=较低: 需要 408 基础名词，但概念模糊也能顺着题干做
  3=标准: 必须准确记忆某个核心概念/公式的定义才能入题
  4=较高: 需精准辨析极易混淆的概念，或提取冷门细节公式
  5=极高: 纯概念辨析题，全凭记忆准确度，毫无推演绕过余地

K2 单步代入需求（需要执行单次直接计算/转换的程度）:
  1=微弱: 几乎无计算，或仅需极简单心算
  2=较低: 需一步简单公式代入，数字友好（多为 2 的幂）
  3=标准: 需代入常规公式计算，可能涉及非 2 的幂次或小数
  4=较高: 单步计算繁杂/易算错，或需多级单位统一换算
  5=极高: 整题核心就是卡这一步复杂计算，算错全盘皆输

K3 机制推演需求（需要在明确规则下多步串行推演的程度）:
  1=微弱: 无需推演流程，得出答案不需走多步
  2=较低: 仅需 2 步以内的极简推导，路径唯一
  3=标准: 需按固定"说明书"走完 3-5 步流程，路径唯一
  4=较高: 推演步数 >5 步，或需维持动态状态更新
  5=极高: 极长程推演，极度消耗工作记忆，中间错一步全盘皆输

K4 条件路由需求（需要识别隐含前提/避开暗坑/切换机制的程度）:
  1=微弱: 题面字面意思即全部，无任何隐藏陷阱
  2=较低: 存在常规注意点，408 考生基本不会踩坑
  3=标准: 存在明确的陷阱词，不触发就会用错公式
  4=较高: 隐含前提很深，必须依靠对机制本质的理解才能路由
  5=极高: 整题专为反直觉设计，顺向常规思维 100% 掉坑

K5 跨域联动需求（需要跨越不同子系统/模块传递状态的程度）:
  1=微弱: 单一知识点内部解决，不涉及其他系统
  2=较低: 提及其他系统名词，但无数据/逻辑实质性关联
  3=标准: 两系统单向拼接，A 的输出直接当 B 的输入
  4=较高: A 系统的状态/异常会改变 B 系统的执行逻辑
  5=极高: 多系统深度耦合，需来回交叉推演与双向验证
"""

COGNITIVE_RADAR_XML = """\
<cognitive_radar>
  <K1_demand>1-5整数。1=微弱常识, 2=基础名词, 3=标准需记忆, 4=易混辨析, 5=纯概念题</K1_demand>
  <K2_demand>1-5整数。1=极简心算, 2=一步简单代入, 3=标准公式计算, 4=复杂单步换算, 5=纯卡计算</K2_demand>
  <K3_demand>1-5整数。1=无需推演, 2=两步内极简, 3=标准3-5步固定推演, 4=长程>5步推演, 5=极长程易断链</K3_demand>
  <K4_demand>1-5整数。1=题面即全部, 2=常规注意点, 3=明确陷阱词需切换机制, 4=深隐含前提需本质理解, 5=专为反直觉设计</K4_demand>
  <K5_demand>1-5整数。1=单一系统, 2=提及他系统无关联, 3=单向数据传递, 4=系统状态异常互相影响, 5=多系统深度耦合双向推演</K5_demand>
  <radar_shape_name>根据雷达最高分维度命名，如：K4陷阱型、K3推演型、K5跨域联动型、K1概念型</radar_shape_name>
</cognitive_radar>"""

COGNITIVE_RADAR_MD = """\
- **K1**: 1-5（1=微弱常识, 2=基础名词, 3=标准需记忆, 4=易混辨析, 5=纯概念题）
- **K2**: 1-5（1=极简心算, 2=一步简单代入, 3=标准公式计算, 4=复杂单步换算, 5=纯卡计算）
- **K3**: 1-5（1=无需推演, 2=两步内极简, 3=标准3-5步推演, 4=长程>5步推演, 5=极长程易断链）
- **K4**: 1-5（1=题面即全部, 2=常规注意点, 3=陷阱词切换, 4=深隐含前提, 5=反直觉设计）
- **K5**: 1-5（1=单一系统, 2=提及无关联, 3=单向传递, 4=状态互相影响, 5=深度耦合）
- **radar_shape_name**: 认知雷达形状名称（如 K4陷阱型、K3推演型）"""
