# -*- coding: utf-8 -*-
"""
题目：总线带宽计算
建模：把场景规则逐句翻译成代码，底部打印完整数据流。

场景规则：
1. 带宽公式 B = F × (W/8)，结果为正整数 MB/s
2. W 为 8 的整数倍
3. 四选项互异
4. 正确值唯一
5. 干扰项对应声明错误类型：
   B错误路径 = F × W（未÷8，bit宽度直接乘频率）
   C错误路径 = 把 F 当 GHz 量级（F数值直接当GHz用 → F_GHz_MHz = F*1000 → 带宽放大1000倍）
   D错误路径 = W × 8 / F（乘除颠倒）
"""

def correct(W, F):
    """正确：W 先由 bit 换算为 Byte（÷8），再乘频率。"""
    return F * (W // 8)

def error_B(W, F):
    """错误路径B：忘记÷8，直接用 bit 宽度 × 频率。"""
    return F * W

def error_C(W, F):
    """错误路径C：将频率单位 MHz 误认为 GHz（数值直接当 GHz，等价 F*1000 MHz）。
    所得带宽 = (F*1000) × (W/8) = correct × 1000。"""
    return (F * 1000) * (W // 8)

def error_D(W, F):
    """错误路径D：公式混淆，误用 W × 8 / F（乘除颠倒）。"""
    return W * 8 // F

# ---- 注入参数 ----
W = 32   # bit
F = 200  # MHz

# ---- 计算各选项值 ----
val_A = correct(W, F)
val_B = error_B(W, F)
val_C = error_C(W, F)
val_D = error_D(W, F)

# ---- 场景规则校验（非恒真，打到特征）----
# 规则2: W 为 8 的整数倍
assert W % 8 == 0, f"规则2违反：W={W} 不是8的整数倍"
# 规则1: B 为正整数
assert isinstance(val_A, int) and val_A > 0, f"规则1违反：B={val_A} 非正整数"
# 规则5: 干扰项等于声明错误路径产物
assert val_B == F * W, f"规则5违反：B项不等于F*W"
assert val_C == correct(W, F) * 1000, f"规则5违反：C项不等于correct*1000"
assert val_D == W * 8 // F, f"规则5违反：D项不等于W*8/F"
# 规则3&4: 四选项互异，A唯一正确
opts = {"A": val_A, "B": val_B, "C": val_C, "D": val_D}
assert len(set(opts.values())) == 4, f"规则3/4违反：选项值有碰撞 {opts}"

# ---- 底部：打印完整数据流 ----
print("=" * 60)
print("PARAMS:", {"W_bit": W, "F_MHz": F})
print("-" * 60)
print("PROCESS:")
print("  W_Byte = W_bit / 8 =", W, "/ 8 =", W // 8, "Byte")
print("  A正确路径: F × (W/8) =", F, "×", W // 8, "=", val_A, "MB/s")
print("  B错误路径: F × W（未÷8） =", F, "×", W, "=", val_B, "(bit·MHz, 量纲错)")
print("  C错误路径: (F×1000)×(W/8) =", F * 1000, "×", W // 8, "=", val_C, "(MHz误当GHz, 放大1000倍)")
print("  D错误路径: W×8/F =", W, "× 8 /", F, "=", val_D, "(乘除颠倒)")
print("-" * 60)
print("RESULT:", {"A": val_A, "B": val_B, "C": val_C, "D": val_D})
print("-" * 60)
print("RULE_CHECK:")
print("  规则1 B为正整数MB/s:", val_A, "→", isinstance(val_A, int) and val_A > 0)
print("  规则2 W%8==0:", W % 8 == 0)
print("  规则5 B==F×W:", val_B == F * W)
print("  规则5 C==correct×1000:", val_C == val_A * 1000)
print("  规则5 D==W×8/F:", val_D == W * 8 // F)
print("  规则3/4 四选项互异:", len(set(opts.values())) == 4, opts)
print("  C/A比 =", val_C / val_A, "(应为1000, 数量级偏差)")
print("  B/A比 =", val_B / val_A, "(应为8, 未÷8放大)")
print("=" * 60)
