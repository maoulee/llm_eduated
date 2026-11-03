# -*- coding: utf-8 -*-
"""
I/O 系统综合（中断/DMA 对比与时间计算）
建模：把题干声明的运算规则 + 场景规则翻译成代码，底部 print 完整数据流。
"""

def solve():
    # ============ PARAMS（题干给定参数）============
    D            = 4096            # 数据块大小 (B)
    d_int        = 2               # 每次中断传送量 (B)
    t_int        = 3               # 每次中断 CPU 开销 (us)
    d_dma        = 4               # DMA 传送单位 = 1 字 (B)
    f            = 100e6           # CPU 时钟频率
    T_bus        = 1.0 / f         # 总线周期 = 1 个时钟周期
    T_bus_us     = T_bus * 1e6     # 总线周期
    t_dma_pre    = 5               # DMA 预处理时间
    t_dma_post   = 5               # DMA 后处理时间
    R            = 2 * 10**6       # 设备传输速率 (B/s)

    process = {}

    # ============ 第1问：中断方式 CPU 总时间 ============
    # 规则：中断次数 == D / d_int；CPU 总时间 == 中断次数 × 每次中断开销
    n_int = D // d_int
    t_int_total = n_int * t_int
    process["Q1"] = {
        "n_int": n_int,
        "t_int": t_int,
        "t_int_total_us": t_int_total
    }

    # ============ 第2问：DMA 方式 CPU 总时间 ============
    # 规则：预处理 1 次 + 后处理 1 次 + 周期窃取 (D/d_dma) 次 × T_bus
    n_dma = D // d_dma
    t_pre       = t_dma_pre * 1                # 预处理仅 1 次
    t_post      = t_dma_post * 1               # 后处理仅 1 次
    t_cyclesteal = n_dma * T_bus_us            # 周期窃取总时间
    t_dma_total = t_pre + t_cyclesteal + t_post
    process["Q2"] = {
        "n_dma": n_dma,
        "T_bus_us": T_bus_us,
        "t_pre_once_us": t_dma_pre,
        "t_post_once_us": t_dma_post,
        "t_cyclesteal_us": t_cyclesteal,
        "t_dma_total_us": t_dma_total
    }

    # ============ 第3问：节省百分比 ============
    # 规则：节省量 / 中断方式 CPU 时间 × 100%
    saved = t_int_total - t_dma_total
    pct_saved = saved / t_int_total * 100
    process["Q3"] = {
        "saved_us": saved,
        "pct_saved(2dp)": round(pct_saved, 2)
    }

    # ============ 第4问：周期窃取占设备传输时间的百分比 ============
    # 分子 = 周期窃取总时间 (D/d_dma × T_bus)
    # 分母 = 设备实际传输时间 (D / R)
    t_device_transfer = D / R * 1e6            # s → us
    pct_cyclesteal = t_cyclesteal / t_device_transfer * 100
    process["Q4"] = {
        "t_cyclesteal_us": t_cyclesteal,
        "t_device_transfer_us": t_device_transfer,
        "pct_cyclesteal(2dp)": round(pct_cyclesteal, 2)
    }

    result = {
        "Q1_中断CPU时间(us)": t_int_total,
        "Q2_DMA_CPU时间(us)": round(t_dma_total, 4),
        "Q3_节省百分比(%)": round(pct_saved, 2),
        "Q4_周期窃取占比(%)": round(pct_cyclesteal, 2)
    }

    return process, result, {
        "D": D, "d_int": d_int, "t_int": t_int, "d_dma": d_dma,
        "f": f, "T_bus_us": T_bus_us, "t_dma_pre": t_dma_pre,
        "t_dma_post": t_dma_post, "R": R
    }


process, result, params = solve()

# ============ 底部：打印完整数据流 ============
print("=" * 60)
print("PARAMS:")
for k, v in params.items():
    print(f"  {k} = {v}")

print("-" * 60)
print("PROCESS:")
print(f"  Q1 中断次数 n_int = {process['Q1']['n_int']}")
print(f"     每次中断开销 t_int = {process['Q1']['t_int']} us")
print(f"     中断CPU总时间 = {process['Q1']['n_int']} × {process['Q1']['t_int']} = {process['Q1']['t_int_total_us']} us")
print(f"  Q2 DMA传送次数 n_dma = {process['Q2']['n_dma']}")
print(f"     总线周期 T_bus = 1/{params['f']:.0e} s = {process['Q2']['T_bus_us']} us")
print(f"     预处理时间 = {process['Q2']['t_pre_once_us']} us × 1 次 = {process['Q2']['t_pre_once_us']} us")
print(f"     后处理时间 = {process['Q2']['t_post_once_us']} us × 1 次 = {process['Q2']['t_post_once_us']} us")
print(f"     周期窃取 = {process['Q2']['n_dma']} × {process['Q2']['T_bus_us']} = {process['Q2']['t_cyclesteal_us']} us")
print(f"     DMA CPU总时间 = {process['Q2']['t_pre_once_us']} + {process['Q2']['t_cyclesteal_us']} + {process['Q2']['t_post_once_us']} = {process['Q2']['t_dma_total_us']} us")
print(f"  Q3 节省量 = {process['Q3']['saved_us']} us")
print(f"     节省百分比 = {process['Q3']['saved_us']}/{process['Q1']['t_int_total_us']} × 100 = {process['Q3']['pct_saved(2dp)']}%")
print(f"  Q4 设备传输时间 = {process['Q4']['t_device_transfer_us']} us")
print(f"     周期窃取占比 = {process['Q4']['t_cyclesteal_us']}/{process['Q4']['t_device_transfer_us']} × 100 = {process['Q4']['pct_cyclesteal(2dp)']}%")

print("-" * 60)
print("RESULT:")
for k, v in result.items():
    print(f"  {k} = {v}")

# ============ 场景规则验证（通过条件 → assert）============
D = params["D"]
R = params["R"]
n_int = process["Q1"]["n_int"]
n_dma = process["Q2"]["n_dma"]
T_bus_us = params["T_bus_us"]
t_int_total = process["Q1"]["t_int_total_us"]
t_dma_total = process["Q2"]["t_dma_total_us"]
t_cyclesteal = process["Q2"]["t_cyclesteal_us"]
t_device_transfer = process["Q4"]["t_device_transfer_us"]

print("-" * 60)
print("RULE_CHECK:")
# 规则1：整除约束
assert D % params["d_int"] == 0, "D mod d_int != 0"
assert D % params["d_dma"] == 0, "D mod d_dma != 0"
print(f"  规则1 整除: {D}%{params['d_int']}==0 ✓, {D}%{params['d_dma']}==0 ✓")
# 规则2：中断高频特征
assert n_int >= 1000, "n_int < 1000"
print(f"  规则2 中断高频: n_int={n_int} >= 1000 ✓")
# 规则3：中断/DMA 次数公式（参数约束：次数=总量÷字长，任意字长成立）
assert n_int == D // params["d_int"] and n_dma == D // params["d_dma"], "次数=总量÷字长"
print(f"  规则3 次数公式: n_int=D//d_int={n_int}, n_dma=D//d_dma={n_dma} ✓")
# 规则4：预处理/后处理各一次
assert process["Q2"]["t_pre_once_us"] == params["t_dma_pre"] and process["Q2"]["t_post_once_us"] == params["t_dma_post"]
print(f"  规则4 预处理/后处理各1次: pre={params['t_dma_pre']}us×1, post={params['t_dma_post']}us×1 ✓")
# 规则5：周期窃取次数与总线周期
assert n_dma == D // params["d_dma"] and abs(T_bus_us - 1.0 / params["f"] * 1e6) < 1e-15
print(f"  规则5 窃取次数=n_dma={n_dma}, T_bus={T_bus_us}us=1/f ✓")
# 规则6：DMA效率优势
assert t_int_total > t_dma_total, "中断CPU时间应>DMA CPU时间"
print(f"  规则6 中断> DMA: {t_int_total} > {t_dma_total} us ✓")
# 规则7：第4问分母语义 + 分子<分母
assert abs(t_device_transfer - D / R * 1e6) < 1e-12 and t_cyclesteal < t_device_transfer
print(f"  规则7 分母=设备传输时间={t_device_transfer}us, 分子={t_cyclesteal}us < 分母 ✓")
print("  所有场景规则验证通过 ✓")
