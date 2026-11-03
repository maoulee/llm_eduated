"""
诊断脚本：Booth乘法 - 检查符号位拼接和乘积解码方式
x = +0.5 = [x]补 0.1000, y = -0.625 = [y]补 1.0110
x*y = -5/16 = -0.3125

问题可能：
1. 乘积10位的拼接方式（PP取几位？MQ取几位？）
2. 部分积是否应该也参与符号
3. Booth判断位顺序是否反了（应该是 附加位-最低位 还是 最低位-附加位）
"""
from fractions import Fraction

x_comp = 0b01000   # 0.1000
neg_x_comp = 0b11000  # 1.1000  
y_comp = 0b10110   # 1.0110

pp_bits = 6
mq_bits = 5
total = 11
mod = 1 << total
pp_mod = 1 << pp_bits

def run_booth(do_shift5=False):
    combo = (0 << mq_bits) | y_comp
    extra = 0
    
    steps = 4 if not do_shift5 else 5
    for i in range(steps):
        mq = combo % (1 << mq_bits)
        pp = combo >> mq_bits
        mq_lsb = mq & 1
        
        # Booth判断位 = (乘数最低位, 附加位)
        pair_high = mq_lsb   # 乘数最低位
        pair_low = extra      # 附加位
        
        # 标准Booth: 看 附加位-最低位 的变化
        # 00或11: +0; 01(低位1高位0): +x; 10(低位0高位1): -x
        # 但这里pair = f"{mq_lsb}{extra}" = 高位mq_lsb, 低位extra
        # 标准: 01→+x 的意思是 低位=1,高位=0 即 extra=1,mq_lsb=0
        # 标准: 10→-x 的意思是 低位=0,高位=1 即 extra=0,mq_lsb=1
        
        # 让我们用标准定义: 判断位 = (mq_lsb, extra) 作为两位数
        judge = mq_lsb * 2 + extra  # 高位mq_lsb, 低位extra
        # 标准: judge=1(01): +x; judge=2(10): -x; 0或3: +0
        # 这对应: 01(+x), 10(-x)
        # 但课本上Booth判断是从低位往高位看: extra在低位, mq_lsb在高位
        # pair = mq_lsb,extra => 01 means mq_lsb=0,extra=1 => 低位变化0→1 => +x
        # 10 means mq_lsb=1,extra=0 => 1→0 => -x
        
        if judge == 1:   # 01
            pp_new = (pp + x_comp) % pp_mod
            op = "+[x]补"
        elif judge == 2:  # 10
            pp_new = (pp + neg_x_comp) % pp_mod
            op = "+[-x]补"
        else:
            pp_new = pp
            op = "+0"
        
        combo_after = (pp_new << mq_bits) | mq
        new_extra = combo_after & 1
        
        sign = (combo_after >> (total - 1)) & 1
        combo = (combo_after >> 1) | (sign << (total - 1))
        combo %= mod
        extra = new_extra
    
    pp_final = combo >> mq_bits
    mq_final = combo % (1 << mq_bits)
    
    # 方式A: PP低5位 + MQ低5位 = 10位
    prod_a = ((pp_final & 0b011111) << 5) | mq_final
    # 方式B: PP全部6位 + MQ低4位 = 10位 (去掉MQ最低位/附加位区域)
    prod_b = (pp_final << 4) | ((mq_final >> 1) & 0b1111)
    # 方式C: PP低5位 + MQ全部5位，但理解为10位补码（PP最高符号位=乘积符号）
    # 乘积符号应该来自PP
    
    return pp_final, mq_final, prod_a, prod_b

def decode10(val):
    v = val % (1<<10)
    if v >= (1<<9):
        v -= (1<<10)
    return Fraction(v, 1<<9)

pp4, mq4, pa4, pb4 = run_booth(do_shift5=False)
print(f"4步: PP={format(pp4,'06b')}, MQ={format(mq4,'05b')}")
print(f"  方式A(PP低5||MQ5): {format(pa4,'010b')} => {decode10(pa4)} = {float(decode10(pa4))}")
print(f"  方式B(PP6||MQ高4): {format(pb4,'010b')} => {decode10(pb4)} = {float(decode10(pb4))}")

pp5, mq5, pa5, pb5 = run_booth(do_shift5=True)
print(f"5步: PP={format(pp5,'06b')}, MQ={format(mq5,'05b')}")
print(f"  方式A(PP低5||MQ5): {format(pa5,'010b')} => {decode10(pa5)} = {float(decode10(pa5))}")
print(f"  方式B(PP6||MQ高4): {format(pb5,'010b')} => {decode10(pb5)} = {float(decode10(pb5))}")

# 期望
print(f"\n期望 x*y = -5/16 = {float(Fraction(-5,16))}")

# 手工验算 Booth 过程的正确性
# 用精确分数追踪
print("\n=== 精确分数追踪 4步 ===")
pp_val = Fraction(0)  # 部分积真值
# MQ 初始 = [y]补 = 1.0110 = -5/8, 附加位=0
# 但Booth中MQ的值只是移位用的位串，不直接参与算术
# 用位级跟踪更清楚

# 标准教材流程（手算）：
# PP=00.0000, MQ=1.0110, 附加位=0
# 第1步: 判断 00, +0, PP=00.0000, 右移→PP=00.0000, MQ=0.1011, 附加位=0
# 第2步: 判断 10, +[-x]补=11.1000, PP=00.0000+11.1000=11.1000(双符号), 右移→PP=11.1100, MQ=0.0101, 附加位=1
#   等等，00.0000 + 11.1000 = 11.1000? 双符号位加法
#   PP=000000(00.0000) + 110000(11.1000) = 110000 = 11.1000
#   右移(算术,符号位11扩展): 111000 = 11.1000... 不对

# 问题可能在于：PP=00.0000 加 [-x]补=11.1000
# [-x]补应该是5位: 1.1000，但PP是6位双符号位，所以[-x]补也要扩展为双符号位: 11.1000
print("\n[-x]补 5位 = 1.1000, 双符号位扩展 = 11.1000")
neg_x_double = 0b111000  # 11.1000
print(f"  = {format(neg_x_double, '06b')}")

# 重跑：PP用双符号位，[-x]补扩展为双符号位
combo = (0 << mq_bits) | y_comp
extra = 0
# neg_x 双符号位
neg_x_dbl = 0b111000   # 1.1000 -> 11.1000
x_dbl = 0b001000       # 0.1000 -> 00.1000

print("\n=== 修正: [x]补和[-x]补用双符号位 ===")
for i in range(4):
    mq = combo % (1 << mq_bits)
    pp = combo >> mq_bits
    mq_lsb = mq & 1
    judge = mq_lsb * 2 + extra
    
    if judge == 1:
        pp_new = (pp + x_dbl) % pp_mod
        op = "+[x]补(00.1000)"
    elif judge == 2:
        pp_new = (pp + neg_x_dbl) % pp_mod
        op = "+[-x]补(11.1000)"
    else:
        pp_new = pp
        op = "+0"
    
    combo_after = (pp_new << mq_bits) | mq
    new_extra = combo_after & 1
    sign = (combo_after >> (total - 1)) & 1
    combo = (combo_after >> 1) | (sign << (total - 1))
    combo %= mod
    extra = new_extra
    
    pp_s = combo >> mq_bits
    mq_s = combo % (1 << mq_bits)
    print(f"  步{i+1}: judge={format(judge,'02b')}, {op}, PP加减后={format(pp_new,'06b')}, 右移PP={format(pp_s,'06b')}, MQ={format(mq_s,'05b')}, 附加位={extra}")

pp_f = combo >> mq_bits
mq_f = combo % (1 << mq_bits)
print(f"最终: PP={format(pp_f,'06b')}, MQ={format(mq_f,'05b')}")
prod = ((pp_f & 0b011111) << 5) | mq_f
print(f"乘积10位(方式A) = {format(prod,'010b')} => {decode10(prod)} = {float(decode10(prod))}")
