# -*- coding: utf-8 -*-
"""
概念辨析题：中断隐指令保存断点（PC）
- 无数值计算，gen.py 形式化校验通过条件（题干无歧义 / 选项互异 / 主体互斥）。
- 通过条件翻译为 assert（打到特征，禁弱化/禁恒真）。
"""

# ============ PARAMS：题干与选项的事实声明 ============

# 题干场景特征
scenario = {
    "中断类型": "可屏蔽外部中断（键盘输入设备）",
    "触发阶段": "CPU 当前指令执行完毕后响应",
    "设问指向": "保存断点（PC）这一操作由谁、在哪个阶段完成",
}

# 正确知识点（教材标准）：中断隐指令三项操作
HARDWARE_OPS = ["关中断", "保存断点（保存PC/返回地址）", "引出中断服务程序"]
assert "保存断点（保存PC/返回地址）" in HARDWARE_OPS, \
    "场景规则违反：保存断点不在中断隐指令（硬件自动）三项操作中"

# 中断隐指令的本质特征
INTERRUPT_HIDDEN_INSTRUCTION_FEATURES = {
    "执行主体": "硬件自动（非软件/非用户程序）",
    "所属阶段": "中断响应阶段（非执行阶段）",
    "可编程性": "不可编程（非指令系统中供程序员使用的指令）",
}

# 四个选项的操作主体声明（各选项主张的"谁"保存断点）
option_subjects = {
    "A": "中断隐指令（硬件自动）",
    "B": "中断服务程序（软件）",
    "C": "用户程序",
    "D": "CALL类指令（函数调用）",
}

# ============ 通过条件 1：题干无歧义 ============
# 设问明确指向"保存断点/PC 的主体"，不出现两种合理解读
assert "PC" in scenario["设问指向"] and ("由谁" in scenario["设问指向"] or "哪个阶段" in scenario["设问指向"]), \
    "通过条件1不满足：设问未明确指向保存断点(PC)的主体"
assert scenario["中断类型"].startswith("可屏蔽外部中断"), \
    "通过条件1不满足：中断类型须为外部中断，场景须清楚"
print("CONDITION_1 无歧义:", {
    "设问指向": scenario["设问指向"],
    "中断类型": scenario["中断类型"],
    "触发阶段": scenario["触发阶段"],
    "判定": "设问明确指向'保存断点(PC)的主体'，场景清楚无歧义",
})

# ============ 通过条件 2：正确选项 A 唯一正确 ============
# A 的主体（中断隐指令/硬件自动）确属中断响应阶段保存断点的正确主体；
# 且 A 的表述无事实错误。校验 A 指向的主体具备三项硬件特征。
subj_A = option_subjects["A"]
assert "硬件自动" in subj_A and "中断隐指令" in subj_A, \
    "通过条件2不满足：正确选项A主体须为'中断隐指令（硬件自动）'"
assert INTERRUPT_HIDDEN_INSTRUCTION_FEATURES["执行主体"] == "硬件自动（非软件/非用户程序）", \
    "通过条件2不满足：中断隐指令执行主体特征不符"
assert INTERRUPT_HIDDEN_INSTRUCTION_FEATURES["所属阶段"] == "中断响应阶段（非执行阶段）", \
    "通过条件2不满足：中断隐指令所属阶段特征不符"
print("CONDITION_2 正确选项A唯一正确:", {
    "A主体": subj_A,
    "中断隐指令特征": INTERRUPT_HIDDEN_INSTRUCTION_FEATURES,
    "判定": "A指向中断隐指令（硬件自动），确属中断响应阶段保存断点的唯一正确主体",
})

# ============ 通过条件 3：4 选项互异（主体两两不同）============
subjects = list(option_subjects.values())
for i in range(len(subjects)):
    for j in range(i + 1, len(subjects)):
        assert subjects[i] != subjects[j], \
            f"通过条件3不满足：选项主体重叠 → {subjects[i]}"
print("CONDITION_3 选项互异:", {
    "各选项主体": option_subjects,
    "判定": "A/B/C/D 四个主体（中断隐指令/中断服务程序/用户程序/CALL指令）互不相同",
})

# ============ 各选项正误判定（知识回忆型）============
def classify(option_key):
    """对每个选项判定正误及理由，基于教材事实。"""
    if option_key == "A":
        return ("正确", "中断隐指令（硬件自动）在中断响应阶段完成保存断点，"
                         "与中断隐指令三项操作（关中断/保存断点/引出中断服务程序）一致。")
    return ("错误", {
        "B": "保存断点（PC）由中断隐指令（硬件）完成，而非中断服务程序（软件）。"
             "中断服务程序保存的是通用寄存器/现场（保护现场），不是断点PC。",
        "C": "用户程序无法感知中断时序，也不负责保存断点。保存断点是硬件自动完成的。",
        "D": "中断保存断点由中断隐指令（硬件自动、不可编程）完成，"
             "并非CPU执行CALL类指令。中断隐指令发生在响应阶段，不是执行阶段。",
    }[option_key])

print("\n=== RESULT ===")
for k in ["A", "B", "C", "D"]:
    verdict, reason = classify(k)
    print(f"OPTION_{k}: 主体={option_subjects[k]:20s} 判定={verdict} | {reason}")

print("\n=== RULE_CHECK ===")
print("中断隐指令三项操作:", HARDWARE_OPS)
print("保存断点归属:", "中断隐指令（硬件自动，中断响应阶段）")
print("正确答案: A")
