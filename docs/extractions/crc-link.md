# Extraction: crc-link

## Question Structure (P1)

```json
{
  "question_type": "综合题",
  "subject": "计算机网络",
  "year": "未知",
  "stem": "小亮在开发物联网设备时，想要为设备的网络通讯定制专用的数据链路层。其中，为确保数据传输的正确性，拟使用循环冗余校验码（CRC）进行差错检测。设待发送的数据比特串为101001，生成多项式G(x)=x³+1。请计算CRC校验码。",
  "correct_answer": "001",
  "options": {
    "A": "000",
    "B": "010",
    "C": "001",
    "D": "101"
  },
  "structure": {
    "given_conditions": [
      "待发送数据比特串：101001",
      "生成多项式：G(x)=x³+1"
    ],
    "asked_target": "asked_target: 计算该数据对应的CRC校验码（模2除法余数）",
    "hidden_constraints": [
      "生成多项式最高次幂为3，需在数据末尾补3个0进行除法运算",
      "多项式x³+1对应二进制除数为1001（缺x²、x¹项对应位为0）",
      "除法运算规则为模2除法（按位异或，无进位、无借位）"
    ],
    "unit_constraints": [
      "无物理单位约束，校验码长度固定为生成多项式阶数（3位二进制）"
    ],
    "key_terms": [
      "循环冗余校验码（CRC）",
      "生成多项式",
      "模2除法",
      "数据链路层"
    ]
  },
  "distractor_analysis": [
    {
      "option": "A",
      "content": "",
      "error_type": "计算失误",
      "targeted_misconception": "模2运算过程中未严格对齐被除数首位，或遗漏中间步骤异或，导致误判为整除余0"
    },
    {
      "option": "B",
      "content": "",
      "error_type": "规则混淆",
      "targeted_misconception": "混淆了CRC补零位数与生成多项式系数映射，或误用普通二进制除法计算"
    },
    {
      "option": "D",
      "content": "",
      "error_type": "概念混淆",
      "targeted_misconception": "将生成多项式G(x)误对应为二进制1010，导致除数错误进而余数偏差"
    }
  ],
  "correct_answer_diagnosis": {
    "answer_status": "计算正确",
    "diagnostic_note": "推理正确。待发送数据101001后补3个0得101001000，按模2除法以1001为除数进行逐位异或运算，最终余数为001，过程与结果均符合CRC校验码计算规范。"
  }
}
```

## Knowledge Units (P2)

### 循环冗余校验（CRC）差错检测原理

- Description: 数据链路层利用CRC码对传输数据进行差错检测，通过模2除法计算余数作为校验码附加在数据末尾，接收方通过相同除法验证余数是否为0以判断传输正确性。

- Subtype: definition

- Subject: 计算机网络


### 生成多项式与二进制除数转换规则

- Description: 将生成多项式G(x)转换为二进制除数时，按x的幂次从高到低排列，系数为1的位填1，系数为0或缺项的位填0。

- Subtype: rule

- Subject: 计算机网络


### 模2除法运算规则

- Description: 模2除法使用按位异或（XOR）替代传统减法，运算过程中不产生进位和借位，当被除数当前位与除数最高位对齐且为1时进行异或，否则商0并左移一位。

- Subtype: rule

- Subject: 计算机网络


### CRC校验码位数与补零规则

- Description: CRC校验码的位数等于生成多项式的最高次幂（阶数），计算前需在原始数据比特串末尾补相同个数的0构成被除数。

- Subtype: rule

- Subject: 计算机网络


### Mechanism: 模2除法无进位无借位机制

- Description: 模2除法在逐位相除时，减法操作等价于按位异或（XOR），不处理进位和借位。

- Affects: 决定除法过程中的商和余数计算结果，直接影响最终CRC校验码的数值。


### Mechanism: 多项式阶数决定补零位数与校验码长度机制

- Description: 生成多项式的最高次幂（阶数）直接决定待发送数据末尾需补0的个数，同时也决定了最终CRC校验码的固定位数。

- Affects: 决定被除数的构造方式以及最终余数（校验码）的截取长度。


### Mechanism: 稀疏多项式缺项补零机制

- Description: 将多项式转换为二进制除数时，缺失的幂次项对应位必须补0，按幂次从高到低严格对齐。

- Affects: 决定除数的二进制表示形式，进而影响模2除法的每一步运算。


## Trigger Rules (P3)

```json
{
  "trigger_rules": [],
  "negative_triggers": []
}
```

## Reasoning Pattern (P4)

```json
{
  "pattern_name": "CRC校验码计算模式",
  "subject": "计算机网络",
  "applicable_conditions": [
    "题目明确给出待发送数据比特串与生成多项式G(x)",
    "要求计算数据链路层的CRC校验码（或FCS）",
    "解题核心依赖模2除法（异或运算）求余数"
  ],
  "steps": [
    {
      "order": 1,
      "name": "确定多项式阶数与校验码长度",
      "description": "识别生成多项式G(x)的最高次幂r，该值直接决定CRC校验码的固定位数和待补零的个数",
      "input": "生成多项式G(x)",
      "output": "阶数r（正整数）",
      "required_knowledge": [
        "CRC校验码位数与补零规则"
      ],
      "common_error_at_this_step": "误将多项式非零项的个数当作阶数，或未正确识别最高次幂"
    },
    {
      "order": 2,
      "name": "构造模2除法被除数",
      "description": "在原始数据比特串末尾严格拼接r个0，形成除法运算的初始被除数",
      "input": "待发送数据比特串; 阶数r",
      "output": "补零后的被除数二进制串",
      "required_knowledge": [
        "CRC校验码位数与补零规则"
      ],
      "common_error_at_this_step": "补0方向错误（误补在首部）或补0个数与阶数r不匹配"
    },
    {
      "order": 3,
      "name": "多项式转二进制除数",
      "description": "按x的幂次从高到低排列G(x)的系数，系数为1的位填1，缺项或系数为0的位严格补0占位",
      "input": "生成多项式G(x)",
      "output": "二进制除数",
      "required_knowledge": [
        "生成多项式与二进制除数转换规则; 稀疏多项式缺项补零机制"
      ],
      "common_error_at_this_step": "忽略代数书写中的缺项（如x³+1错转为11或101），导致除数位数或位权错位"
    },
    {
      "order": 4,
      "name": "执行模2除法求余",
      "description": "将被除数与除数最高位对齐，按位进行异或（XOR）运算，全程无进位、无借位，逐位处理直至当前余数位数小于除数位数",
      "input": "被除数二进制串; 二进制除数",
      "output": "模2除法余数",
      "required_knowledge": [
        "模2除法运算规则; 模2除法无进位无借位机制"
      ],
      "common_error_at_this_step": "受常规算术除法思维影响引入借位，或异或规则混淆（如误将1⊕1算作0但借位，或当前位为0时错误左移）"
    },
    {
      "order": 5,
      "name": "格式化输出校验码",
      "description": "提取除法余数，若其有效位数不足r位，则在左侧高位补0至r位，得到符合协议规范的校验码",
      "input": "模2除法余数; 阶数r",
      "output": "r位CRC校验码",
      "required_knowledge": [
        "CRC校验码位数与补零规则"
      ],
      "common_error_at_this_step": "直接输出计算余数未补齐前导0，导致校验码长度与生成多项式阶数不符"
    }
  ],
  "common_breakpoints": [
    {
      "step": 3,
      "reason": "生成多项式在数学表达中常省略系数为0的项，考生易受代数书写习惯影响，忽略二进制映射时必须严格按幂次占位的底层规则",
      "error_manifestation": "除数位数变短或中间关键位错填1，导致后续模2除法每一步的对齐基准和异或结果均发生连锁错误"
    },
    {
      "step": 4,
      "reason": "模2除法本质是线性反馈移位寄存器的异或过程，与人类熟悉的带借位减法/除法认知模型存在根本冲突，思维惯性难以切换",
      "error_manifestation": "在中间步骤进行借位运算，或当被除数当前位为0时错误跳过/继续左移，最终余数计算完全偏离正确路径"
    }
  ],
  "can_verify_with_code": true,
  "verification_approach": "使用Python整数位运算模拟：将数据串转为整数后左移r位（等价补0）得到`dividend`，将多项式转为二进制整数得到`divisor`。计算除数位数`div_len`，从`shift = len(bin(dividend))-2 - div_len + 1`开始循环，若`(dividend >> shift) & 1`为1，则执行`dividend ^= divisor << shift`，随后`shift -= 1`。循环结束后，`dividend`即为余数，使用`format(dividend, '0{}b'.format(r))`即可输出标准r位CRC校验码。"
}
```
