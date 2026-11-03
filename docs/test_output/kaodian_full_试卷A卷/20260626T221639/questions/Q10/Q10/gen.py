# -*- coding: utf-8 -*-
"""
中断I/O方式可行性分析 —— 建模码
逐句翻译 question.md 声明的场景规则（5条通过条件），
底部打印完整数据流（PARAMS / PROCESS / RESULT / RULE_CHECK），
并用 assert 打场景规则（打到特征，非恒真结构判据）。
"""

# ========== PARAMS（题干给定参数）==========
f_hz     = 2_000_000_000      # CPU 主频 2 GHz = 2e9 Hz
C_resp   = 500                # 中断响应时钟周期
C_serv   = 4000               # 中断服务时钟周期
C_rest   = 500                # 中断恢复时钟周期
R_A_kbs  = 512                # 设备A传输率 512 KB/s
R_B_kbs  = 2048               # 设备B传输率 2048 KB/s
D_bytes  = 4                  # 每次中断传输数据量 4 B（两设备相同）
KB       = 1024               # 1 KB = 1024 B

# ---------- 场景规则1：中断总时间一致性 ----------
# T_total = (C_resp + C_serv + C_rest) / f
total_cycles = C_resp + C_serv + C_rest
T_total_s  = total_cycles / f_hz          # 秒
T_total_us = T_total_s * 1e6             # 微秒

# ---------- 场景规则2：数据到达间隔一致性 ----------
# T_interval = D / R,  R(KB/s)×1024 = R(B/s)
R_A_bs = R_A_kbs * KB                    # B/s
R_B_bs = R_B_kbs * KB                    # B/s
T_A_s  = D_bytes / R_A_bs                # 秒
T_B_s  = D_bytes / R_B_bs                # 秒
T_A_us = T_A_s * 1e6                     # 微秒
T_B_us = T_B_s * 1e6                     # 微秒

# ---------- 场景规则3：可行性判断一致性 ----------
# 中断I/O可行  <=>  T_total <= T_interval
feasible_A = T_total_us <= T_A_us
feasible_B = T_total_us <= T_B_us

# 比值（用于规则4、规则5 判断）
ratio_total_to_B = T_total_us / T_B_us   # T_total / T_B
ratio_A_to_total = T_A_us / T_total_us   # T_A / T_total

# ========== 打印完整数据流 ==========
print("=" * 60)
print("PARAMS:")
print("  f_hz     =", f_hz, "(2 GHz)")
print("  C_resp   =", C_resp)
print("  C_serv   =", C_serv)
print("  C_rest   =", C_rest)
print("  R_A_kbs  =", R_A_kbs, "KB/s")
print("  R_B_kbs  =", R_B_kbs, "KB/s")
print("  D_bytes  =", D_bytes, "B")
print()

print("PROCESS:")
print("  [第(1)问 中断总时间]")
print("  total_cycles = C_resp + C_serv + C_rest = %d + %d + %d = %d" % (C_resp, C_serv, C_rest, total_cycles))
print("  T_total(s)   = %d / %d = %.12g s" % (total_cycles, f_hz, T_total_s))
print("  T_total(us)  = %.12g us" % T_total_us)
print()
print("  [第(2)问 中断间隔]")
print("  R_A(B/s) = %d * 1024 = %d B/s" % (R_A_kbs, R_A_bs))
print("  R_B(B/s) = %d * 1024 = %d B/s" % (R_B_kbs, R_B_bs))
print("  T_A(s) = %d / %d = %.12g s" % (D_bytes, R_A_bs, T_A_s))
print("  T_B(s) = %d / %d = %.12g s" % (D_bytes, R_B_bs, T_B_s))
print("  T_A(us) = %.12g us" % T_A_us)
print("  T_B(us) = %.12g us" % T_B_us)
print()
print("  [第(3)问 可行性]")
print("  feasible_A = (T_total <= T_A) = (%.6g <= %.6g) = %s" % (T_total_us, T_A_us, feasible_A))
print("  feasible_B = (T_total <= T_B) = (%.6g <= %.6g) = %s" % (T_total_us, T_B_us, feasible_B))
print("  ratio T_total/T_B = %.6g" % ratio_total_to_B)
print("  ratio T_A/T_total = %.6g" % ratio_A_to_total)
print()

print("RESULT:")
print("  第(1)问 T_total = %.6g us (= %g 个时钟周期 / 2GHz)" % (T_total_us, total_cycles))
print("  第(2)问 T_A = %.6g us,  T_B = %.6g us" % (T_A_us, T_B_us))
print("  第(3)问 设备A可行=%s  设备B可行=%s" % (feasible_A, feasible_B))
print("=" * 60)

# ========== 场景规则 assert（通过条件 → assert，打到特征） ==========
# 规则1：三阶段周期和忠实等于题干给定值
assert total_cycles == (C_resp + C_serv + C_rest)
# 规则1-续：T_total = total_cycles / f（换算一致性）
assert abs(T_total_s - total_cycles / f_hz) < 1e-15
# 规则2：T_interval = D / R（B/s），R(KB/s)*1024
assert abs(T_A_s - D_bytes / (R_A_kbs * KB)) < 1e-15
assert abs(T_B_s - D_bytes / (R_B_kbs * KB)) < 1e-15
# 规则3：设备A必须可行（T_total <= T_A）
assert feasible_A == True, "规则3: 设备A应可行但feasible_A=%s" % feasible_A
# 规则3：设备B必须不可行（T_total > T_B）
assert feasible_B == False, "规则3: 设备B应不可行但feasible_B=%s" % feasible_B
# 规则4：T_total / T_B 不等于整数（避免边界模糊）
assert ratio_total_to_B != int(ratio_total_to_B), \
    "规则4: T_total/T_B=%.6g 恰为整数，边界模糊" % ratio_total_to_B
# 规则5：设备A安全裕度 T_A / T_total >= 3
assert ratio_A_to_total >= 3, \
    "规则5: T_A/T_total=%.6g < 3，设备A安全裕度不足" % ratio_A_to_total

print("ALL_RULE_CHECKS_PASSED")
