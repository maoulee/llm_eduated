"""
存储器地址线/数据线计算（选择题）
按字节编址，存储空间 32KB，存储字长 32 位。
"""
import math

# ============ 参数 ============
ADDR_UNIT_BITS = 8        # 按字节编址 → 编址单元 = 1 字节 = 8 位
STORAGE_KB = 32           # 存储空间 32KB
K_VALUE = 1024            # 正确: 1K = 1024
WORD_LEN_BITS = 32        # 存储字长 32 位

# ============ 正确计算 ============
total_bytes = STORAGE_KB * K_VALUE           # 场景规则1: 编址单元总数 = 总字节数
addr_units_correct = total_bytes              # 按字节编址 → 编址单元 = 1 字节
addr_lines_correct = int(math.log2(addr_units_correct))   # 场景规则2: 地址线 = log2(编址单元总数)
data_lines_correct = WORD_LEN_BITS           # 场景规则3: 数据线 = 存储字长位数

correct_pair = (addr_lines_correct, data_lines_correct)

# ============ 干扰项 B: 地址线/数据线互换 ============
b_addr, b_data = data_lines_correct, addr_lines_correct

# ============ 干扰项 C: K=1000 单位换算错误 ============
# 错误: 将 1K 视为 1000，则 32K = 32000 字节
# 误算者直接 int(log2(32000)) = 14（取整数部分，未意识到需取整到能覆盖的值）
total_bytes_c = STORAGE_KB * 1000            # 32000
log2_c_raw = math.log2(total_bytes_c)
c_addr = int(log2_c_raw)                      # 截断取整 → 14
c_data = data_lines_correct

# ============ 干扰项 D: 按字编址理解 ============
word_bytes = WORD_LEN_BITS // 8              # 编址单元 = 4 字节
addr_units_d = total_bytes // word_bytes     # 编址单元总数 = 总字节数 / 4
d_addr = int(math.log2(addr_units_d))
d_data = data_lines_correct

# ============ 汇总选项 ============
options = {
    "A": {"pair": correct_pair,            "desc": "正确结果"},
    "B": {"pair": (b_addr, b_data),         "desc": "地址线/数据线互换"},
    "C": {"pair": (c_addr, c_data),         "desc": "K=1000单位换算错误"},
    "D": {"pair": (d_addr, d_data),         "desc": "按字编址理解偏差"},
}

# ============ 底部打印完整数据流（检查载体） ============
print("=" * 60)
print("PARAMS:")
print(f"  编址方式: 按字节编址 (编址单元 = {ADDR_UNIT_BITS} 位 = 1 字节)")
print(f"  存储空间: {STORAGE_KB}KB")
print(f"  存储字长: {WORD_LEN_BITS} 位")
print(f"  K值(正确): {K_VALUE}")

print("\nPROCESS:")
print(f"  [正确] 总字节数 = {STORAGE_KB} × {K_VALUE} = {total_bytes}")
print(f"  [正确] 编址单元总数(按字节编址) = {addr_units_correct}")
print(f"  [正确] 地址线数 = log2({addr_units_correct}) = {addr_lines_correct}")
print(f"  [正确] 数据线数 = 存储字长 = {data_lines_correct}")
print(f"  [干扰B] 互换 → 地址线={b_addr}, 数据线={b_data}")
print(f"  [干扰C] K=1000 → 总字节数={total_bytes_c}, log2({total_bytes_c})={log2_c_raw:.4f}, 截断取整={c_addr}, 数据线={c_data}")
print(f"  [干扰D] 按字编址 → 编址单元={word_bytes}字节, 单元数={addr_units_d}, log2({addr_units_d})={d_addr}, 数据线={d_data}")

print("\nRESULT:")
for key, val in options.items():
    print(f"  {key}: 地址线={val['pair'][0]}, 数据线={val['pair'][1]}  ({val['desc']})")

print("\n" + "=" * 60)
print("RULE_CHECK (场景规则验证):")

# 规则1: 编址单元总数 == 总字节数
r1 = (addr_units_correct == total_bytes)
print(f"  规则1[编址单元总数==总字节数]: {addr_units_correct} == {total_bytes} → {r1}")

# 规则2: 地址线 = log2(编址单元总数)，须为整数
r2 = (2 ** addr_lines_correct == addr_units_correct)
print(f"  规则2[地址线=log2(编址单元总数)且为整数]: 2^{addr_lines_correct} == {addr_units_correct} → {r2}")

# 规则3: 数据线 = 存储字长
r3 = (data_lines_correct == WORD_LEN_BITS)
print(f"  规则3[数据线==存储字长]: {data_lines_correct} == {WORD_LEN_BITS} → {r3}")

# 规则4: 四选项互异
pairs = [v["pair"] for v in options.values()]
r4 = len(set(pairs)) == 4
print(f"  规则4[四选项互异]: 去重后剩 {len(set(pairs))} 个 → {'互异' if r4 else '有碰撞!'}")
print(f"    四对: A={correct_pair}, B={(b_addr,b_data)}, C={(c_addr,c_data)}, D={(d_addr,d_data)}")

# 规则6: 干扰项对应声明错误类型
r6b = (b_addr == data_lines_correct and b_data == addr_lines_correct)
r6c = (c_data == data_lines_correct and c_addr != addr_lines_correct)
r6d = (d_data == data_lines_correct and addr_units_d == total_bytes // word_bytes)
print(f"  规则6[干扰项对应错误类型]:")
print(f"    B[互换]: addr={b_addr}==原data={data_lines_correct}, data={b_data}==原addr={addr_lines_correct} → {r6b}")
print(f"    C[K=1000]: data线不变={c_data}=={data_lines_correct}, addr由32000算出={c_addr}≠正确{addr_lines_correct} → {r6c}")
print(f"    D[按字编址]: data线不变={d_data}=={data_lines_correct}, 单元数={addr_units_d}=总字节/{word_bytes} → {r6d}")

# 规则7: 干扰项合理性(非荒谬值: 地址线、数据线均为正整数且在合理范围)
all_vals = [v for p in pairs for v in p]
r7 = all(v > 0 and v < 64 for v in all_vals)
print(f"  规则7[干扰项合理性(均正整数且<64)]: {all_vals} → {r7}")

all_rules = r1 and r2 and r3 and r4 and r6b and r6c and r6d and r7
print(f"\n  >>> 全部场景规则通过: {all_rules}")
