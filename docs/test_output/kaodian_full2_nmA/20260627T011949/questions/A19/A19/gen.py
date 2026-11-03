# -*- coding: utf-8 -*-
"""
CPU 性能综合题（CPI / MIPS / 性能比较 / 改进分析）
建模：把题干的运算规则与场景规则翻译成代码。
"""

# ============================================================
# PARAMS（题干注入参数）
# ============================================================
freq = {"M1": 3.0e9, "M2": 2.0e9}  # Hz
freq_ghz = {"M1": 3.0, "M2": 2.0}   # GHz

# 频度（百分比）
p = {"A": 0.40, "B": 0.25, "C": 0.15, "D": 0.20}

# 各类指令 CPI
cpi_M1 = {"A": 2, "B": 4, "C": 3, "D": 5}
cpi_M2 = {"A": 1, "B": 5, "C": 2, "D": 3}

categories = ["A", "B", "C", "D"]

# 改进方案参数
improved_class = "B"
improved_factor = 0.5  # 降至原来的 1/2


# ============================================================
# 建模函数
# ============================================================
def weighted_cpi(cpi_table, probs):
    """加权平均 CPI = Σ p_i × CPI_i"""
    return sum(probs[cat] * cpi_table[cat] for cat in categories)


def mips_hz(freq_hz, cpi_avg):
    """MIPS = f(Hz) / (CPI × 10^6)"""
    return freq_hz / (cpi_avg * 1e6)


def mips_ghz(freq_ghz, cpi_avg):
    """MIPS = f(GHz) × 10^3 / CPI （等价写法）"""
    return freq_ghz * 1e3 / cpi_avg


# ============================================================
# 第 1 问：加权平均 CPI
# ============================================================
cpi1 = weighted_cpi(cpi_M1, p)
cpi2 = weighted_cpi(cpi_M2, p)

# 第 1 问明细
q1_detail = {cat: (p[cat], cpi_M1[cat], cpi_M2[cat], p[cat] * cpi_M1[cat], p[cat] * cpi_M2[cat]) for cat in categories}

# ============================================================
# 第 2 问：MIPS
# ============================================================
mips1_hz = mips_hz(freq["M1"], cpi1)
mips2_hz = mips_hz(freq["M2"], cpi2)
mips1_ghz = mips_ghz(freq_ghz["M1"], cpi1)
mips2_ghz = mips_ghz(freq_ghz["M2"], cpi2)

# ============================================================
# 第 3 问：性能比较
# ============================================================
# 执行时间 ∝ CPI / f （IC 相同时）
# 时间更短 = 更快；MIPS 更高 = 更快
ratio_cpi_freq = cpi1 / freq["M1"]  # M1 的执行时间比例因子
ratio_cpi_freq2 = cpi2 / freq["M2"]  # M2 的执行时间比例因子
faster = "M1" if mips1_hz > mips2_hz else ("M2" if mips2_hz > mips1_hz else "相同")

# ============================================================
# 第 4 问：改进 M2 的 B 类 CPI
# ============================================================
cpi_M2_improved = dict(cpi_M2)
cpi_M2_improved[improved_class] = cpi_M2[improved_class] * improved_factor  # B 类 CPI: 5 → 2.5

cpi2_improved = weighted_cpi(cpi_M2_improved, p)
mips2_improved = mips_hz(freq["M2"], cpi2_improved)
speedup = mips2_improved / mips2_hz

# 改进前后变化幅度
change_ratio = abs(mips2_improved - mips2_hz) / mips2_hz


# ============================================================
# 场景规则 assert（翻译自 question.md 的可机检约束）
# ============================================================
# 规则1: 频度归一
assert abs(sum(p[cat] for cat in categories) - 1.0) < 1e-9, "频度之和必须为1"

# 规则2: 加权 CPI 定义已由 weighted_cpi 函数实现

# 规则3: MIPS 两种写法一致
assert abs(mips1_hz - mips1_ghz) < 1e-9, "M1 MIPS 两种写法不一致"
assert abs(mips2_hz - mips2_ghz) < 1e-9, "M2 MIPS 两种写法不一致"

# 规则4: 性能等价性——更快者 = MIPS 更高者 = 执行时间更短者
exec_time_factor_M1 = cpi1 / freq["M1"]
exec_time_factor_M2 = cpi2 / freq["M2"]
faster_by_time = "M1" if exec_time_factor_M1 < exec_time_factor_M2 else "M2"
faster_by_mips = "M1" if mips1_hz > mips2_hz else "M2"
assert faster_by_time == faster_by_mips, "执行时间判断与MIPS判断不一致"

# 暗坑触发检查（K4=4核心考点）：
# 单比CPI得出的结论（CPI更低者更快）必须与综合MIPS得出的结论相反，
# 才能真正考察"频率不同不能直接比CPI"。否则考点未触发。
faster_by_cpi_only = "M1" if cpi1 < cpi2 else "M2"  # 仅比CPI的结论
assert faster_by_cpi_only != faster_by_mips, \
    "暗坑未触发：单比CPI与综合MIPS结论相同，K4考点失效"

# 规则5: 改进局部性——仅 B 类 CPI 改变，其余不变
for cat in categories:
    if cat != improved_class:
        assert cpi_M2_improved[cat] == cpi_M2[cat], f"改进后{cat}类CPI不应改变"
assert cpi_M2_improved[improved_class] == cpi_M2[improved_class] * improved_factor

# 规则6: 加速比 > 1.0 且变化幅度 >= 10%
assert speedup > 1.0, "加速比必须>1"
assert change_ratio >= 0.10, "MIPS变化幅度必须>=10%"


# ============================================================
# 底部：打印完整数据流
# ============================================================
print("=" * 60)
print("PARAMS:")
print("  频度:", p)
print("  M1 CPI:", cpi_M1, " M2 CPI:", cpi_M2)
print("  M1 频率: %.1f GHz, M2 频率: %.1f GHz" % (freq_ghz["M1"], freq_ghz["M2"]))
print("  改进方案: %s类CPI × %.1f" % (improved_class, improved_factor))

print("\n" + "=" * 60)
print("第1问 — 加权平均 CPI:")
print("  明细 (类别: 频度, M1_CPI, M2_CPI, M1贡献, M2贡献):")
for cat in categories:
    pp, c1, c2, d1, d2 = q1_detail[cat]
    print("    %s: p=%.2f, M1_CPI=%d, M2_CPI=%d, M1贡献=%.2f, M2贡献=%.2f" % (cat, pp, c1, c2, d1, d2))
print("  CPI_M1 = %.4f → 保留两位: %.2f" % (cpi1, round(cpi1, 2)))
print("  CPI_M2 = %.4f → 保留两位: %.2f" % (cpi2, round(cpi2, 2)))

print("\n" + "=" * 60)
print("第2问 — MIPS:")
print("  M1 MIPS (Hz法)   = %.6f GHz / (%.4f × 10^6) = %.4f → %.2f" % (freq["M1"], cpi1, mips1_hz, round(mips1_hz, 2)))
print("  M1 MIPS (GHz法)  = %.1f × 1000 / %.4f = %.4f → %.2f" % (freq_ghz["M1"], cpi1, mips1_ghz, round(mips1_ghz, 2)))
print("  M2 MIPS (Hz法)   = %.6f GHz / (%.4f × 10^6) = %.4f → %.2f" % (freq["M2"], cpi2, mips2_hz, round(mips2_hz, 2)))
print("  M2 MIPS (GHz法)  = %.1f × 1000 / %.4f = %.4f → %.2f" % (freq_ghz["M2"], cpi2, mips2_ghz, round(mips2_ghz, 2)))
print("  规则3检查: M1两种写法差=%.2e, M2两种写法差=%.2e" % (abs(mips1_hz - mips1_ghz), abs(mips2_hz - mips2_ghz)))

print("\n" + "=" * 60)
print("第3问 — 性能比较:")
print("  CPI_M1 = %.2f, CPI_M2 = %.2f (M2 CPI更低 → 单比CPI会判M2更快)" % (cpi1, cpi2))
print("  f_M1 = %.1f GHz, f_M2 = %.1f GHz (M1 频率更高 → 反向权衡)" % (freq_ghz["M1"], freq_ghz["M2"]))
print("  【暗坑】单比CPI判: %s更快, 综合MIPS判: %s更快 → 结论相反，必须综合CPI与主频" % (faster_by_cpi_only, faster_by_mips))
print("  执行时间比例因子 M1: CPI/f = %.4f / %.1fe9 = %.4e" % (cpi1, freq_ghz["M1"], cpi1 / freq["M1"]))
print("  执行时间比例因子 M2: CPI/f = %.4f / %.1fe9 = %.4e" % (cpi2, freq_ghz["M2"], cpi2 / freq["M2"]))
print("  M1 MIPS = %.2f, M2 MIPS = %.2f" % (mips1_hz, mips2_hz))
print("  结论: 更快的机器 = %s (MIPS更高, 执行时间更短)" % faster)

print("\n" + "=" * 60)
print("第4问 — 改进 M2 B类 CPI:")
print("  改进前 M2 CPI表:", cpi_M2)
print("  改进后 M2 CPI表:", cpi_M2_improved, " (B类: %d→%.1f)" % (cpi_M2["B"], cpi_M2_improved["B"]))
print("  改进后 CPI_M2 = %.4f → %.2f" % (cpi2_improved, round(cpi2_improved, 2)))
print("  改进后 M2 MIPS = %.4f → %.2f" % (mips2_improved, round(mips2_improved, 2)))
print("  改进前 M2 MIPS = %.4f → %.2f" % (mips2_hz, round(mips2_hz, 2)))
print("  加速比 = %.4f / %.4f = %.4f → 保留三位: %.3f" % (mips2_improved, mips2_hz, speedup, round(speedup, 3)))
print("  MIPS变化幅度 = %.4f = %.2f%%" % (change_ratio, change_ratio * 100))
print("  规则6检查: 加速比>1=%s, 变化幅度>=10%%=%s" % (speedup > 1.0, change_ratio >= 0.10))

print("\n" + "=" * 60)
print("RESULT 汇总:")
print("  第1问: CPI_M1 = %.2f, CPI_M2 = %.2f" % (round(cpi1, 2), round(cpi2, 2)))
print("  第2问: MIPS_M1 = %.2f, MIPS_M2 = %.2f" % (round(mips1_hz, 2), round(mips2_hz, 2)))
print("  第3问: 更快的机器 = %s" % faster)
print("  第4问: 改进后MIPS = %.2f, 加速比 = %.3f" % (round(mips2_improved, 2), round(speedup, 3)))
print("=" * 60)
