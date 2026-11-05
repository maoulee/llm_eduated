## status

draft

## blueprint_contract

- slot_id: Q45
- question_type: 综合应用题
- score: 10
- target_subject: 存储器层次结构与虚拟内存管理
- target_family: 组成原理-3 > 存储系统 > 虚拟存储器
- primary_target_name: 虚拟存储器与Cache的协同工作
- examination_mode: 虚拟-Cache协同映射追踪结构
- k_target: K3-K5跨域耦合型
- difficulty_level: 5
- should_be:
  - 以"地址转换链路"为核心，考察从虚拟地址到物理地址再到Cache数据块的完整路径推演
  - 重点考察层级间的字段对应关系
  - 跨越多个存储层次且状态依赖明显
  - 需完成虚拟地址字段划分、页表/TLB转换和Cache映射判断
- should_not_be:
  - 不考察单一知识点内部问题
  - 不脱离地址转换链路做纯概念辨析
  - 不将Cache映射建立在虚拟地址之上
- hard_constraints:
  - 综合应用题，10分
  - 难度5，K3-K5跨域耦合型
  - 考察模式必须为"虚拟-Cache协同映射追踪结构"

## route

- question_form: 综合应用题（共享题干 + 子问题链）
- question_type: mixed（概念推导 + 数值计算 + 状态追踪）
- requires_parameter_verification: true
- requires_solver: true
- requires_code: false

## core_knowledge_intent

- must_test:
  - 虚拟地址到物理地址的转换机制（页号提取、页表/TLB查表、物理页号拼接页内偏移）
  - Cache映射机制（物理地址的Tag/Index/Block Offset字段划分与命中判断）
  - 虚拟地址字段与物理地址字段的对应关系（页内偏移 = Block Offset + 可能的额外偏移）
- must_not_shift_to:
  - 不偏移为纯页表结构计算题（如只考页表项大小、页表总大小）
  - 不偏移为纯Cache容量/行数计算题（脱离地址转换链路）
- coverage_success_criteria:
  - 学生需完整走完"虚拟地址字段划分 → 页表转换 → 物理地址字段划分 → Cache映射判断"链路
  - 至少涉及一次TLB与Cache的交互分析或命中率统计

## expected_reasoning_actions

- 根据系统参数（虚拟/物理地址位数、页大小、Cache容量、相联度、块大小）推导虚拟地址各字段（VPN、Page Offset）的位数
- 根据系统参数推导物理地址各字段（PPN、Page Offset）及Cache映射字段（Tag、Index、Block Offset）的位数
- 从给定虚拟地址中提取页号（VPN）和页内偏移
- 通过页表（或TLB）查找，将虚拟页号转换为物理页号，拼接页内偏移得到物理地址
- 从物理地址中提取Cache映射所需的Tag、Index、Block Offset字段
- 根据Index定位Cache行，比较Tag判断是否命中
- 若涉及多次访问，追踪Cache状态变化（如替换策略下的行更新）
- 综合多次访问结果，统计TLB命中率或Cache命中率

## question_structure_plan

- shared_context: 给出系统参数（虚拟地址位数、物理地址位数、页大小、Cache容量、相联度、块大小、替换策略等），以及页表/TLB的初始状态或页表内容
- sub_question_chain:
  - (1) 地址格式推导：写出虚拟地址和物理地址的字段划分及各字段位数
  - (2) 地址转换追踪：给定一个或多个虚拟地址，完成页表转换，写出对应的物理地址
  - (3) Cache映射判断：对转换后的物理地址进行Cache映射，给出Tag/Index值并判断命中与否
  - (4) 综合分析：统计命中率，或分析TLB缺失与Cache命中的交互情况
- dependency_pattern: 强依赖链——(1)是(2)的前提，(2)是(3)的前提，(3)是(4)的前提；前一步字段划分错误将导致后续全部错误

## parameter_plan

- parameter_slots:
  - virtual_address_bits: 虚拟地址总位数，候选范围 24-36，用于推导VPN和Page Offset位数
  - physical_address_bits: 物理地址总位数，候选范围 20-32，用于推导PPN和Cache映射字段位数
  - page_size: 页面大小，候选范围 2^10-2^12（1KB-4KB），决定Page Offset位数
  - cache_capacity: Cache总容量，候选范围 2^10-2^14（1KB-16KB），结合相联度和块大小决定Index位数
  - associativity: Cache相联度，候选范围 1-8，决定每组行数
  - block_size: Cache块大小，候选范围 2^5-2^8（32B-256B），决定Block Offset位数
  - replacement_policy: Cache替换策略，候选范围 FIFO/LRU，影响多次访问的状态追踪
  - tlb_entries: TLB容量，候选范围 4-16，影响TLB命中率分析
  - page_table_entries: 页表内容，需给出若干页号到物理页号的映射关系
  - virtual_addresses: 待追踪的虚拟地址序列，2-4个，用于多步状态追踪
- validation_targets:
  - 虚拟地址位数 ≥ 物理地址位数（或合理设定）
  - Page Offset位数 = log2(page_size)
  - VPN位数 = virtual_address_bits - Page Offset位数
  - PPN位数 = physical_address_bits - Page Offset位数
  - Block Offset位数 = log2(block_size)
  - Index位数 = log2(cache_capacity / (associativity * block_size))
  - Tag位数 = physical_address_bits - Index位数 - Block Offset位数
  - 所有位数必须为非负整数
  - 页表中给出的页号必须在VPN位数可表示的范围内
  - 虚拟地址必须在虚拟地址位数可表示的范围内
- adjustment_priority:
  - 优先调整 cache_capacity 和 associativity 使 Index 位数为合理整数
  - 其次调整 block_size 使 Block Offset 与 Page Offset 的关系清晰
  - 最后调整虚拟地址序列确保覆盖命中/缺失多种情况

## terminology_and_expression_constraints

- required_terms:
  - 虚拟地址、物理地址、页号（VPN）、页内偏移（Page Offset）
  - 物理页号（PPN）、页表、TLB（快表）
  - Cache标记（Tag）、Cache索引（Index）、块内偏移（Block Offset）
  - 命中、缺失（未命中）、替换策略
- required_qualifiers:
  - 提及Cache映射时必须明确"基于物理地址"
  - 提及页表转换时必须明确"页内偏移保持不变"
  - 提及TLB时必须说明TLB中缓存的是"页号到物理页号的映射"
- avoid_phrases:
  - "用虚拟地址查Cache" → 应改为"用物理地址的Index和Tag查Cache"
  - "页号就是Cache的Index" → 应改为"物理地址中的Index字段用于定位Cache行"
  - "地址直接映射到Cache" → 应改为"物理地址按字段划分后，Index定位Cache行，Tag用于比对"
- standard_rewrites:
  - bad: "计算Cache的组号" → good: "从物理地址中提取Index字段值"
  - bad: "看TLB里有没有这个地址" → good: "在TLB中查找该虚拟页号对应的表项"
  - bad: "地址映射到Cache第几行" → good: "物理地址的Index字段值为X，定位到Cache第X行"

## audit_focus

- final_review_must_check:
  - 题干中系统参数是否完整（虚拟/物理地址位数、页大小、Cache容量、相联度、块大小）
  - 地址字段划分是否自洽（各字段位数之和等于地址总位数）
  - Cache映射是否明确基于物理地址而非虚拟地址
  - 页表内容是否与虚拟地址中的页号范围匹配
  - 子问题链是否形成强依赖（前一步是后一步的前提）
  - 是否设置了典型陷阱（如诱导学生用虚拟地址做Cache映射）
- solve_output_should_contain:
  - 虚拟地址字段划分表（字段名、位数）
  - 物理地址字段划分表（字段名、位数）
  - 每个虚拟地址的转换过程（VPN提取 → 页表查找 → PPN拼接 → 物理地址）
  - 每个物理地址的Cache映射过程（Tag/Index/Block Offset提取 → 命中判断）
  - 命中率统计或TLB-Cache交互分析
- fail_if_missing:
  - 缺少地址字段位数推导
  - 缺少页表转换步骤
  - Cache映射使用了虚拟地址字段
  - 缺少命中/缺失判断
  - 参数自洽性不满足（位数之和≠地址总位数，或Index/Tag位数为负）
