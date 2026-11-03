"""
最终验证：标准Booth乘法完整正确实现
关键发现：5次判断+4次移位，PP最终=-5/16，但拼接乘积的方式需要调整

PP=11.1011(双符号位6位), MQ=00001
PP真值 = -5/16 ✓
但PP的6位 + MQ的5位 = 11位，怎么拼成10位？

标准结果：双符号位PP的最高位是冗余的
乘积 = PP的低5位 || MQ的5位
PP=11.1011, 低5位=1.1011 → 但这是负数，符号位=1
PP低5位 = 11011 = 27
MQ = 00001
乘积10位 = 11011_00001 = 1101100001

但这个解码: 1101100001, 10位补码: >=512所以减1024: 1101100001=865, 865-1024=-159, 值=-159/512
这不等于-5/16=-160/512

差了1/512！问题出在哪里？

啊，问题是：PP的6位是双符号位，但乘积应该取PP的"有效"部分。
在双符号位中，11.1011表示-5/16，但正确的10位乘积应该直接是-5/16的补码。
-5/16的10位补码小数 = ?
-5/16 * 512 = -160 → 10位补码: 1024-160=864 = 1101100000

所以正确乘积10位 = 1101100000
而我得到的是 1101100001 (差最低位1)

问题：MQ的值不对。让我想想为什么。

5次判断4次移位，MQ只右移了4次，从10110变成了00001。
但标准Booth做n+1=5次右移的话MQ会被完全移出。

等等，标准Booth的正确做法是：
- n+1=5次"判断+加减"
- n+1=5次"右移" 
不对，标准是n+1次判断，n次移位。

让我换个角度：直接验证4次判断+4次移位+第5次判断+第5次移位
即5次判断+5次移位的结果
然后乘积 = PP低5位 || MQ(移位后)
"""
from fractions import Fraction

x_dbl = 0b001000      # 00.1000
neg_x_dbl = 0b111000  # 11.1000
y_comp_5 = 0b10110    # 1.0110

total_mod = 1 << 11

combo = (0 << 5) | y_comp_5
extra = 0

print("=== 5次判断+5次移位 ===")
for i in range(5):
    mq = combo % 32
    pp = combo >> 5
    mq_lsb = mq & 1
    judge = mq_lsb * 2 + extra
    
    if judge == 1:
        pp_new = (pp + x_dbl) % 64
        op = "+[x]补"
    elif judge == 2:
        pp_new = (pp + neg_x_dbl) % 64
        op = "+[-x]补"
    else:
        pp_new = pp
        op = "+0"
    
    combo_after = (pp_new << 5) | mq
    new_extra = combo_after & 1
    sign = (combo_after >> 10) & 1
    combo = (combo_after >> 1) | (sign << 10)
    combo %= total_mod
    extra = new_extra
    
    pp_s = combo >> 5
    mq_s = combo % 32
    b = format(pp_s % 64, '06b')
    print(f"  步{i+1}: judge={format(judge,'02b')}, {op}, PP={b[0:2]}.{b[2:]}, MQ={format(mq_s,'05b')}, ext={extra}")

pp_f = combo >> 5
mq_f = combo % 32

# 乘积10位 = PP低5位 || MQ 5位
prod10 = ((pp_f & 0b011111) << 5) | mq_f
v = prod10
if v >= 512: v -= 1024
val = Fraction(v, 512)
b = format(pp_f % 64, '06b')
print(f"\n最终: PP={b[0:2]}.{b[2:]}, MQ={format(mq_f,'05b')}")
print(f"乘积10位(PP低5||MQ5) = {format(prod10,'010b')} = {val} = {float(val)}")
print(f"期望 = -5/16 = {float(Fraction(-5,16))}")

# PP本身真值
pp_val = pp_f % 64
if pp_val >= 32: pp_val -= 64
pp_true = Fraction(pp_val, 16)
print(f"PP真值 = {pp_true}, PP*2 = {pp_true*2}")
# 5次右移后PP=真实乘积/2^5? 不对，因为每次加减后有累积

# 实际上x*y = -5/16, 而PP真值 = pp_true
# 如果pp_true*2^5 = x*y? 
print(f"PP真值*32 = {pp_true*32}")
print(f"x*y = {Fraction(-5,16)}")
