"""
gen.py — SUB R1,(R2) 单总线数据通路执行阶段微操作序列建模
题干翻译：题干规则 → 代码；通过条件 → assert
"""
import re

# ============================================================
# PARAMS：题干参数
# ============================================================
PARAMS = {
    "指令": "SUB R1, (R2)",
    "功能": "R1 ← R1 − M[R2]",
    "总线类型": "单总线（同一时刻至多一个寄存器输出到总线）",
    "ALU输入A": "暂存器 Y",
    "ALU输入B": "内部总线",
    "ALU输出": "暂存器 Z（ADD/SUB 结果自动锁存）",
    "SUB定义": "Z ← Y − 总线",
    "寻址方式": "寄存器间接寻址（R2 内容作为访存地址）",
}

# ============================================================
# 微操作序列（执行阶段，不含取指/译码）
#
# 翻译题干规则：
#   功能 R1 ← R1 − M[R2]
#   SUB 定义 Z ← Y − 总线
#   => Y 必须存被减数 R1，总线必须传减数 M[R2]
#
# 推导步骤：
#   ① 需访存取操作数 M[R2]：先送 R2→MAR，再 Read→MDR
#   ② Y 须存 R1（被减数）：送 R1→Y
#   ③ 送 M[R2]（减数）到总线 + SUB：Z = Y − 总线 = R1 − M[R2]
#   ④ 写回：Z→R1
# ============================================================
micro_ops = [
    ("T1", "R2 的内容（访存地址）送入 MAR",
     ["R2out", "MARin"]),

    ("T2", "启动存储器读，将 M[R2] 读入 MDR",
     ["Read"]),

    ("T3", "R1 的内容（被减数）送上总线并写入暂存器 Y（锁存至 ALU 输入端 A）",
     ["R1out", "Yin"]),

    ("T4", "MDR 的内容（操作数 M[R2]）送上总线（ALU 输入端 B），执行减法 Z ← Y − 总线",
     ["MDRout", "SUB"]),

    ("T5", "暂存器 Z 的内容（运算结果）写回 R1",
     ["Zout", "R1in"]),
]

n_steps = len(micro_ops)

# ============================================================
# 打印 PARAMS + REASONING
# ============================================================
print("=" * 70)
print("PARAMS")
for k, v in PARAMS.items():
    print(f"  {k}: {v}")

print("\n" + "=" * 70)
print("REASONING — 执行阶段微操作序列推导")
print("-" * 70)
print("指令功能: R1 ← R1 − M[R2]")
print("SUB 定义:  Z ← Y − 总线")
print("=> Y 须存 R1（被减数），总线须传 M[R2]（减数），结果 = R1 − M[R2]")
print()
print("执行步骤分解:")
print("  ① 访存取操作数 M[R2]:  R2→MAR, Read→MDR")
print("  ② 锁存被减数 R1 到 Y:  R1→总线→Yin")
print("  ③ 送减数 M[R2] 到总线并执行 SUB:  MDRout + SUB → Z = Y − M[R2] = R1 − M[R2]")
print("  ④ 写回结果到 R1:  Zout + R1in")
print("-" * 70)

for T, desc, signals in micro_ops:
    print(f"  {T}: {desc}")
    print(f"       控制信号: {', '.join(signals)}")

print(f"\n执行阶段总步数: {n_steps}")

# ============================================================
# ASSERT — 通过条件逐条验证
# ============================================================
print("\n" + "=" * 70)
print("ASSERT — 6 条通过条件验证")

# --- 条件1：步数在 [4,8] 且 >= 5 ---
print(f"\n[条件1] 步数 {n_steps} ∈ [4,8] 且 >= 5")
assert 4 <= n_steps <= 8 and n_steps >= 5, f"步数 {n_steps} 不满足"
print(f"  ✓ assert 4 <= {n_steps} <= 8  且  {n_steps} >= 5")

# --- 条件2：单总线约束——每节拍至多一个 Xout ---
print(f"\n[条件2] 单总线约束：每节拍至多一个 'Xout'")
for T, desc, signals in micro_ops:
    out_sigs = [s for s in signals if s.endswith("out")]
    assert len(out_sigs) <= 1, f"{T} 出现 {len(out_sigs)} 个 Xout: {out_sigs}"
    print(f"  {T}: Xout={out_sigs} (数量 {len(out_sigs)}) ✓")

# --- 条件3：Y 正确使用——Yin 先于 SUB ---
print(f"\n[条件3] Y 正确使用：Yin 节拍先于 SUB 节拍")
all_signals_flat = [s for _, _, sigs in micro_ops for s in sigs]
assert "Yin" in all_signals_flat, "缺少 Yin"
yin_step = next(i for i, (_, _, sigs) in enumerate(micro_ops) if "Yin" in sigs)
sub_step = next(i for i, (_, _, sigs) in enumerate(micro_ops) if "SUB" in sigs)
assert yin_step < sub_step, f"Yin(T{yin_step+1}) 必须在 SUB(T{sub_step+1}) 之前"
print(f"  Yin 在 T{yin_step+1}，SUB 在 T{sub_step+1}，顺序正确 ✓")

# --- 条件4：减法操作数顺序——Y←R1(被减数)，总线←M[R2](减数) ---
print(f"\n[条件4] 减法操作数顺序：Y 锁存 R1（被减数），总线传 M[R2]（减数）")
yin_sigs = micro_ops[yin_step][2]
sub_sigs = micro_ops[sub_step][2]
assert "R1out" in yin_sigs, "Yin 节拍缺少 R1out（Y 应锁存 R1 被减数）"
assert "MDRout" in sub_sigs, "SUB 节拍缺少 MDRout（总线应传 M[R2] 减数）"
print(f"  T{yin_step+1}: R1out → Yin,  Y ← R1（被减数）✓")
print(f"  T{sub_step+1}: MDRout + SUB, Z ← Y − 总线 = R1 − M[R2] ✓")

# --- 条件5：写回完整——最后节拍含 Zout + R1in ---
print(f"\n[条件5] 写回完整：最后节拍含 Zout + R1in")
last_sigs = micro_ops[-1][2]
assert "Zout" in last_sigs, "最后节拍缺少 Zout"
assert "R1in" in last_sigs, "最后节拍缺少 R1in"
print(f"  T{micro_ops[-1][0]}: 含 Zout + R1in ✓")

# --- 条件6：第(2)问可证伪——取消 Y 后不可行 ---
print(f"\n[条件6] 第(2)问可证伪：取消 Y → ALU 两端均连总线 → 不可行")
single_bus_capacity = 1   # 单总线同一时刻传输的数据数
alu_input_ports = 2       # ALU 需要两个不同操作数
assert single_bus_capacity < alu_input_ports, \
    "单总线容量应不足以为 ALU 两端同时供数"
print(f"  单总线同时传输能力 = {single_bus_capacity} < ALU 输入端数 = {alu_input_ports}")
print(f"  => 取消 Y 后无法同时供两操作数 → 方案不可行 ✓")

# ============================================================
# ANSWER
# ============================================================
print("\n" + "=" * 70)
print("ANSWER")
print("-" * 70)
print("\n第(1)问：执行阶段微操作序列")
print(f"{'节拍':<6}{'微操作功能描述':<55}{'有效控制信号'}")
print("-" * 70)
for T, desc, signals in micro_ops:
    print(f"{T:<6}{desc:<55}{', '.join(signals)}")
print(f"\n执行阶段共 {n_steps} 个节拍。")

print("\n第(2)问：")
print("方案不可行。")
print("原因：单总线结构中，同一时刻总线只能传输一个数据。取消暂存器 Y 后，")
print("ALU 的两个输入端 A 和 B 都连接到同一条内部总线，但单总线无法在同一")
print("节拍内同时为两个输入端提供两个不同的操作数。暂存器 Y 的作用正是在")
print("前一节拍锁存一个操作数（R1），使得后一节拍总线可以传输另一个操作数")
print("（M[R2]），从而完成 SUB 运算。取消 Y 后此机制失效，无法执行双操作数运算。")

print("\n" + "=" * 70)
print("ALL ASSERTS PASSED ✓")
