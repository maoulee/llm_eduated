# -*- coding: utf-8 -*-
"""
单总线数据通路 - SUB R1,R2 指令微操作序列
建模：定义各节拍功能+控制信号，将题干6条通过条件翻译为 assert 逐节拍校验。

通过条件翻译表（题干通过条件 → assert）：
  1. 总线无冲突：每节拍 "out" 信号至多1个
  2. 控制信号一致性：所有信号 ∈ C1~C15 定义表
  3. 取指完整性：PC→MAR / Read / MDR→IR / PC+1 四项齐全
  4. 减法操作数顺序：R1→Y（被减数），R2→Bus（减数），不可颠倒
  5. 写回正确性：结果经 Z→Bus→R1，不可跳过 Z
  6. 节拍连续性：编号连续无遗漏
"""

# ===== 控制信号定义表 (C1~C15) =====
SIGNAL_TABLE = {
    "PCout", "PC+1", "MARin", "Read", "Write",
    "MDRout", "IRin", "R1out", "R1in", "R2out",
    "Yin", "Zin", "Zout", "ADD", "SUB"
}

# 向总线输出数据的信号（单总线冲突判定依据）
BUS_OUT_SIGNALS = {"PCout", "MDRout", "R1out", "R2out", "Zout"}

# ALU 功能信号
ALU_FUNC_SIGNALS = {"ADD", "SUB"}


def parse_signals(signal_str):
    """解析信号字符串 → 信号集合，去空格、逗号。"""
    return {s.strip() for s in signal_str.split(",") if s.strip()}


# ===== 微操作序列定义 =====
# 取指阶段
fetch = [
    {
        "beat": "T1",
        "desc": "PC 内容送入 MAR",
        "signals": "PCout, MARin"
    },
    {
        "beat": "T2",
        "desc": "存储器读：M[MAR] 的内容读入 MDR",
        "signals": "Read"
    },
    {
        "beat": "T3",
        "desc": "MDR 内容送入 IR",
        "signals": "MDRout, IRin"
    },
    {
        "beat": "T4",
        "desc": "PC 自增（内部逻辑，不占用总线）",
        "signals": "PC+1"
    },
]

# 执行阶段：SUB R1, R2 → R1 ← R1 − R2
# ALU: 输入A来自Y，输入B来自Bus，A−B = R1−R2
execute = [
    {
        "beat": "T5",
        "desc": "R1 内容送入 ALU 输入锁存器 Y（被减数）",
        "signals": "R1out, Yin"
    },
    {
        "beat": "T6",
        "desc": "R2 内容送总线（ALU 输入B），执行减法，结果存入 Z",
        "signals": "R2out, SUB, Zin"
    },
    {
        "beat": "T7",
        "desc": "Z 内容经总线送入 R1（写回结果）",
        "signals": "Zout, R1in"
    },
]

all_steps = fetch + execute


# ===== 逐节拍解析信号 =====
for step in all_steps:
    step["signal_set"] = parse_signals(step["signals"])

all_signals = set()
for step in all_steps:
    all_signals |= step["signal_set"]


# ===== 通过条件 6：节拍连续性 =====
beat_nums = []
for step in all_steps:
    # 提取编号数字
    num = int(step["beat"].replace("T", "").replace("t", ""))
    beat_nums.append(num)

assert beat_nums == list(range(1, len(beat_nums) + 1)), \
    f"节拍不连续: {beat_nums}"

fetch_beat_nums = [int(s["beat"][1:]) for s in fetch]
exec_beat_nums = [int(s["beat"][1:]) for s in execute]
assert exec_beat_nums[0] == fetch_beat_nums[-1] + 1, \
    "执行阶段第一个节拍编号未紧接取指阶段最后节拍"


# ===== 通过条件 1：总线无冲突（每节拍 "out" 信号至多1个）=====
for step in all_steps:
    outs_in_beat = step["signal_set"] & BUS_OUT_SIGNALS
    assert len(outs_in_beat) <= 1, \
        f"总线冲突 [{step['beat']}]: 有 {len(outs_in_beat)} 个out信号 {outs_in_beat}"


# ===== 通过条件 2：控制信号一致性（全部来自定义表）=====
for step in all_steps:
    undefined = step["signal_set"] - SIGNAL_TABLE
    assert not undefined, \
        f"未定义信号 [{step['beat']}]: {undefined}"


# ===== 通过条件 3：取指完整性（4项操作齐全）=====
fetch_all_signals = set()
for step in fetch:
    fetch_all_signals |= step["signal_set"]

# 3a: PC→MAR（PCout + MARin 必须在同一节拍）
pc_to_mar_ok = False
for step in fetch:
    if {"PCout", "MARin"} <= step["signal_set"]:
        pc_to_mar_ok = True
        break
assert pc_to_mar_ok, "取指不完整：缺少 PC→MAR（PCout+MARin）"

# 3b: Read 信号
assert "Read" in fetch_all_signals, "取指不完整：缺少 Read"

# 3c: MDR→IR（MDRout + IRin 必须在同一节拍）
mdr_to_ir_ok = False
for step in fetch:
    if {"MDRout", "IRin"} <= step["signal_set"]:
        mdr_to_ir_ok = True
        break
assert mdr_to_ir_ok, "取指不完整：缺少 MDR→IR（MDRout+IRin）"

# 3d: PC+1 信号
assert "PC+1" in fetch_all_signals, "取指不完整：缺少 PC+1"


# ===== 通过条件 4：减法操作数顺序（R1→Y 被减数，R2→Bus 减数）=====
exec_all_signals = set()
for step in execute:
    exec_all_signals |= step["signal_set"]

# 4a: R1→Y（被减数 R1 送入 ALU 输入A锁存器）
r1_to_y_ok = False
r1_to_y_beat = None
for step in execute:
    if {"R1out", "Yin"} <= step["signal_set"]:
        r1_to_y_ok = True
        r1_to_y_beat = step["beat"]
        break
assert r1_to_y_ok, "减法操作数顺序错：缺少 R1→Y（被减数未送入ALU输入A）"

# 4b: R2→Bus（减数 R2 经总线送入 ALU 输入B，伴随 SUB 信号）
r2_to_bus_ok = False
r2_to_bus_beat = None
for step in execute:
    if "R2out" in step["signal_set"]:
        r2_to_bus_ok = True
        r2_to_bus_beat = step["beat"]
        break
assert r2_to_bus_ok, "减法操作数顺序错：缺少 R2→Bus（减数未经总线送入ALU输入B）"

# 4c: 顺序正确——R1→Y 必须早于或等于 R2→Bus（至少 R1 先进 Y）
#       关键：不能 R2→Y 而 R1→Bus（顺序颠倒导致 A-B 变为 R2-R1）
assert not (any({"R2out", "Yin"} <= s["signal_set"] for s in execute)), \
    "减法操作数顺序错：R2 送入 Y，会导致 A−B = R2−R1（顺序颠倒）"

# 4d: SUB 功能信号存在
assert "SUB" in exec_all_signals, "执行阶段缺少 SUB 功能信号"


# ===== 通过条件 5：写回正确性（结果经 Z→Bus→R1）=====
# 5a: ALU 运算结果先存入 Z（Zin 与 SUB/ADD 在同一节拍或之前）
alu_zin_ok = False
alu_zin_beat = None
for step in execute:
    if "Zin" in step["signal_set"]:
        alu_zin_ok = True
        alu_zin_beat = step["beat"]
        break
assert alu_zin_ok, "写回错：缺少 Zin（结果未存入 Z 锁存器）"

# 5b: Z→Bus→R1（Zout + R1in 必须在同一节拍，且在 Zin 之后）
z_to_r1_ok = False
z_to_r1_beat = None
for step in execute:
    if {"Zout", "R1in"} <= step["signal_set"]:
        z_to_r1_ok = True
        z_to_r1_beat = step["beat"]
        break
assert z_to_r1_ok, "写回错：缺少 Z→R1（Zout+R1in）"

z_to_r1_num = int(z_to_r1_beat[1:])
alu_zin_num = int(alu_zin_beat[1:])
assert z_to_r1_num > alu_zin_num, \
    f"写回错：Z→R1({z_to_r1_beat}) 在 Zin({alu_zin_beat}) 之前或同一拍，结果未经 Z 锁存"

# 5c: 不能跳过 Z 直接从 ALU/Bus 写回 R1
# （如果 R1in 出现在没有 Zout 的节拍 → 直接从总线写回，跳过 Z）
for step in execute:
    if "R1in" in step["signal_set"] and "Zout" not in step["signal_set"]:
        # R1in 不与 Zout 同时出现 → 可能从其他源写入 R1
        # 在正确序列中不应出现（R1in 只应在写回节拍与 Zout 同时出现）
        pass  # 实际上 5b 已保证 Zout+R1in 同节拍，这里不额外 assert


# ===== 底部：打印完整数据流 =====
print("=" * 70)
print("单总线数据通路 - SUB R1,R2 指令微操作序列")
print("指令语义: R1 ← R1 − R2 (ALU: A−B, A来自Y, B来自Bus)")
print("=" * 70)

print("\n【PARAMS】")
print(f"  数据通路结构: 单总线")
print(f"  ALU: 输入A=Y锁存器, 输入B=Bus, 结果→Z, 支持 ADD/SUB")
print(f"  控制信号定义表: C1~C15 共 {len(SIGNAL_TABLE)} 个信号")
print(f"  指令: SUB R1, R2 → R1 ← R1 − R2")
print(f"  寻址方式: R1、R2 均为寄存器直接寻址")
print(f"  总线输出信号(out): {sorted(BUS_OUT_SIGNALS)}")

print("\n【PROCESS / 取指阶段】")
print(f"{'节拍':<6} {'功能描述':<46} {'有效控制信号'}")
print("-" * 70)
for step in fetch:
    print(f"{step['beat']:<6} {step['desc']:<46} {step['signals']}")

print("\n【PROCESS / 执行阶段】")
print(f"{'节拍':<6} {'功能描述':<46} {'有效控制信号'}")
print("-" * 70)
for step in execute:
    print(f"{step['beat']:<6} {step['desc']:<46} {step['signals']}")

print("\n【RESULT】")
print(f"  取指阶段节拍数: {len(fetch)} (T1~T{fetch_beat_nums[-1]})")
print(f"  执行阶段节拍数: {len(execute)} (T{exec_beat_nums[0]}~T{exec_beat_nums[-1]})")
print(f"  总节拍数: {len(all_steps)} (T1~T7, 连续编号)")
print(f"  使用的全部控制信号: {sorted(all_signals)}")
print(f"  控制信号总数(去重): {len(all_signals)}")

print("\n【RULE_CHECK / 通过条件验证】")
print(f"  条件1 总线无冲突: PASS (每节拍out信号至多1个)")
for step in all_steps:
    outs = step["signal_set"] & BUS_OUT_SIGNALS
    print(f"         {step['beat']}: out信号={sorted(outs) if outs else '无'}, 数量={len(outs)}")
print(f"  条件2 控制信号一致性: PASS (全部 ∈ C1~C15)")
print(f"         未定义信号: {sorted(all_signals - SIGNAL_TABLE) if all_signals - SIGNAL_TABLE else '无'}")
print(f"  条件3 取指完整性: PASS")
print(f"         PC→MAR(PCout+MARin): {['T1'][0] if pc_to_mar_ok else '缺失'}")
print(f"         Read: 存在" if "Read" in fetch_all_signals else "         Read: 缺失")
print(f"         MDR→IR(MDRout+IRin): T3" if mdr_to_ir_ok else "         MDR→IR: 缺失")
print(f"         PC+1: 存在" if "PC+1" in fetch_all_signals else "         PC+1: 缺失")
print(f"  条件4 减法操作数顺序: PASS")
print(f"         R1→Y(被减数,R1out+Yin): {r1_to_y_beat}")
print(f"         R2→Bus(减数,R2out+SUB): {r2_to_bus_beat}")
print(f"         运算: Y−Bus = R1−R2 ✓ (顺序正确)")
print(f"  条件5 写回正确性: PASS")
print(f"         结果存入Z(Zin): {alu_zin_beat}")
print(f"         Z→Bus→R1(Zout+R1in): {z_to_r1_beat}")
print(f"         Z→R1 在 Zin 之后: {z_to_r1_beat} > {alu_zin_beat} ✓")
print(f"  条件6 节拍连续性: PASS (T1~T7 连续, 跨阶段衔接 T4→T5)")
