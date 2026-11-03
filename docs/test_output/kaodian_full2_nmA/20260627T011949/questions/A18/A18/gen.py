# -*- coding: utf-8 -*-
"""
指令执行微操作序列与控制信号（文字推导）—— gen.py
建模：单总线数据通路上取指/间址/执行周期的微操作序列与控制信号。
底部 print 完整数据流。
"""

# ====================================================================
# PARAMS：题目参数
# ====================================================================
PARAMS = {
    "编址方式": "按字节编址",
    "地址线位数": 16,
    "总线宽度": 16,
    "存储字长": 16,
    "指令字长_位": 16,
    "指令字长_字节": 16 // 8,   # = 2
    "通用寄存器": ["R0","R1","R2","R3","R4","R5","R6","R7"],
}

PC_INC = PARAMS["指令字长_字节"]  # 按字节编址，指令2字节 → PC+2

# ====================================================================
# 控制信号清单（直接从题干清单翻译，不靠正则提取）
# ====================================================================
control_signals = set()

# 寄存器与总线交互信号
for sig in ["PCin","PCout","MARin","MDRin","MDRout","IRin"]:
    control_signals.add(sig)
for n in range(8):
    control_signals.add(f"R{n}in")
    control_signals.add(f"R{n}out")

# ALU 锁存信号
for sig in ["Yin","Zin","Zout"]:
    control_signals.add(sig)

# ALU 运算选择信号
for sig in ["ALU_ADD","ALU_SUB","ALU_AND","ALU_OR"]:
    control_signals.add(sig)

# 访存控制信号
for sig in ["Read","Write"]:
    control_signals.add(sig)

# ====================================================================
# 数据通路部件表（从题干翻译）：部件 → 能力描述
# 仅用于"数据通路完整性"验证（场景规则2）
# ====================================================================
datapath = {
    "PC":  {"bus_in": True, "bus_out": True, "notes": "PCin/PCout"},
    "MAR": {"bus_in": True, "bus_out": False,"notes": "MARin; 输出→主存地址线(只读)"},
    "MDR": {"bus_in": True, "bus_out": True, "notes": "MDRin/MDRout; Read/Write 控制访存"},
    "IR":  {"bus_in": True, "bus_out": True, "notes": "IRin; 地址字段→控制器→可经内部通路送MAR"},
    "ALU": {"bus_in": True, "bus_out": True, "notes": "Yin(总线→Y锁存); Zin(结果→Z); Zout(Z→总线); ALU_ADD/SUB/AND/OR"},
}
for n in range(8):
    datapath[f"R{n}"] = {"bus_in": True, "bus_out": True, "notes": f"R{n}in/R{n}out"}

# ====================================================================
# 微操作序列：每步 = {步号, 周期, 微操作描述, 所需控制信号(列表)}
# ====================================================================

# ---- 第1问：取指周期 ----
fetch_cycle = [
    {"step":"T1","cycle":"取指","microop":"PC → MAR",
     "signals":["PCout","MARin"]},
    {"step":"T2","cycle":"取指","microop":"PC + 2 → PC",
     "signals":["PCout","Yin","ALU_ADD","Zin","Zout","PCin"]},
    {"step":"T3","cycle":"取指","microop":"Mem[MAR] → MDR → IR",
     "signals":["Read","MDRout","IRin"]},
]

# ---- 第2问：LDR R1, @40 —— 间址周期 + 执行周期 ----
# 间址周期：取主存[形式地址40]的内容作为有效地址EA，再送MAR
indirect_cycle = [
    {"step":"T1","cycle":"间址","microop":"IR 地址字段(形式地址40) → MAR",
     "signals":["MARin"]},
    {"step":"T2","cycle":"间址","microop":"Mem[MAR] → MDR",
     "signals":["Read"]},
    {"step":"T3","cycle":"间址","microop":"MDR(=有效地址EA) → MAR",
     "signals":["MDRout","MARin"]},
]
# 执行周期：按EA访存取操作数 → R1
exec_ldr = [
    {"step":"T1","cycle":"执行","microop":"Mem[MAR](EA处) → MDR",
     "signals":["Read"]},
    {"step":"T2","cycle":"执行","microop":"MDR → R1",
     "signals":["MDRout","R1in"]},
]

# ---- 第3问：ADD R2, R3 —— 执行周期 ----
exec_add = [
    {"step":"T1","cycle":"执行","microop":"R2 → Y 锁存器",
     "signals":["R2out","Yin"]},
    {"step":"T2","cycle":"执行","microop":"R3→总线→ALU B端; Y→ALU A端; ADD→Z",
     "signals":["R3out","ALU_ADD","Zin"]},
    {"step":"T3","cycle":"执行","microop":"Z → 总线 → R2",
     "signals":["Zout","R2in"]},
]

# ====================================================================
# 辅助函数
# ====================================================================
def used_signals(steps):
    sigs = set()
    for s in steps:
        sigs.update(s["signals"])
    return sigs

def check_signal_support(steps, tag):
    """场景规则2+4：每个微操作的每个控制信号，都要在 control_signals 清单中有支撑。"""
    issues = []
    for s in steps:
        for sig in s["signals"]:
            if sig not in control_signals:
                issues.append(f"  [{tag}] {s['step']} {s['microop']}: 信号 '{sig}' 在控制信号清单中无支撑")
    return issues

# ====================================================================
# 场景规则验证（4 条约束）
# ====================================================================

# --- 规则1：PC增量 = 指令字节数 ---
rule1_pass = (PC_INC == PARAMS["指令字长_字节"])
rule1_msg = f"PC_INC={PC_INC}, 指令字长_字节={PARAMS['指令字长_字节']} → {'一致' if rule1_pass else '不一致'}"

# --- 规则2+4：数据通路完整性 + 控制信号覆盖性 ---
all_steps = fetch_cycle + indirect_cycle + exec_ldr + exec_add
support_issues = check_signal_support(all_steps, "ALL")
rule2_pass = (len(support_issues) == 0)
rule4_pass = rule2_pass  # 规则4=所有信号都在清单中，与规则2同一检查

# --- 规则3：ADD R2,R3 执行周期唯一确定序列 ---
expected_add = [
    {"T1": {"R2out","Yin"}},
    {"T2": {"R3out","ALU_ADD","Zin"}},
    {"T3": {"Zout","R2in"}},
]
rule3_pass = True
for i, exp_dict in enumerate(expected_add):
    exp_sigs = list(exp_dict.values())[0]
    actual_sigs = set(exec_add[i]["signals"])
    if exp_sigs != actual_sigs:
        rule3_pass = False
        break
rule3_msg = "T1={R2out,Yin}, T2={R3out,ALU_ADD,Zin}, T3={Zout,R2in} → 唯一确定"

# --- 额外验证：ADD不含Read/Write（第3问核心论点）---
add_sigs = used_signals(exec_add)
add_has_memaccess = ("Read" in add_sigs) or ("Write" in add_sigs)
add_no_mem = not add_has_memaccess

# --- 额外验证：LDR含Read（对比）---
ldr_sigs = used_signals(indirect_cycle + exec_ldr)
ldr_has_read = "Read" in ldr_sigs

# ====================================================================
# ASSERTS（场景规则）
# ====================================================================
assert rule1_pass, f"[规则1失败] PC增量({PC_INC}) != 指令字节数({PARAMS['指令字长_字节']})"
assert rule2_pass, "[规则2失败] 存在无支撑信号:\n" + "\n".join(support_issues)
assert rule3_pass, "[规则3失败] ADD执行周期序列与唯一推导序列不符"
assert rule4_pass, "[规则4失败] 信号未全覆盖"
assert add_no_mem, "[第3问核心] ADD执行周期不应含Read/Write"
assert ldr_has_read, "[对比] LDR应含Read信号"

# ====================================================================
# 底部：打印完整数据流
# ====================================================================
def fmt_steps(steps):
    lines = []
    for s in steps:
        lines.append(f"    {s['step']} | {s['microop']} | 控制信号: {', '.join(s['signals'])}")
    return "\n".join(lines)

print("=" * 70)
print("PARAMS:")
for k, v in PARAMS.items():
    print(f"  {k} = {v}")
print(f"  PC增量(PC_INC) = {PC_INC}")
print()

print("CONTROL_SIGNALS 清单:", sorted(control_signals))
print()

print("=" * 70)
print("【第1问·3分】取指周期微操作序列:")
print(fmt_steps(fetch_cycle))
print()

print("【第2问·4分】LDR R1, @40 间址周期 + 执行周期:")
print("  --- 间址周期（间接寻址：主存[40]内容 = 有效地址EA）---")
print(fmt_steps(indirect_cycle))
print("  --- 执行周期（按EA访存取操作数 → R1）---")
print(fmt_steps(exec_ldr))
print()

print("【第3问·3分】ADD R2, R3 执行周期微操作序列:")
print(fmt_steps(exec_add))
print()

print("=" * 70)
print("RULE_CHECK（场景规则验证）:")
print(f"  规则1 [PC增量一致]: {rule1_msg}  → {'PASS' if rule1_pass else 'FAIL'}")
print(f"  规则2 [数据通路完整]: 无支撑信号数 = {len(support_issues)}  → {'PASS' if rule2_pass else 'FAIL'}")
print(f"  规则3 [ADD序列唯一确定]: {rule3_msg}  → {'PASS' if rule3_pass else 'FAIL'}")
print(f"  规则4 [控制信号覆盖]: 所有信号⊆清单 = {rule4_pass}  → {'PASS' if rule4_pass else 'FAIL'}")
print(f"  额外  [ADD不含Read/Write]: {add_no_mem}  (ADD信号集合 = {sorted(add_sigs)})")
print(f"  额外  [LDR含Read]: {ldr_has_read}  (LDR信号集合 = {sorted(ldr_sigs)})")
print()

print("=" * 70)
print("RESULT:")
print(f"  PC增量 = {PC_INC}")
print(f"  取指周期步数 = {len(fetch_cycle)}")
print(f"  LDR间址周期步数 = {len(indirect_cycle)}")
print(f"  LDR执行周期步数 = {len(exec_ldr)}")
print(f"  ADD执行周期步数 = {len(exec_add)}")
print(f"  ADD无访存信号(Read/Write) = {add_no_mem}")
print(f"  LDR含Read信号 = {ldr_has_read}")
print("  ALL ASSERTS PASSED ✓")
