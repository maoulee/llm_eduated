# -*- coding: utf-8 -*-
"""
总线控制方式与带宽分析 —— gen.py
建模：问题2 带宽计算 + 场景规则机检（带宽一致性 / 参数有效性 / 考察覆盖）
"""
import math

# ============================================================
# PARAMS（题干注入参数）
# ============================================================
bus_width_bits = 32          # 数据总线宽度（位）
bus_freq_MHz  = 533          # 总线工作频率（MHz）

# ============================================================
# 问题2：总线带宽计算（翻译场景规则中的带宽一致性约束）
# ============================================================
bus_width_bytes      = bus_width_bits / 8                    # 位 → 字节：32/8 = 4 B
bus_freq_Hz          = bus_freq_MHz * (10**6)                # MHz → Hz：533×10^6
bandwidth_bytes_per_s = bus_width_bytes * bus_freq_Hz        # B/s
bandwidth_MBps        = bandwidth_bytes_per_s / (10**6)      # MB/s（1 MB = 10^6 B）

# ============================================================
# 场景规则机检（把 question.md 声明的约束翻译成 assert）
# ============================================================

# --- 规则1：带宽一致性约束 ---
# bandwidth_MBps 必须等于 bus_width_bits/8 * bus_freq_MHz
assert bandwidth_MBps == (bus_width_bits / 8) * bus_freq_MHz, \
    f"带宽一致性失败: {bandwidth_MBps} != {bus_width_bits/8}*{bus_freq_MHz}"
# bandwidth_bytes_per_s 必须等于 bus_width_bits/8 * bus_freq_MHz * 10^6
assert bandwidth_bytes_per_s == (bus_width_bits / 8) * bus_freq_MHz * (10**6), \
    "bytes_per_s 一致性失败"

# --- 规则2：参数有效性约束 ---
assert bus_width_bits in (32, 64), f"总线位宽非标准值: {bus_width_bits}"
assert 100 <= bus_freq_MHz <= 1000, f"总线频率超范围: {bus_freq_MHz}"
assert not (bus_freq_MHz & (bus_freq_MHz - 1) == 0), \
    f"频率 {bus_freq_MHz} 是2的幂，不满足区分度约束"

# --- 规则3：考察覆盖约束（问题1三种方式 + 问题3选择逻辑） ---
three_methods = {
    "链式查询":   {"原理": "含总线请求BR/总线授权BG信号线，BG信号逐级链式传递",
                  "优点": ["结构简单，连线少", "扩充设备容易"],
                  "缺点": ["优先级固定（离仲裁器近优先级高）", "对电路故障敏感，一处断链后续全不可用"]},
    "计数器定时查询": {"原理": "含BR信号线+设备地址线，仲裁器内部计数器轮询设备号",
                  "优点": ["优先级可灵活设置（改计数器初值）", "对电路故障不敏感于链式"],
                  "缺点": ["线数多于链式（需设备地址线）", "计数器初值固定时优先级仍固定"]},
    "独立请求":   {"原理": "每个设备独立BR+BG线对（共2n+1条控制线），仲裁器直接裁决",
                  "优点": ["响应速度快（不需逐级传递）", "优先级由仲裁器灵活指定，可动态调整"],
                  "缺点": ["控制线数多（2n+1条），硬件复杂", "仲裁器逻辑复杂，成本高"]},
}
# 问题1 覆盖三种方式 × （原理 + ≥2优点 + ≥2缺点）
for name, info in three_methods.items():
    assert "原理" in info and len(info["原理"]) > 0, f"{name} 缺原理"
    assert len(info["优点"]) >= 2, f"{name} 优点不足2条"
    assert len(info["缺点"]) >= 2, f"{name} 缺点不足2条"

# 问题3 选择逻辑：选出的方式在问题1分析中必须具备"响应快"+"可灵活调整优先级"
chosen = "独立请求"
chosen_info = three_methods[chosen]
chosen_features = set(chosen_info["优点"])
# 场景要求：高灵活性（动态调优先级）+ 高响应速度 → 所选方式必须同时满足这两点
has_fast_response   = any("快" in f for f in chosen_features)   # 响应快
has_flexible_prio   = any("灵活" in f for f in chosen_features)  # 可动态调优先级
assert has_fast_response, f"{chosen} 不满足响应快要求"
assert has_flexible_prio, f"{chosen} 不满足灵活调整优先级要求"

# ============================================================
# 底部：打印完整数据流
# ============================================================
print("=" * 60)
print("PARAMS:")
print(f"  bus_width_bits = {bus_width_bits} 位")
print(f"  bus_freq_MHz   = {bus_freq_MHz} MHz")
print(f"  设备数（问题3场景）= 6")
print()
print("PROCESS (问题2 带宽计算):")
print(f"  bus_width_bytes       = {bus_width_bits}/8 = {bus_width_bytes} B")
print(f"  bus_freq_Hz           = {bus_freq_MHz}×10^6 = {bus_freq_Hz:.0f} Hz")
print(f"  bandwidth_bytes_per_s = {bus_width_bytes} × {bus_freq_Hz:.0f} = {bandwidth_bytes_per_s:.0f} B/s")
print(f"  bandwidth_MBps        = {bandwidth_bytes_per_s:.0f} / 10^6 = {bandwidth_MBps} MB/s")
print()
print("RESULT (问题2 答案):")
print(f"  总线带宽 = {bandwidth_MBps} MB/s  (= {bus_width_bytes} × {bus_freq_MHz})")
print()
print("RULE_CHECK:")
print(f"  规则1 带宽一致性: {bandwidth_MBps} == {bus_width_bits/8}*{bus_freq_MHz} = {(bus_width_bits/8)*bus_freq_MHz}  ✓")
print(f"  规则2 参数有效性: 位宽{bus_width_bits}∈{{32,64}} ✓ | 频率{bus_freq_MHz}∈[100,1000] ✓ | 非2的幂 ✓")
print(f"  规则3 考察覆盖: 三种方式原理+≥2优缺点 ✓ | 问题3选[{chosen}]具备 响应快={has_fast_response}, 灵活优先级={has_flexible_prio} ✓")
print(f"\n所有场景规则 assert 通过。")
