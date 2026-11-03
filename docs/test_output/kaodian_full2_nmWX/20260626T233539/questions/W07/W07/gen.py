"""
Cache 命中率与平均访问时间计算 — gen.py
翻译 question.md 声明的运算规则与场景规则（通过条件 → assert）。
"""

from fractions import Fraction as F


def solve(t_c, t_m, N, H, t_c2, h2):
    # ---- 第（1）题：命中率 / 缺失率 ----
    # 规则：h = H / N
    h = F(H, N)
    h_miss = 1 - h

    # ---- 第（2）题：AMAT + 效率 ----
    # 规则：AMAT = t_c + (1-h)*t_m   (缺失代价 = t_m，不含已消耗的 t_c)
    amat = t_c + (1 - h) * t_m

    # 效率 e = t_c / AMAT
    e = F(t_c) / amat

    # ---- 第（3）题：二级 Cache 递推 ----
    # 规则：AMAT2 = t_c + (1-h)*[t_c2 + (1-h2)*t_m]
    amat2 = t_c + (1 - h) * (t_c2 + (1 - h2) * t_m)

    return {
        "t_c": t_c, "t_m": t_m, "N": N, "H": H,
        "t_c2": t_c2, "h2": h2,
        "h": h, "h_miss": h_miss,
        "amat": amat, "e": e,
        "amat2": amat2,
    }


# ===================== 注入参数 =====================
P = dict(t_c=F(2), t_m=F(40), N=1000, H=950, t_c2=F(8), h2=F(4, 5))
R = solve(**P)

h       = R["h"]
h_miss  = R["h_miss"]
amat    = R["amat"]
e       = R["e"]
amat2   = R["amat2"]
t_c     = R["t_c"]
t_m     = R["t_m"]
t_c2    = R["t_c2"]
h2      = R["h2"]
N       = R["N"]
H       = R["H"]

# ===================== 数据流打印 =====================
print("=" * 60)
print("PARAMS:", {
    "t_c": int(t_c), "t_m": int(t_m), "N": N, "H": H,
    "t_c2": int(t_c2), "h2": float(h2),
})
print("-" * 60)
print("Q1 PROCESS:")
print("  h      = H/N = %d/%d = %s  (= %.2f)" % (H, N, h, float(h)))
print("  h_miss = 1-h = %s  (= %.2f)" % (h_miss, float(h_miss)))
print("-" * 60)
print("Q2 PROCESS:")
print("  1-h        = %s" % (1 - h))
print("  AMAT = t_c + (1-h)*t_m = %d + %s*%d = %s  (= %.2f)" % (
    int(t_c), (1 - h), int(t_m), amat, float(amat)))
print("  等价写法 h*t_c+(1-h)*(t_c+t_m) = %s" % (
    h * t_c + (1 - h) * (t_c + t_m)))
print("  e = t_c/AMAT = %d / %s = %s  (= %.4f)" % (
    int(t_c), amat, e, float(e)))
print("-" * 60)
print("Q3 PROCESS:")
print("  L1缺失部分 = t_c2 + (1-h2)*t_m = %d + %s*%d = %s" % (
    int(t_c2), (1 - h2), int(t_m), t_c2 + (1 - h2) * t_m))
print("  AMAT2 = t_c + (1-h)*[t_c2+(1-h2)*t_m]")
print("        = %d + %s*%s = %s  (= %.2f)" % (
    int(t_c), (1 - h), t_c2 + (1 - h2) * t_m, amat2, float(amat2)))
print("  AMAT2 < AMAT ?  %s  (%s < %s)" % (amat2 < amat, amat2, amat))
print("-" * 60)
print("RESULT:")
print("  h = %s, h_miss = %s" % (float(h), float(h_miss)))
print("  AMAT = %s, e = %s" % (float(amat), float(e)))
print("  AMAT2 = %s" % float(amat2))
print("=" * 60)

# ===================== 通过条件（场景规则 → assert） =====================
# 规则1: h = H/N 且 h + h_miss == 1
assert h == F(H, N), "命中率必须等于 H/N"
assert h + h_miss == 1, "命中率+缺失率必须=1"

# 规则2: AMAT 两种等价写法必须相等
amat_equiv = h * t_c + (1 - h) * (t_c + t_m)
assert amat == amat_equiv, "AMAT两种写法不等: %s != %s" % (amat, amat_equiv)

# 规则3: e = t_c/AMAT 且 0 < e <= 1
assert e == t_c / amat, "效率定义不符"
assert 0 < e <= 1, "效率应在(0,1]: e=%s" % e

# 规则4: AMAT2 递推公式 + AMAT2 >= t_c
amat2_formula = t_c + (1 - h) * (t_c2 + (1 - h2) * t_m)
assert amat2 == amat2_formula, "AMAT2递推公式不符"
assert amat2 >= t_c, "AMAT2不应低于命中时间"

# 规则5: t_m = 20*t_c 且 0.8 <= h <= 0.98
assert t_m == 20 * t_c, "t_m必须是t_c的20倍"
assert F(8, 10) <= h <= F(98, 100), "命中率h应在[0.80,0.98]"

# 规则6: AMAT2 < AMAT (L2改善性)
assert amat2 < amat, "增设L2后AMAT应下降"

print("\n>>> 全部场景规则 assert 通过 <<<")
