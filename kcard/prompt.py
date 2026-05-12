# kcard/prompts.py (V4 - 最终黄金版，修复大括号转义)

"""
此模块包含知识卡片（KCard）生成流程所需的所有Prompt模板。
所有要求JSON输出的Prompt都经过强化，并包含高质量示例以引导模型。
所有在f-string中使用的JSON示例都已正确使用双大括号 {{}} 进行转义。
"""

# Prompt 1: 用于分批次识别错误知识点（带复杂示例）
ERROR_IDENTIFICATION_PROMPT = """你是一位极其严谨和细致的计算机科学考试阅卷人。你的任务是审查一个复杂问题和多个回答，识别每个回答中具体错误的知识点，并最终汇总所有错误点的出现频率。

**核心指令**:
1.  **逐个审查**: 你必须严格按照编号顺序，独立地分析 `[回答 1]`, `[回答 2]`, ... 中的每一个。
2.  **精确定位**: 将每个错误归因到最直接相关的、具体的技术知识点上。请严格参考下方示例中的粒度。
3.  **汇总与对齐**: 在分析完所有回答后，将识别出的所有错误知识点进行汇总并对齐到一个标准名称下，然后累加它们的出现次数。
4.  **JSON输出**: 你的最终输出必须是一个JSON对象，只包含汇总后的结果。响应必须以 `{{` 开头，以 `}}` 结尾，绝不能包含任何解释性文字或Markdown标记。

---
[示例 - 复杂场景分析]
**这是一个你需要遵循的完整示例，请严格模仿它的分析粒度和输出格式。**
[示例问题]
"在一个含有A, B, C三种资源（数量分别为10, 5, 7）的系统中，T0时刻有P0-P4五个进程，其资源分配情况如下：..."
[示例待评估的回答]
--- [回答 1] ---
"...系统是安全的。安全序列是 <P1,...>。"
--- [回答 2] ---
"...两个条件都满足，所以系统可以立即为P1分配资源..."
--- [回答 3] ---
"...银行家算法可以预防死锁，同时也能避免进程饥饿..."
[示例分析过程 (你的内心思考过程)]
1.  分析`[回答 1]`：错误的核心知识点是“银行家算法安全性检查”。
2.  分析`[回答 2]`：错误的核心知识点是“银行家算法资源请求流程”。
3.  分析`[回答 3]`：错误的核心知识点是“银行家算法基本概念”。
[示例最终JSON输出]
{{
  "银行家算法安全性检查": 1,
  "银行家算法资源请求流程": 1,
  "银行家算法基本概念": 1
}}
---
[正式任务]
[原始问题]
{question}
---
[待评估的N个回答]
{responses_block}
---
生成最终的汇总JSON：
"""

# Prompt 2: 用于将多个批次的统计结果进行最终合并与对齐
KNOWLEDGE_POINT_ALIGNMENT_PROMPT = """你是一个严格执行指令的JSON数据处理工具。你的唯一任务是合并和对齐输入的JSON对象数组。

**任务**: 合并一个JSON数组中所有对象的计数，并将概念相似的键（key）对齐到一个标准名称下。

**输出约束**:
- 你的输出必须是一个JSON对象。
- 响应必须以 `{{` 开头，以 `}}` 结尾。
- **绝对不要**包含任何解释性文本、Markdown标记或其他非JSON内容。

---
[待对齐的知识点统计列表 (JSON数组)]
{error_frequency_jsons}
---
[JSON输出格式示例]
{{
  "银行家算法安全性检查": 10,
  "银行家算法资源请求流程": 4
}}
---
生成合并对齐后的JSON：
"""

# Prompt 3: 用于生成最终的、包含概念和可选代码的知识卡片（带双示例）
KNOWLEDGE_CARD_GENERATION_PROMPT = """你是一位顶级的计算机科学教授和Python专家，你的核心任务是将一个知识点封装成一个包含“理论”和“工具”的、结构化的知识卡片。

**核心任务与逻辑**:
1.  **深入分析**: 拿到一个知识点名称（如“操作码扩展编码原理”），你必须首先深入思考：这个宏观概念之下，是否包含一个或多个**具体的、可计算的、有固定步骤的算法子任务**？
2.  **生成概念定义**: **对于所有知识点**，都必须提供一个清晰、结构化的概念定义。
3.  **生成Python工具**:
    *   如果你在第一步的分析中，识别出了一个具体的算法子任务（例如，从“操作码扩展编码原理”中识别出“计算下一级可用指令空间”的算法），你**必须**为这个子任务提供一个功能完整的Python函数作为“工具”。
    *   如果该知识点纯属理论，确实不包含任何可计算的固定流程（例如“指令集架构的分类”），才可以将 `python_implementation` 字段的值设为 `null`。
4.  **严格遵循示例**: 你的输出必须严格模仿下面示例的结构和质量。

---
[示例 1 - 偏概念理论型知识点]

[输入知识点名称]
"银行家算法基本概念"

[输出JSON]
{{
  "knowledge_point_name": "银行家算法基本概念",
  "error_frequency": 1,
  "concept_definition": {{
    "summary": "银行家算法是一种用于在操作系统中避免死锁的资源分配和调度算法。",
    "key_characteristics": [
      "核心思想：在分配资源前，预先判断这次分配是否会导致系统进入不安全状态，如果会，则拒绝分配，让进程等待。",
      "目的：预防死锁（Deadlock Prevention），而非检测或解除死锁。",
      "与饥饿的关系：算法本身不保证能避免饥饿（Starvation），一个低优先级的进程或资源需求特殊的进程可能长时间得不到满足。",
      "前提条件：需要预知进程的最大资源需求量，且系统中的进程数和资源数是固定的。"
    ]
  }},
  "python_implementation": null
}}
---
[示例 2 - 偏算法实现型知识点]

[输入知识点名称]
"银行家算法安全性检查"

[输出JSON]
{{
  "knowledge_point_name": "银行家算法安全性检查",
  "error_frequency": 3,
  "concept_definition": {{
    "summary": "安全性检查是银行家算法的核心，用于判断系统在某一时刻是否存在一个“安全序列”，从而确定当前状态是否安全。",
    "key_characteristics": [
      "安全序列：一个进程的序列 <P1, P2, ..., Pn>，如果对于每个Pi，它申请的资源可以被当前可用的资源加上所有在它之前的进程Pj所释放的资源所满足。",
      "安全状态：如果系统存在至少一个安全序列，则称系统处于安全状态。不安全状态不一定会导致死锁，但可能导致死锁。",
      "算法本质：这是一个循环检查的过程，模拟所有进程依次执行并释放资源的过程，直到所有进程都能完成。"
    ]
  }},
  "python_implementation": {{
    "description": "该函数接收系统当前状态，检查是否存在一个安全序列。如果存在，则返回True和安全序列；否则返回False和空列表。",
    "function_signature": "def run_safety_check(available: list, allocation: list[list], need: list[list]) -> tuple[bool, list]:",
    "code_body": [
      "    # 初始化",
      "    num_processes = len(allocation)",
      "    num_resources = len(available)",
      "    work = available[:]",
      "    finish = [False] * num_processes",
      "    safe_sequence = []",
      "",
      "    while len(safe_sequence) < num_processes:",
      "        found_process = False",
      "        for i in range(num_processes):",
      "            if not finish[i]:",
      "                if all(need[i][j] <= work[j] for j in range(num_resources)):",
      "                    for j in range(num_resources):",
      "                        work[j] += allocation[i][j]",
      "                    finish[i] = True",
      "                    safe_sequence.append(i)",
      "                    found_process = True",
      "                    break",
      "        if not found_process:",
      "            return False, []",
      "    return True, safe_sequence"
    ],
    "example_usage": "available = [3, 3, 2]; allocation = [[0,1,0], [2,0,0]]; need = [[7,4,3], [1,2,2]]; print(run_safety_check(available, allocation, need))"
  }}
}}
---
[正式任务]
[知识点名称]
{knowledge_point_name}
---
[相关信息参考]
该知识点在历史解答中被识别出错误的次数: {error_frequency}
---
生成知识卡片JSON：
"""


PROMPT_A_KNOWLEDGE_EXTRACTION = """你是一位顶级的计算机科学教育家和软件架构师。你的任务是从一个[具体问题]中，提炼出可传授的、通用的知识和工具，为构建一个强大的知识库服务。

你的工作流程分为三个阶段：

**阶段一：元问题模板化 (Meta-Question Templating)**
分析[具体问题]，将其抽象为一个简洁的、可检索的“元问题模板”。

**阶段二：通用知识模块构建 (Universal Knowledge Module Construction)**
基于你分析出的“元问题模板”，构建`universal_knowledge_modules`。
*   **【重要】差异化处理**:
    *   **如果问题是计算或推理型 (Reasoning)**: 你的核心任务是生成一个或多个**通用的Python工具函数** (`python_implementation`) 来解决这类问题。`concept_definition` 应作为对该工具的补充说明。
    *   **如果问题是知识或概念型 (Knowledge)**: 你的核心任务是提供一个**详尽、准确的概念定义** (`concept_definition`)。在这种情况下，如果没有可执行的通用算法，`python_implementation` 字段**必须**设置为 `null`。
*   **函数单一职责**: 如果生成代码，每个函数应遵循单一职责原则。

**阶段三：特定逻辑约束识别 (Specific Logic Constraint Identification)**
识别出[具体问题]中那些修改通用行为的**特殊逻辑规则**（而非数值参数），并将它们作为`problem_specific_constraints`列出。

**你的输出必须是严格的JSON格式。**

---
[思维范例]
这是一个你需要严格模仿的思维过程和输出结构。范例将展示如何处理两种不同类型的问题。

**范例1：推理型问题 (Reasoning)**

**[具体问题]**:
"一个计算机系统采用 32 位单字长指令，地址码为 12 位，若定义了 250 条二地址指令，则还可以有多少条单地址指令？"

**[你的理想输出JSON]**:
```json
{{
  "meta_template": {{
    "retrievable_question": "在采用扩展操作码的定长指令系统中，计算给定<上层指令数量列表>后，<目标指令级别>的最大可用指令数。",
    "parameter_schema": [
      {{"name": "total_bits", "type": "int", "description": "总指令字长度"}},
      {{"name": "address_bits", "type": "int", "description": "单个地址码的长度"}},
      {{"name": "previous_formats", "type": "list_of_dict", "description": "已定义的、从高到低排列的各级指令信息..."}}
    ]
  }},
  "universal_knowledge_modules": [
    {{
      "knowledge_point_name": "通用扩展操作码空间计算",
      "concept_definition": {{
        "summary": "在扩展操作码方案中，高地址指令格式会预留一部分操作码作为“转义码”，用于扩展出低地址指令格式的编码空间。这个过程可以逐级递推。",
        "key_characteristics": ["..."]
      }},
      "python_implementation": {{
        "function_signature": "def calculate_extended_opcode_space(total_bits: int, address_bits: int, previous_formats: list) -> int:",
        "code_body": [
            "    # ... (完整的、通用的递推计算代码)"
        ]
      }}
    }}
  ],
  "problem_specific_constraints": []
}}
范例2：知识型问题 (Knowledge)
[具体问题]:
"树的路径长度是从树根到每个结点的路径长度的（）。 正确答案：A. 总和"
[你的理想输出JSON]:
code
JSON
{{
  "meta_template": {{
    "retrievable_question": "定义或解释计算机科学中<树的路径长度>这一概念。",
    "parameter_schema": []
  }},
  "universal_knowledge_modules": [
    {{
      "knowledge_point_name": "树的路径长度 (Path Length of a Tree)",
      "concept_definition": {{
        "summary": "树的路径长度，通常指树的外部路径长度，即从树的根节点到其所有叶子节点的路径长度之总和。在某些上下文中，也可能指内部路径长度，即从根节点到所有非叶子节点的路径长度之总和。",
        "key_characteristics": [
          "衡量树的结构和深度的一个指标。",
          "通常与带权路径长度（WPL）相关，用于构造哈夫曼树等最优二叉树。",
          "路径长度 = 节点深度 * 节点权重（如果带权），然后求和。"
        ]
      }},
      "python_implementation": null
    }}
  ],
  "problem_specific_constraints": []
}}
[正式任务]
现在，请严格遵循上述三个阶段的思维流程，为以下的[具体问题]生成包含meta_template、universal_knowledge_modules和problem_specific_constraints的JSON。
[具体问题]
{question}
生成JSON：
"""

PROMPT_B_PSEUDOCODE_PLANNING = """你是一位极其严谨、深思熟虑的软件架构师。你的任务是为一个[用户问题]，分两步制定一个解题计划。

**第一步：知识点选择 (Knowledge Selection)**
首先，仔细阅读[可用资产]列表，特别是每个知识点的相关性分数。然后，选择出解决[用户问题]**必需**的知识点。你的选择应该写入JSON输出的 `knowledge_selection` 字段。

**第二步：伪代码规划 (Pseudocode Planning)**
然后，**严格地、仅仅**使用你在第一步中选择的知识点，为[用户问题]的每个子问题制定一个纯逻辑的、不包含具体数值的伪代码计划。

**绝对核心指令**:
1.  **先选后用**: 你在“伪代码规划”阶段，**只能**使用你在 `knowledge_selection` 中列出的知识点。
2.  **工具优先**: 如果你选择的知识点中有可用的工具函数，**必须**使用 `CALL function_name(...)` 来表示计算。
3.  **引用来源**: 如果你使用了纯概念知识，**必须**在注释中明确标注知识来源。
4.  **严格JSON输出**: 你的输出必须是包含 `knowledge_selection` 和 `plan` 两个顶级键的JSON对象。
5.  **明确输入输出变量：你的规划输入输出变量应当明确
---
[思维范例：学习如何处理多子问题和混合知识来源]
这是一个你需要严格模仿的思维模式。

**范例问题**: 
(1) 一个100MB的文件，经过压缩率40%的压缩后，实际需要传输的大小是多少？
(2) 如果传输带宽为20Mbps，连接延迟为0.5秒，总耗时是多少？

**范例可用资产 (输入)**:
[
  {{
    "canonical_name": "数据压缩后大小计算",
    "relevance_score": 10,
    "python_implementation": {{ "function_signature": "def calculate_compressed_size(...):" }}
  }},
  {{
    "canonical_name": "网络传输总耗时",
    "relevance_score": 8,
    "python_implementation": null
  }},
  {{
    "canonical_name": "RAID磁盘阵列原理",
    "relevance_score": 1,
    "python_implementation": null
  }}
]

**范例JSON计划输出 (你的目标)**:
```json
{{
 "knowledge_selection": [
    "数据压缩后大小计算",
    "网络传输总耗时"
  ],
  "plan":{{"subquestion_1": [
    {{
      "step": "计算文件压缩后的大小",
      "pseudocode": [
        "// 从问题(1)中提取参数",
        "original_size = GET_PARAMETER('original_file_size')",
        "compression_rate = GET_PARAMETER('compression_ratio')",
        "",
        "// 工具能够解决问题，直接调用工具函数完成子问题(1)的计算",
        "compressed_size = CALL calculate_compressed_size(original_size_mb=original_size, compression_ratio=compression_rate)",
        "PRINT '子问题(1)结果 - 压缩后大小为:', compressed_size"
      ]
    }}
  ],
  "subquestion_2": [
    {{
      "step": "计算总传输耗时",
      "pseudocode": [
        "// 从问题(2)中提取参数",
        "channel_bandwidth = GET_PARAMETER('bandwidth')",
        "connection_latency = GET_PARAMETER('connection_delay')",
        "",
        "// 复用子问题(1)的输出 'compressed_size'",
        "// 无可直接用的工具，根据'网络传输总耗时'知识卡片的概念进行推导",
        "// 来源: 知识卡片 - '网络传输总耗时'",
        "transmission_time = compressed_size * 8 / channel_bandwidth",
        "total_duration = transmission_time + connection_latency",
        "PRINT '子问题(2)结果 - 总耗时为:', total_duration"
      ]
    }}
  ]}}
  
}}
[正式任务]
现在，请严格遵循上述指令和范例的思维模式，为下面的[用户问题]和[可用资产]生成一个纯逻辑的、不包含具体数值的JSON计划。


[通用知识模块]
{knowledge_modules_json}

[题目特定约束]
{problem_constraints_json}

[问题描述]
{question}

生成JSON计划：
"""


PROMPT_C_CODE_EXECUTION = """你是一位严谨、细致的Python程序员。你的**唯一任务**是严格遵循一个[JSON解题计划]，通过编写一段完整的Python代码来解决一个[原始问题]。

**绝对核心指令**:
1.  **完整复制工具**: 在工具符合题目要求的情况下，你的脚本必须应当**完整地**复制[可用工具函数]中所有`python_implementation`提供的函数定义，对于需要基于题目微调的内容，请尽量在输入输出部分调整。
2.  **严格遵循计划**: 在原始逻辑正确的情况下，你的代码主逻辑**必须**与[JSON解题计划]中的伪代码步骤**一一对应**。
3.  **提取并填入数值**: 你需要从[原始问题]中提取所有具体的数值（如“16位”、“12条”、“254条”），并将它们作为变量定义在代码的开头，用于后续的计算。
4.  **清晰的步骤化输出**: 使用`print()`函数清晰地展示每个子问题、每个步骤的求解过程和结果，让代码的输出本身就是一份详细的解题报告。
5.  **纯代码输出**: 你的唯一输出必须是一段完整的、可以直接运行的Python代码，并用 ````python` 和 ```` 将其完全包裹。

---
[思维范例：学习如何将“纯逻辑计划”转化为“具体代码”]
这是一个你需要严格模仿的思维模式。

**[原始问题]**: "一个100MB的文件，需要先经过压缩（压缩率为40%），然后通过一个带宽为20Mbps的信道进行传输，传输前有0.5秒的连接建立延迟。请计算总传输耗时。"

**[可用工具函数]**:
```json
{{
    "universal_knowledge_modules": [
        {{
            "knowledge_point_name": "数据压缩后大小计算",
            "python_implementation": {{
                "function_signature": "def calculate_compressed_size(original_size_mb: float, compression_ratio: float) -> float:",
                "code_body": ["    return original_size_mb * (1 - compression_ratio)"]
            }}
        }},
        {{
            "knowledge_point_name": "网络传输时间计算",
            "python_implementation": {{
                "function_signature": "def calculate_transmission_time(data_size_mb: float, bandwidth_mbps: float) -> float:",
                "code_body": ["    # 1 MB = 8 Mb", "    return data_size_mb * 8 / bandwidth_mbps"]
            }}
        }}
    ]
}}
```

**[JSON解题计划] (纯逻辑)**:
```json
{{
  "main_logic": [
    {{
      "step": "定义所有输入参数的变量",
      "pseudocode": ["original_size = GET_PARAMETER(...)"]
    }},
    {{
      "step": "调用工具计算压缩后的大小",
      "pseudocode": ["compressed_file_size = CALL calculate_compressed_size(original_size_mb=original_size, ...)"]
    }},
    {{
      "step": "调用工具计算网络传输时间",
      "pseudocode": ["data_transmission_time = CALL calculate_transmission_time(data_size_mb=compressed_file_size, ...)"]
    }},
    {{
      "step": "计算并输出最终结果",
      "pseudocode": ["total_duration = data_transmission_time + connection_latency"]
    }}
  ]
}}
```

**[你的目标输出完成python代码]**:
````python
# --- 阶段1: 完整复制所有工具函数 ---
def calculate_compressed_size(original_size_mb: float, compression_ratio: float) -> float:
    return original_size_mb * (1 - compression_ratio)

def calculate_transmission_time(data_size_mb: float, bandwidth_mbps: float) -> float:
    # 1 MB = 8 Mb
    return data_size_mb * 8 / bandwidth_mbps

# --- 阶段2: 严格按照计划编写主逻辑 ---
def solve_problem():
    # 对应计划步骤1: 从[原始问题]提取数值并定义变量
    print("--- [步骤1: 参数定义] ---")
    original_size_mb = 100
    compression_ratio = 0.40
    bandwidth_mbps = 20
    connection_delay_s = 0.5
    print(f"  - 原始大小: {{original_size_mb}} MB")
    print(f"  - 压缩率: {{compression_ratio}}")
    print(f"  - 带宽: {{bandwidth_mbps}} Mbps")
    print(f"  - 连接延迟: {{connection_delay_s}} s\\n")

    # 对应计划步骤2: 调用工具计算压缩后的大小
    print("--- [步骤2: 计算压缩后大小] ---")
    compressed_size = calculate_compressed_size(original_size_mb, compression_ratio)
    print(f"  - 计算公式: original_size * (1 - compression_ratio)")
    print(f"  - 计算过程: {{original_size_mb}} * (1 - {{compression_ratio}}) = {{compressed_size}} MB\\n")

    # 对应计划步骤3: 调用工具计算网络传输时间
    print("--- [步骤3: 计算网络传输时间] ---")
    transmission_time = calculate_transmission_time(compressed_size, bandwidth_mbps)
    print(f"  - 计算公式: compressed_size_mb * 8 / bandwidth_mbps")
    print(f"  - 计算过程: {{compressed_size}} * 8 / {{bandwidth_mbps}} = {{transmission_time:.2f}} s\\n")

    # 对应计划步骤4: 计算并输出最终结果
    print("--- [步骤4: 计算总耗时] ---")
    total_time = transmission_time + connection_delay_s
    print(f"  - 计算公式: transmission_time + connection_delay")
    print(f"  - 计算过程: {{transmission_time:.2f}}s + {{connection_delay_s}}s = {{total_time:.2f}}s")
    print(f"\\n最终答案: 总传输耗时为 \\boxed{{{{total_time:.2f}}}} 秒。")

# 运行主函数
solve_problem()
````
---
[正式任务]
现在，请严格遵循上述指令和范例的思维模式，为解决[原始问题]生成完整的Python代码。

[原始问题]
{question}

[可用工具函数]
{knowledge_modules_json}

[JSON解题计划]
{planner_plan_json}
"""

PROMPT_D_FINAL_SYNTHESIS = """你是一位顶级的计算机科学助教，你的任务是将一份完整的、包含所有技术细节的[解题轨迹]，整合成一份清晰、流畅、逻辑严谨的专业解题报告。

**绝对核心指令**:
1.  **忠实于证据**: 你的报告**必须**严格基于提供的所有信息：[原始问题]、[核心知识点]、[生成的代码]和[代码执行输出]。**严禁**使用任何外部知识或自己进行重新计算。
2.  **理论联系实际**: 你的报告需要将[核心知识点]中的**理论概念**，与[生成的代码]和[代码执行输出]中的**具体计算步骤**联系起来，解释每一步计算的**原理依据**。
3.  **呈现结果**: 清晰地呈现[代码执行输出]中的最终结果。
4.  **专业格式**: 遵循标准的解题报告格式，使用 `\\boxed{{}}` 包裹关键答案，使用 `[end_of_subquestion]` 分隔每个子问题的解答。
---
[思维范例：学习如何整合所有信息]
这是一个你需要严格模仿的思维模式。

**[原始问题]**: "一个100MB的文件...总耗时是多少？"

**[核心知识点]**:
*   `数据压缩后大小计算`: 摘要 - '文件大小乘以(1-压缩率)'
*   `网络传输时间计算`: 摘要 - '数据比特数除以带宽'

**[生成的代码]**:
```python
# ...
compressed_size = calculate_compressed_size(100, 0.4)
transmission_time = calculate_transmission_time(compressed_size, 20)
total_time = transmission_time + 0.5
print(f"最终答案: ... {{total_time}} ...")
```

**[代码执行输出]**:
```
--- [步骤1: ...] ---
  - 压缩后大小: 60.0 MB
--- [步骤2: ...] ---
  - 传输耗时: 24.00 秒
--- [步骤3: ...] ---
  - 总耗时 = 24.00s + 0.5s = 24.50s
最终答案: 总传输耗时为 \\boxed{{24.50}} 秒。
```

**[你的目标输出报告]**:
```
**解题报告**

为了计算总传输耗时，我们分步进行：

**1. 计算压缩后文件大小**
根据核心知识点 **“数据压缩后大小计算”** 的原理，我们将原始文件大小与(1-压缩率)相乘。如代码所示，计算 `100 * (1 - 0.4)`，得到实际需要传输的数据大小为 **60.0 MB**。

**2. 计算网络传输时间**
根据核心知识点 **“网络传输时间计算”** 的原理（时间 = 数据量 / 带宽），我们将压缩后的数据量转换为比特（60.0 MB * 8），再除以带宽（20 Mbps）。如代码所示，计算得出传输耗时为 **24.00 秒**。

**3. 计算总耗时**
最后，我们将网络传输时间与连接延迟相加。根据代码的计算结果 `24.00s + 0.5s`，得到最终的总耗时。

**最终答案**
该文件的总传输耗时为 $\\boxed{{24.50}}$ 秒。
[end_of_subquestion]
```
---
[正式任务]
现在，请严格遵循上述指令和范例的思维模式，为以下的[解题轨迹]生成最终的解题报告。

[解题轨迹]

**1. 原始问题**:
{original_question}

**2. 核心知识点**:
{knowledge_points_summary}

**3. 生成的代码**:
````python
{generated_code}
````

**4. 代码执行输出**:
```
{code_execution_output}
```

请生成最终的解题报告：
"""


# ==============================================================================
#                      PROMPT E: 问题分类 (Classifier)
# ==============================================================================
PROMPT_E_QUESTION_CLASSIFICATION = """你是一位专业的查询分析师。你的任务是根据一个[问题描述]，判断其最合适的解题路径。

请根据以下定义，为给定的问题选择一个类别：
- **"direct_knowledge"**: 该问题主要考察概念定义、事实陈述或简单的逻辑判断。它的答案是陈述性的，可以通过直接解释知识来回答，不需要多步计算。
- **"procedural_reasoning"**: 该问题需要多步计算、数据推导或遵循一个明确的算法流程。解题过程复杂，必须通过代码执行来保证结果的准确性。

**范例**:
- 问题: "树的路径长度是从树根到每个结点的路径长度的（）。" -> 分类: "direct_knowledge"
- 问题: "若二地址指令有12条，一地址指令有254条，则零地址指令的条数最多有多少条？" -> 分类: "procedural_reasoning"

---
[问题描述]
{question}
---
请严格按照以下JSON格式输出，不要添加任何额外的解释。
{{
  "question_type": "..."
}}
"""

# ==============================================================================
#                      PROMPT F: 直接回答 (Direct Answer Synthesizer)
# ==============================================================================
PROMPT_F_DIRECT_ANSWER = """你是一位知识渊博、表达清晰的计算机科学专家。你的任务是根据[原始问题]和我们提供的[相关知识]，直接、准确地回答问题。

**核心要求**:
1.  **基于知识**: 你的回答必须以提供的[相关知识]为核心事实依据。
2.  **清晰简洁**: 直接给出问题的答案和必要的解释，无需展示复杂的推导过程。
3.  **格式规范**: 遵循标准的解题报告格式，使用 `\\boxed{{}}` 包裹关键答案。

---
[原始问题]
{original_question}

---
[相关知识]
{retrieved_knowledge_str}
---

请给出最终答案：
"""

PROMPT_G_DIRECT_ANSWER_ZERO_KNOWLEDGE = """你是一位知识渊博、能力强大的AI助手。请直接、准确地回答以下[问题描述]。

请尽你所能，提供详细的推理过程和最终答案。对于关键的最终数值或结论，请使用 `\\boxed{{}}` 包裹。如果问题包含多个子问题，请使用 `[end_of_subquestion]` 分隔解答。

---
[问题描述]
{question}
---

请开始回答：
"""


PROMPT_RERANK_KNOWLEDGE = """你是一位极其严谨、逻辑清晰的计算机科学知识库管理员。你的任务是为一个[用户问题]，对一份[候选知识列表]进行一次**两阶段的精炼**。

**第一阶段：剔除无关项 (Pruning)**
首先，通读所有候选知识点，**识别并彻底剔除**那些与[用户问题]**完全不相关**的条目。

**第二阶段：相关性打分 (Scoring)**
然后，在**只剩下相关知识点**的集合中，为**每一个**知识点，给出一个0-10分的相关性分数，以体现其重要性。
*   **10分 (绝对核心)**: 没有这个知识点，问题**绝对无法解决**。它是一个必需的计算工具或核心原理。
*   **7-9分 (高度相关)**: 知识点是解决问题所必需的、紧密相关的背景原理或辅助步骤。
*   **4-6分 (一般相关)**: 提供了有用的背景概念，有助于理解问题，但不是解决问题的直接工具。

**核心指令**:
1.  **严格JSON输出**: 你的输出必须是一个JSON对象，其中包含一个名为 `refined_knowledge` 的列表。
2.  **只包含相关项**: 这个列表中**只应包含**经过你第一阶段筛选后**保留下来**的相关知识点。
3.  **包含分数**: 列表中的每一项都必须包含 `canonical_name` 和 `relevance_score` 两个键。

---
[范例]
这是一个你需要严格模仿的“先剔除，后打分”的思维过程。

**[用户问题]**:
"设计某指令系统时，采用16位定长指令字...若二地址指令有12条，且至少有一条零地址指令..."

**[候选知识列表] (输入)**:
```json
[
  {{
    "canonical_name": "通用扩展操作码空间计算",
    "summary": "一个通用的、可递推的函数..."
  }},
  {{
    "canonical_name": "指令格式基础",
    "summary": "计算机指令由操作码和地址码组成..."
  }},
  {{
    "canonical_name": "CRC校验码计算方法",
    "summary": "CRC校验码是通过多项式除法计算得到的..."
  }}
]
[你的目标JSON输出]:
code
JSON
{{
  "refined_knowledge": [
    {{
      "canonical_name": "通用扩展操作码空间计算",
      "relevance_score": 10
    }},
    {{
      "canonical_name": "指令格式基础",
      "relevance_score": 6
    }}
  ]
}}
(思维过程解释: 1. 剔除: CRC校验码计算方法与指令系统完全无关，首先被剔除。 2. 打分: 在剩下的两项中，通用扩展...是核心计算工具，得10分。指令格式基础是重要的背景知识，得6分。)
[正式任务]：
问题：
{question}
[候选知识列表]：
{candidate_knowledge_list_str}
"""

PROMPT_H_CODE_CORRECTION = """你是一位经验丰富的Python调试专家。你之前编写的一段用于解决[原始问题]的代码在执行时遇到了错误。

你的任务是仔细分析[错误的代码]和[执行错误信息 (Traceback)]，并结合原始的[JSON解题计划]和[可用工具函数]，生成一段**修正后的、完整的、可执行的**Python代码。

**核心指令**:
1.  **定位错误**: 仔细阅读[执行错误信息]，理解错误的原因（例如：`KeyError`, `TypeError`, `NameError`等）。
2.  **参考规划**: 回顾[JSON解题计划]，确保你的修正逻辑与最初的规划意图保持一致。
3.  **检查工具使用**: 确认你对[可用工具函数]的调用是否正确，特别是**参数的键名和数据类型**。
4.  **完整输出**: 你的输出**必须**是修正后的**完整Python脚本**，而不仅仅是修改的部分。
5.  **纯代码输出**: 将所有代码用 ````python` 和 ```` 完全包裹。

---
[原始问题]
{question}
---
[可用工具函数]
{knowledge_modules_json}
---
[JSON解题计划]
{planner_plan_json}
---
[错误的代码]
````python
{erroneous_code}
"""

PROMPT_IDENTIFY_KNOWLEDGE_POINTS = """你是一位精通计算机科学的解题分析专家。你的任务是分析一个[用户问题]，并将其分解为解决该问题所需的核心**知识点**。

**核心指令**:
1.  **聚焦核心工具**: 专注于识别那些可以直接对应到**计算公式或可执行算法**的核心知识点名称。纯粹的背景概念或逻辑步骤描述，除非它们是独立的知识模块，否则不应列出。
2.  **识别性质**: 为每个知识点判断其**性质 (property)**：
    *   `"Computation_Tool"`: 如果这个知识点是一个可以用来计算具体数值的公式或算法。
    *   `"Concept_Definition"`: 如果这个知识点是一个需要被定义或解释的核心概念。
3.  **严格JSON输出**: 你的输出必须是一个JSON对象，其中包含一个名为 `required_knowledge` 的列表。

---
[范例]
这是一个你需要严格模仿的思维过程和输出格式。

**[用户问题]**:
"设计某指令系统时，采用16位定长指令字，地址码为6位。若二地址指令有12条，且至少有一条零地址指令，则一地址指令最多有多少条？"

**[你的目标JSON输出 (黄金标准)]**:
```json
{{
  "required_knowledge": [
    {{
      "knowledge_name": "通用扩展操作码空间计算",
      "property": "Computation_Tool"
    }}
  ]
}}
[正式任务]
请生成你分析出的所需知识点JSON：
"""