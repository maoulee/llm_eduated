"""
异步串行传输有效数据传输率
帧格式: 1位起始位 + 8位数据位 + 1位奇校验位 + 1位停止位
波特率 B = 9600 baud，每个码元携带 1 bit
有效数据传输率 = B × d / n  （d=数据位数, n=帧总位数）
"""

# ============ PARAMS ============
B = 9600       # 波特率 (baud)
start_bit = 1  # 起始位
d = 8          # 数据位
parity = 1     # 奇校验位
stop_bit = 1   # 停止位

# 帧总位数 n = 起始位 + 数据位 + 校验位 + 停止位
n = start_bit + d + parity + stop_bit

print("=== PARAMS ===")
print(f"B(波特率) = {B} baud")
print(f"起始位={start_bit}, 数据位d={d}, 校验位={parity}, 停止位={stop_bit}")
print(f"帧总位数 n = {start_bit}+{d}+{parity}+{stop_bit} = {n}")

# ============ REASONING ============
print("\n=== REASONING ===")

# 正确计算: 有效数据传输率 = B × d / n
A = B * d / n
print(f"正确值 A = B × d / n = {B} × {d} / {n} = {B*d}/{n} = {A:.4f} bps")

# 干扰项 B: 忽略附加位开销，直接取波特率
B_opt = B * 1.0
print(f"干扰项 B = 波特率本身 = {B_opt:.4f} bps  (忽略附加位开销)")

# 干扰项 C: 漏算起始位，n 误计为 10
n_wrong = d + parity + stop_bit  # 漏掉起始位 = 8+1+1 = 10
C = B * d / n_wrong
print(f"干扰项 C = {B} × {d} / {n_wrong} = {B*d}/{n_wrong} = {C:.4f} bps  (漏算起始位)")

# 干扰项 D: 比例方向颠倒，帧总位数做分子、数据位数做分母
D = B * n / d
print(f"干扰项 D = {B} × {n} / {d} = {B*n}/{d} = {D:.4f} bps  (比例方向颠倒)")

print(f"\n四舍五入取整:")
print(f"  A ≈ {round(A)} bps")
print(f"  B = {round(B_opt)} bps")
print(f"  C = {round(C)} bps")
print(f"  D = {round(D)} bps")

# ============ ANSWER ============
print("\n=== ANSWER ===")
print(f"A = {A:.2f} bps  (正确答案)")
print(f"B = {B_opt:.2f} bps")
print(f"C = {C:.2f} bps")
print(f"D = {D:.2f} bps")

# ============ ASSERT (通过条件 → 可机检特征) ============

# 条件1: 帧总位数正确 n=11
assert n == 11, f"帧总位数应为11，实际={n}"

# 条件2: 正确值唯一确定 A = 9600×8/11
assert abs(A - 9600 * 8 / 11) < 1e-9, f"A 应等于 9600*8/11，实际={A}"

# 条件3: 4选项互异
options = {A, B_opt, C, D}
assert len(options) == 4, f"4个选项应互异，实际只有{len(options)}个不同值"

# 条件4: 干扰项对应声明错误类型
# B = 9600（忽略附加位开销）
assert abs(B_opt - 9600) < 1e-9, f"B 应为9600，实际={B_opt}"
# C = 9600×8/10（漏算起始位，n误计10）
assert abs(C - 9600 * 8 / 10) < 1e-9, f"C 应为 9600*8/10，实际={C}"
assert n_wrong == 10, f"C的误算帧总位应为10，实际={n_wrong}"
# D = 9600×11/8（比例方向颠倒）
assert abs(D - 9600 * 11 / 8) < 1e-9, f"D 应为 9600*11/8，实际={D}"

# 条件5: 干扰项有合理性——非荒谬值（均在 [0, 50000] 合理范围内）
for label, val in [("A",A),("B",B_opt),("C",C),("D",D)]:
    assert 0 < val < 50000, f"{label}={val} 超出合理范围"

# 正确值与各干扰项差值足够大（无碰撞）
for label, val in [("B",B_opt),("C",C),("D",D)]:
    assert abs(A - val) > 100, f"A与{label}差值过小(|{A-val:.2f}|<=100)，区分度不足"

print("\n✅ 所有 assert 通过，通过条件全部满足。")
