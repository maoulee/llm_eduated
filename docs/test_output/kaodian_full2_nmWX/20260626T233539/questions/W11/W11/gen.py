"""
水平型微指令格式设计与控存容量 —— 代码翻译（func_model）
题干规则直接翻译成 Python，底部 print 完整数据流。
"""
import math

def solve(groups, num_test_conditions, next_addr_bits):
    """
    groups: [(组名, 组内微命令数), ...]
    num_test_conditions: 判别测试条件数（T1,T2,...）
    next_addr_bits: 下地址字段宽度（位）
    返回完整数据流字典。
    """
    # ---- 问题1：各互斥组子字段位数 ----
    # 场景规则1：组内 n 个微命令 + 1 个无操作 = n+1 种状态 → 位数 = ceil(log2(n+1))
    subgroup_bits = []
    group_detail = []
    for gname, n in groups:
        bits = math.ceil(math.log2(n + 1))  # +1 = 无操作状态
        subgroup_bits.append(bits)
        group_detail.append({
            "组": gname,
            "微命令数n": n,
            "状态数(n+1)": n + 1,
            "子字段位数_ceil(log2(n+1))": bits,
            "错误验证_ceil(log2(n))": math.ceil(math.log2(n)),  # 常见错误：漏+1
        })

    # 场景规则2：操作控制字段总位数 = 各组位数之和
    op_control_bits = sum(subgroup_bits)

    # ---- 问题2：P字段位数 ----
    # 场景规则3：P字段位数 = ceil(log2(判别条件数+1))，+1 = 无条件转移状态
    p_field_bits = math.ceil(math.log2(num_test_conditions + 1))

    # 场景规则4：微指令字长 = 操作控制字段 + P字段 + 下地址字段
    micro_word_len = op_control_bits + p_field_bits + next_addr_bits

    # ---- 问题3：控存最大容量 ----
    # 场景规则5：控存最大容量 = 微指令字长 × 2^(下地址字段位数)
    num_addressable_units = 2 ** next_addr_bits
    control_store_capacity = micro_word_len * num_addressable_units

    # 常见错误：误用操作控制字段位数替代下地址字段位数（本题参数下恰好与正确值相同）
    error_capacity = micro_word_len * (2 ** op_control_bits)

    return {
        "PARAMS": {
            "groups": groups,
            "num_test_conditions": num_test_conditions,
            "next_addr_bits": next_addr_bits,
        },
        "PROCESS_Q1": {
            "各组子字段位数": group_detail,
            "操作控制字段总位数": op_control_bits,
        },
        "PROCESS_Q2": {
            "判别条件数": num_test_conditions,
            "状态数(条件数+1)": num_test_conditions + 1,
            "P字段位数_ceil(log2(条件数+1))": p_field_bits,
            "下地址字段位数": next_addr_bits,
            "微指令字长_操作控制+P+下地址": micro_word_len,
            "验证_各字段之和": op_control_bits + p_field_bits + next_addr_bits,
        },
        "RESULT_Q3": {
            "微指令字长": micro_word_len,
            "可寻址微指令单元数_2^(下地址位数)": num_addressable_units,
            "控存最大容量(bit)": control_store_capacity,
            "控存最大容量(Kbit)": control_store_capacity / 1024,
            "常见错误_误用操作控制位数做指数": {
                "误用指数(操作控制位数)": op_control_bits,
                "错误容量": error_capacity,
                "是否等于正确容量": error_capacity == control_store_capacity,
            },
        },
    }


# ---- 注入题干参数跑 ----
groups = [("第一组", 4), ("第二组", 3), ("第三组", 3), ("第四组", 2)]
result = solve(groups, num_test_conditions=3, next_addr_bits=9)

# ---- 底部：打印完整数据流 ----
import json
print("=" * 60)
print("PARAMS:")
print(json.dumps(result["PARAMS"], ensure_ascii=False, indent=2))
print()
print("PROCESS_Q1 (各互斥组子字段位数):")
print(json.dumps(result["PROCESS_Q1"], ensure_ascii=False, indent=2))
print()
print("PROCESS_Q2 (P字段 + 微指令字长):")
print(json.dumps(result["PROCESS_Q2"], ensure_ascii=False, indent=2))
print()
print("RESULT_Q3 (控存最大容量):")
print(json.dumps(result["RESULT_Q3"], ensure_ascii=False, indent=2))
print("=" * 60)

# ---- 场景规则反例验证：证明模型未将控存容量弱化为恒等 ----
# 用一组操作控制位数≠下地址位数的参数，确认两条路径产生不同结果
print("场景规则反例验证（操作控制位数≠下地址位数时的区分）:")
test = solve([("测试组", 7)], num_test_conditions=3, next_addr_bits=6)
print(f"  操作控制位数={math.ceil(math.log2(8))}=3, 下地址位数=6")
print(f"  正确容量(2^6=64): {test['RESULT_Q3']['控存最大容量(bit)']}")
print(f"  错误容量(2^3=8):  {test['RESULT_Q3']['常见错误_误用操作控制位数做指数']['错误容量']}")
print(f"  两者是否不同: {test['RESULT_Q3']['控存最大容量(bit)'] != test['RESULT_Q3']['常见错误_误用操作控制位数做指数']['错误容量']}")
print("=" * 60)
