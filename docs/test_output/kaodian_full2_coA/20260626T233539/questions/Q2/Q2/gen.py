# -*- coding: utf-8 -*-
"""
异步串行传输与数据传输率 —— 建模码
翻译题干帧格式 + 有效数据传输率公式 + 4 选项各自错误路径
"""


def effective_rate(B, D, N):
    """有效数据传输率 = B × D / N（场景规则2：公式）"""
    return B * D / N


# ====== 题干参数（符号参数注入） ======
START = 1      # 起始位数（固定）
D = 8          # 数据位数
P = 1          # 校验位数（奇校验）
S = 2          # 停止位数
B = 9600       # 波特率 bps

# 场景规则1：帧总位数自洽  N == 1 + D + P + S
N = START + D + P + S

# ====== A：正确结果（场景规则2 + 规则4：A = 唯一正确值）======
val_A = effective_rate(B, D, N)

# ====== B：忽略校验位（P→0），N'=1+D+0+S=11 ======
N_no_parity = START + D + 0 + S
val_B = effective_rate(B, D, N_no_parity)

# ====== C：忽略停止位（S→0），N''=1+D+P+0=10 ======
N_no_stop = START + D + P + 0
val_C = effective_rate(B, D, N_no_stop)

# ====== D：将波特率直接作为有效数据传输率 ======
val_D = B

# ====== 底部：打印完整数据流 ======
print("=" * 60)
print("PARAMS:", {
    "起始位": START,
    "数据位D": D,
    "校验位P": P,
    "停止位S": S,
    "波特率B": B,
    "帧总位N(1+D+P+S)": N,
})
print("-" * 60)
print("PROCESS:", {
    "N = 1+D+P+S": f"1+{D}+{P}+{S} = {N}",
    "N_no_parity(B选项) = 1+D+0+S": f"1+{D}+0+{S} = {N_no_parity}",
    "N_no_stop(C选项) = 1+D+P+0": f"1+{D}+{P}+0 = {N_no_stop}",
})
print("-" * 60)
print("OPTION_A:", {"正确值": val_A, "实际值": val_A, "改错方式": "无（正确选项）"})
print("OPTION_B:", {"正确值": val_A, "实际值": val_B, "改错方式": f"忽略校验位, N'={N_no_parity}, 算 B×D/N'"})
print("OPTION_C:", {"正确值": val_A, "实际值": val_C, "改错方式": f"忽略停止位, N''={N_no_stop}, 算 B×D/N''"})
print("OPTION_D:", {"正确值": val_A, "实际值": val_D, "改错方式": "将波特率直接当作有效数据传输率"})
print("-" * 60)
print("RESULT:", {
    "A(正确)": f"{val_A:.2f} bps",
    "B(忽略校验位)": f"{val_B:.2f} bps",
    "C(忽略停止位)": f"{val_C:.2f} bps",
    "D(=波特率)": f"{val_D} bps",
})
print("-" * 60)
# 场景规则验证（数据流中可直接读出）
print("RULE_CHECK:", {
    "规则1_帧总位自洽 N==1+D++P+S": f"{N} == {START+D+P+S} -> {N == START+D+P+S}",
    "规则3_4选项互异": f"A={val_A:.2f}, B={val_B:.2f}, C={val_C:.2f}, D={val_D} -> 互异={len({val_A, val_B, val_C, val_D}) == 4}",
    "规则4_A=唯一正确值": f"A={val_A:.2f} = effective_rate(B,D,N)",
})
