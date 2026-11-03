"""
验证脚本：用数学方法确认 Booth 乘法的正确流程和结果
x = +0.5, y = -0.625, 5位补码小数
"""
from fractions import Fraction

# 补码表示
# [x]补 = 0.1000, [y]补 = 1.0110
# [-x]补 = 1.1000

# Booth 补码一位乘法，标准流程：
# 部分积用双符号位(6位)，乘数用5位(含符号位) + 1位附加位
# 总共做 n+1=5 次循环？还是 n=4 次？
# 标准 Booth: 对 n+1 位乘数(含符号)，做 n+1 次移位，但最后一次不移位？

# 让我用最基本的方式验证：x*y 的数学结果
x = Fraction(1, 2)
y = Fraction(-5, 8)
print(f"x*y = {x*y} = {float(x*y)}")
# 应该是 -5/16 = -0.3125

# 用Python整数模拟，PP为6位双符号位，级联MQ为5位
# 总寄存器 = 11位（PP高6 + MQ低5），附加位在MQ右侧

def booth_sim(x_comp, neg_x_comp, y_comp, n_steps, pp_bits=6, mq_bits=5):
    """模拟Booth乘法"""
    total = pp_bits + mq_bits  # 11位联合
    mod = 1 << total
    pp_mod = 1 << pp_bits
    
    # 初始
    combo = (0 << mq_bits) | y_comp  # PP=0, MQ=[y]补
    extra = 0
    
    print(f"\n=== Booth sim ({n_steps} steps) ===")
    print(f"初始: PP=00.0000, MQ={format(y_comp, '05b')}, 附加位=0")
    
    for i in range(n_steps):
        mq = combo % (1 << mq_bits)
        pp = combo >> mq_bits
        mq_lsb = mq & 1
        pair = f"{mq_lsb}{extra}"
        
        # 判断
        if pair == "01":
            pp_new = (pp + x_comp) % pp_mod
            op = "+[x]补"
        elif pair == "10":
            pp_new = (pp + neg_x_comp) % pp_mod
            op = "+[-x]补"
        else:
            pp_new = pp
            op = "+0"
        
        combo_after = (pp_new << mq_bits) | mq
        new_extra = combo_after & 1
        
        # 算术右移
        sign = (combo_after >> (total - 1)) & 1
        combo = (combo_after >> 1) | (sign << (total - 1))
        combo %= mod
        extra = new_extra
        
        pp_s = combo >> mq_bits
        mq_s = combo % (1 << mq_bits)
        print(f"  步{i+1}: pair={pair}, {op}, PP加减后={format(pp_new,'06b')}, 右移后PP={format(pp_s,'06b')}, MQ={format(mq_s,'05b')}, 附加位={extra}")
    
    pp_final = combo >> mq_bits
    mq_final = combo % (1 << mq_bits)
    print(f"最终: PP={format(pp_final,'06b')}, MQ={format(mq_final,'05b')}")
    
    # 拼接10位乘积：PP去掉最高冗余符号位(取低5位) || MQ(5位)
    prod_high = pp_final & 0b011111
    prod_low = mq_final & 0b11111
    prod10 = (prod_high << 5) | prod_low
    prod_str = format(prod10, '010b')
    
    # 解码10位补码小数
    val = prod10
    if val >= (1 << 9):
        val -= (1 << 10)
    prod_val = Fraction(val, 1 << 9)
    
    print(f"乘积10位 = {prod_str}, 真值 = {prod_val} = {float(prod_val)}")
    return prod_val

# 测试4步
print("\n--- 4 steps (standard Booth for 4-bit mantissa) ---")
r4 = booth_sim(0b01000, 0b11000, 0b10110, 4)

# 测试5步  
print("\n--- 5 steps ---")
r5 = booth_sim(0b01000, 0b11000, 0b10110, 5)

expected = x * y
print(f"\n期望: x*y = {expected} = {float(expected)}")
print(f"4步结果 == 期望: {r4 == expected}")
print(f"5步结果 == 期望: {r5 == expected}")
