# -*- coding: utf-8 -*-
"""
CPI 与 MIPS 计算综合题——建模与求解
翻译 question.md 的运算规则为可执行代码。
"""

def solve(cpi_list, ratio_list, freq_hz, N):
    """
    cpi_list  : 各类指令 CPI 列表
    ratio_list: 各类指令使用比例(百分比)列表
    freq_hz   : CPU 主频(Hz)
    N         : 程序总指令数

    返回 CPI_weighted / MIPS / exec_time 以及完整数据流。
    """
    # ---- 翻译 Q1: 加权平均 CPI = Σ(CPIi × ratioi) ----
    detail_cpi = []
    cpi_weighted = 0.0
    for i in range(len(cpi_list)):
        ratio_decimal = ratio_list[i] / 100.0          # 百分比 -> 小数
        term = cpi_list[i] * ratio_decimal
        detail_cpi.append({
            "类别i": i,
            "CPIi": cpi_list[i],
            "比例%": ratio_list[i],
            "比例小数": ratio_decimal,
            "CPIi×比例": term,
        })
        cpi_weighted += term

    # ---- 翻译 Q2: MIPS = 主频(Hz) / (CPI × 10^6) ----
    mips = freq_hz / (cpi_weighted * 1e6)

    # ---- 翻译 Q3: 执行时间 = N × CPI / 主频(Hz) ----
    exec_time = N * cpi_weighted / freq_hz

    # ---- 公式链一致性: exec_time == N / (MIPS × 10^6) ----
    exec_time_via_mips = N / (mips * 1e6)

    return {
        "cpi_weighted": cpi_weighted,
        "mips": mips,
        "exec_time": exec_time,
        "exec_time_via_mips": exec_time_via_mips,
        "detail_cpi": detail_cpi,
    }


# ============ 注入参数 ============
cpi_list    = [1, 3, 2, 2]          # ALU / Load / Store / 转移
ratio_list  = [50, 20, 15, 15]      # 百分比
freq_hz     = 800 * 10**6           # 800 MHz -> Hz
N           = 2 * 10**8             # 2×10^8 条

res = solve(cpi_list, ratio_list, freq_hz, N)

# ============ 底部打印完整数据流 ============
print("=" * 60)
print("PARAMS:")
print("  cpi_list   =", cpi_list)
print("  ratio_list =", ratio_list, "(百分比)")
print("  freq       =", freq_hz, "Hz =", freq_hz / 1e6, "MHz")
print("  N          =", N)
print()

print("PROCESS — Q1 加权平均 CPI:")
for d in res["detail_cpi"]:
    print(f"  类别{d['类别i']}: CPI={d['CPIi']}, 比例={d['比例%']}% -> "
          f"小数={d['比例小数']}, 项(CPIi×比例)={d['CPIi×比例']}")
cpi_terms_str = " + ".join(
    f"{d['CPIi']}×{d['比例小数']}" for d in res["detail_cpi"]
)
print(f"  CPI_weighted = {cpi_terms_str} = {res['cpi_weighted']}")
print()

print("PROCESS — Q2 MIPS:")
print(f"  MIPS = 主频 / (CPI × 10^6)")
print(f"       = {freq_hz} / ({res['cpi_weighted']} × 10^6)")
print(f"       = {freq_hz} / {res['cpi_weighted'] * 1e6}")
print(f"       = {res['mips']}")
print(f"  MIPS(保留2位小数) = {round(res['mips'], 2)}")
print()

print("PROCESS — Q3 执行时间:")
print(f"  exec_time = N × CPI / 主频")
print(f"            = {N} × {res['cpi_weighted']} / {freq_hz}")
print(f"            = {N * res['cpi_weighted']} / {freq_hz}")
print(f"            = {res['exec_time']} s")
print(f"  exec_time(保留3位小数) = {round(res['exec_time'], 3)} s")
print()

print("=" * 60)
print("RESULT:")
print(f"  Q1  CPI_weighted = {res['cpi_weighted']}")
print(f"  Q2  MIPS         = {res['mips']}  (≈{round(res['mips'], 2)})")
print(f"  Q3  exec_time    = {res['exec_time']} s  (≈{round(res['exec_time'], 3)} s)")
print()

# ============ 场景规则断言（通过条件，打到特征 / 禁弱化为恒真）============
print("=" * 60)
print("RULE_CHECK — 场景规则验证:")

# 规则1: 比例归一化 == 100
r1 = sum(ratio_list)
assert r1 == 100, f"比例之和={r1}, 应为100"
print(f"  [规则1] 比例之和 = {r1} == 100  ✓")

# 规则2: CPI 非平凡性 — 至少两类CPI不同 且 至少一类CPI≥3
assert len(set(cpi_list)) >= 2, "CPI值全部相同，加权平均退化为简单取值"
assert max(cpi_list) >= 3, "无任何CPI≥3，参数退化"
print(f"  [规则2] 不同CPI值集合 = {sorted(set(cpi_list))} (≥2种), max={max(cpi_list)} (≥3)  ✓")

# 规则3: 加权CPI公式正确性 — 重算验证
r3_manual = sum(cpi_list[i] * ratio_list[i] / 100.0 for i in range(len(cpi_list)))
assert abs(r3_manual - res["cpi_weighted"]) < 1e-12, "加权CPI公式不符"
print(f"  [规则3] CPI_weighted={res['cpi_weighted']} == Σ(CPIi×ratioi)={r3_manual}  ✓")

# 规则4: MIPS公式正确性
r4_manual = freq_hz / (res["cpi_weighted"] * 1e6)
assert abs(r4_manual - res["mips"]) < 1e-9, "MIPS公式不符"
print(f"  [规则4] MIPS={res['mips']} == 主频/(CPI×10^6)={r4_manual}  ✓")

# 规则5: 执行时间公式正确性 + 量级 0.001s ~ 10s
r5_manual = N * res["cpi_weighted"] / freq_hz
assert abs(r5_manual - res["exec_time"]) < 1e-15, "执行时间公式不符"
assert 0.001 <= res["exec_time"] <= 10, f"执行时间{res['exec_time']}不在[0.001,10]s范围"
print(f"  [规则5] exec_time={res['exec_time']}s ∈ [0.001, 10]s  ✓")

# 规则6: 公式链一致性 exec_time == N/(MIPS×10^6)
assert abs(res["exec_time"] - res["exec_time_via_mips"]) < 1e-15, "公式链不一致"
print(f"  [规则6] exec_time={res['exec_time']} == N/(MIPS×10^6)={res['exec_time_via_mips']}  ✓")

# 规则7: MIPS 非整数
assert res["mips"] != int(res["mips"]), "MIPS为整数，退化无区分度"
print(f"  [规则7] MIPS={res['mips']} 非整数  ✓")

print()
print("ALL RULES PASSED ✓")
