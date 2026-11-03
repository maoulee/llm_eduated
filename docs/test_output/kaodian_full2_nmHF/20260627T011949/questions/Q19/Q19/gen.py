# -*- coding: utf-8 -*-
"""
同步总线带宽计算 —— gen.py
将题干运算规则翻译为代码，忠实实现场景规则，底部打印完整数据流。

题干规则：
  Q1: 单字带宽 = (w/8) * f / C  (MB/s)
  Q2: 突发带宽 = N * (w/8) * f / (1 + N)  (MB/s)
      提升倍数 = 突发带宽 / 单字带宽

场景规则（参数间约束，换参数仍成立）：
  R1: BW_single == (w//8) * f / C
  R2: BW_burst  == N * (w//8) * f / (1 + N)
  R3: C >= 2 且 N > 1（周期数守恒）
  R4: ratio == BW_burst / BW_single 且 ratio > 1（突发必须更快）
  R5: f∈[50,200]非2幂；w∈{8,16,32,64}；C∈[2,5]；N∈[4,8]
"""

import math

def is_power_of_two(n):
    return n > 0 and (n & (n - 1)) == 0

def solve(f, w, C, N):
    # ===== 翻译题干规则 =====

    # 陷阱2：w 单位是 bit，必须 /8 转 Byte
    bytes_per_word = w // 8          # 每个数据字传输字节数

    # Q1：单字传输带宽
    # 陷阱1：分母是总周期数 C（含地址周期），不是数据周期数 C-1
    BW_single = (bytes_per_word * f) / C   # MB/s  (f 以 MHz=10^6 Hz 代入，结果天然是 MB/s)

    # Q2：突发传输带宽
    # 陷阱3：突发事务总周期数 = 1(地址) + N(数据)，不是 N*C
    burst_cycles = 1 + N
    burst_bytes = N * bytes_per_word
    BW_burst = (burst_bytes * f) / burst_cycles   # MB/s

    # 提升倍数（保留两位小数）
    ratio = BW_burst / BW_single
    ratio_rounded = round(ratio, 2)

    return {
        "bytes_per_word": bytes_per_word,
        "BW_single": BW_single,
        "burst_cycles": burst_cycles,
        "burst_bytes": burst_bytes,
        "BW_burst": BW_burst,
        "ratio": ratio,
        "ratio_rounded": ratio_rounded,
    }

def check_scene_rules(f, w, C, N, res):
    """验证场景规则（题目成立 ⇔ 这些约束满足）"""
    issues = []

    # R5: 参数范围
    if not (50 <= f <= 200):
        issues.append(f"R5_FAIL: f={f} 不在 [50,200]")
    if is_power_of_two(f):
        issues.append(f"R5_FAIL: f={f} 是2的幂（题目要求非2幂）")
    if w not in (8, 16, 32, 64):
        issues.append(f"R5_FAIL: w={w} 不在 {{8,16,32,64}}")
    if not (2 <= C <= 5):
        issues.append(f"R5_FAIL: C={C} 不在 [2,5]")
    if N not in (4, 5, 6, 7, 8):
        issues.append(f"R5_FAIL: N={N} 不在 [4,8]")

    # R1: 单字带宽公式一致性
    if res["BW_single"] != (w // 8) * f / C:
        issues.append("R1_FAIL: BW_single != (w/8)*f/C")

    # R2: 突发带宽公式一致性
    if res["BW_burst"] != N * (w // 8) * f / (1 + N):
        issues.append("R2_FAIL: BW_burst != N*(w/8)*f/(1+N)")

    # R3: 周期数守恒
    if C < 2:
        issues.append(f"R3_FAIL: C={C} < 2")
    if N <= 1:
        issues.append(f"R3_FAIL: N={N} <= 1")

    # R4: 提升倍数一致性 + ratio > 1
    if res["ratio"] != res["BW_burst"] / res["BW_single"]:
        issues.append("R4_FAIL: ratio != BW_burst/BW_single")
    if not (res["BW_burst"] / res["BW_single"] > 1):
        issues.append("R4_FAIL: 突发带宽未高于单字带宽")

    return issues


# ===== 注入题干参数 =====
f = 66    # MHz，非2的幂
w = 32    # bit
C = 3     # 单字事务总周期数（含地址周期）
N = 4     # 突发传输数据字数

res = solve(f, w, C, N)
issues = check_scene_rules(f, w, C, N, res)

# ===== 底部：打印完整数据流 =====
print("=" * 60)
print("PARAMS:", {
    "f (MHz)": f,
    "w (bit)": w,
    "C (单字事务总周期数)": C,
    "N (突发数据字数)": N,
})
print("-" * 60)
print("PROCESS:")
print("  每个数据字字节数  bytes_per_word = w/8 = {} bit / 8 = {} Byte".format(w, res["bytes_per_word"]))
print("  --- Q1: 单字传输带宽 ---")
print("  单字事务总周期数 C = {} (含1地址周期 + {}数据周期)".format(C, C - 1))
print("  BW_single = (w/8) * f / C = {} * {} / {} = {:.4f} MB/s".format(
    res["bytes_per_word"], f, C, res["BW_single"]))
print("  --- Q2: 突发传输带宽 ---")
print("  突发事务总周期数 = 1(地址) + N(数据) = 1 + {} = {}".format(N, res["burst_cycles"]))
print("  突发数据量 = N * (w/8) = {} * {} = {} Byte".format(N, res["bytes_per_word"], res["burst_bytes"]))
print("  BW_burst = N*(w/8)*f / (1+N) = {} * {} / {} = {:.4f} MB/s".format(
    res["burst_bytes"], f, res["burst_cycles"], res["BW_burst"]))
print("  --- 提升倍数 ---")
print("  ratio = BW_burst / BW_single = {:.4f} / {:.4f} = {:.4f}".format(
    res["BW_burst"], res["BW_single"], res["ratio"]))
print("  ratio (保留两位小数) = {}".format(res["ratio_rounded"]))
print("-" * 60)
print("RESULT:")
print("  Q1 答案：单字传输最大带宽 = {:.4f} MB/s".format(res["BW_single"]))
print("  Q2 答案：突发传输有效带宽 = {:.4f} MB/s".format(res["BW_burst"]))
print("  Q2 答案：带宽提升倍数 = {}".format(res["ratio_rounded"]))
print("-" * 60)
print("RULE_CHECK (场景规则验证):")
print("  R1: BW_single == (w/8)*f/C = {} == {} → {}".format(
    res["BW_single"], (w // 8) * f / C, "PASS" if res["BW_single"] == (w // 8) * f / C else "FAIL"))
print("  R2: BW_burst == N*(w/8)*f/(1+N) = {} == {} → {}".format(
    res["BW_burst"], N * (w // 8) * f / (1 + N),
    "PASS" if res["BW_burst"] == N * (w // 8) * f / (1 + N) else "FAIL"))
print("  R3: C={}>=2 且 N={}>1 → {}".format(C, N, "PASS" if C >= 2 and N > 1 else "FAIL"))
print("  R4: ratio==BW_burst/BW_single → {} / {} = {} (>1: {}) → {}".format(
    res["BW_burst"], res["BW_single"], res["ratio"],
    "是" if res["ratio"] > 1 else "否",
    "PASS" if res["ratio"] == res["BW_burst"] / res["BW_single"] and res["ratio"] > 1 else "FAIL"))
print("  R5: f={}非2幂={} | w={}∈{{8,16,32,64}}={} | C={}∈[2,5]={} | N={}∈[4,8]={}".format(
    f, "是" if not is_power_of_two(f) else "否",
    w, "是" if w in (8,16,32,64) else "否",
    C, "是" if 2<=C<=5 else "否",
    N, "是" if N in (4,5,6,7,8) else "否"))

if issues:
    print("\n!!! 场景规则验证未通过 !!!")
    for iss in issues:
        print("  -", iss)
else:
    print("\n>>> 全部场景规则验证通过 <<<")
