# -*- coding: utf-8 -*-
"""
变址寻址有效地址计算 —— 单选题建模
忠实实现题干场景规则，assert 通过条件，底部 print 完整数据流。
"""

def compute_all_options(R1, PC, A, ADDR_BITS=16):
    """计算各选项的正确值与干扰项产物。"""
    addr_max = (1 << ADDR_BITS) - 1  # 64KB = 0xFFFF

    # 场景规则1：变址寻址定义成立 —— EA = R1 + A（加法）
    EA_indexed = (R1 + A) & addr_max       # 正确：变址寻址

    # 干扰项各路径
    EA_direct = A & addr_max                 # B：直接寻址混淆，EA = A
    EA_relative = (PC + A) & addr_max        # C：相对寻址混淆，EA = PC + A
    EA_subtract = (R1 - A) & addr_max        # D：运算方向错误，EA = R1 − A

    return {
        "addr_max": addr_max,
        "EA_indexed": EA_indexed,
        "EA_direct": EA_direct,
        "EA_relative": EA_relative,
        "EA_subtract": EA_subtract,
    }


# ============ 注入题干参数 ============
R1 = 0x8000
PC = 0x2004
A  = 0x003C

res = compute_all_options(R1, PC, A)
addr_max  = res["addr_max"]
EA_A      = res["EA_indexed"]    # 正确
EA_B      = res["EA_direct"]     # 干扰
EA_C      = res["EA_relative"]   # 干扰
EA_D      = res["EA_subtract"]   # 干扰

# ============ assert 场景规则（通过条件）============
# 规则1：变址寻址定义成立 —— EA == R1 + A（加法）
assert EA_A == (R1 + A) & addr_max, "变址寻址定义：EA 必须等于 R1+A"

# 规则2：四选项互异
four = [EA_A, EA_B, EA_C, EA_D]
assert len(set(four)) == 4, f"四选项不互异: {[hex(v) for v in four]}"

# 规则3：正确值唯一确定（变址寻址定义无歧义）
# —— 本规则为定义层面保证，EA_indexed 由加法唯一确定，无需额外 assert

# 规则4：各干扰项与正确项不同
assert EA_B != EA_A, "直接寻址 EA != 变址 EA"
assert EA_C != EA_A, "相对寻址 EA != 变址 EA"
assert EA_D != EA_A, "方向错误 EA != 变址 EA"

# 规则5：各干扰项之间互异（A、PC+A、R1−A 两两不同）
distractors = [EA_B, EA_C, EA_D]
assert len(set(distractors)) == 3, f"干扰项互异失败: {[hex(v) for v in distractors]}"

# ============ 底部：打印完整数据流 ============
print("=" * 60)
print("PARAMS:")
print(f"  R1  (变址寄存器) = {hex(R1)}")
print(f"  PC  (程序计数器) = {hex(PC)}")
print(f"  A   (形式地址)   = {hex(A)}")
print(f"  地址空间上限       = {hex(addr_max)}  (64KB, {16}位)")
print()

print("PROCESS / 各选项计算路径:")
print(f"  [A 正确] 变址寻址: EA = R1 + A = {hex(R1)} + {hex(A)} = {hex(EA_A)}")
print(f"  [B 干扰] 直接寻址: EA = A      = {hex(EA_B)}")
print(f"  [C 干扰] 相对寻址: EA = PC + A = {hex(PC)} + {hex(A)} = {hex(EA_C)}")
print(f"  [D 干扰] 方向错误: EA = R1 - A = {hex(R1)} - {hex(A)} = {hex(EA_D)}")
print()

print("RESULT:")
print(f"  正确答案 = A: {hex(EA_A)}")
print()

print("RULE_CHECK (场景规则验证):")
print(f"  规则1 变址定义 EA==R1+A : {EA_A == (R1 + A) & addr_max}")
print(f"  规则2 四选项互异          : {len(set(four)) == 4}  -> {[hex(v) for v in four]}")
print(f"  规则3 正确值唯一(加法确定) : True")
print(f"  规则4 干扰项!=正确项       : B!=A:{EA_B!=EA_A}, C!=A:{EA_C!=EA_A}, D!=A:{EA_D!=EA_A}")
print(f"  规则5 干扰项互异           : {len(set(distractors))==3}  -> {[hex(v) for v in distractors]}")
print()

print("OPTION_A:", {"正确值": hex(EA_A), "实际值": hex(EA_A), "改错方式": "无（正确选项）"})
print("OPTION_B:", {"正确值": hex(EA_A), "实际值": hex(EA_B), "改错方式": "直接寻址混淆：误取 EA=A"})
print("OPTION_C:", {"正确值": hex(EA_A), "实际值": hex(EA_C), "改错方式": "相对寻址混淆：误取 EA=PC+A"})
print("OPTION_D:", {"正确值": hex(EA_A), "实际值": hex(EA_D), "改错方式": "运算方向错误：误取 EA=R1-A"})
print("=" * 60)
print("ALL ASSERTS PASSED ✓")
