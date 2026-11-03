"""Quick test: fix symbol extension for [x]补 and [-x]补 when adding to 6-bit PP"""
from fractions import Fraction

x5 = 0b01000   # [x]补 5位 = 0.1000
neg_x5 = 0b11000  # [-x]补 5位 = 1.1000
y5 = 0b10110   # [y]补 = 1.0110

# 双符号位扩展
x6 = 0b001000     # 00.1000
neg_x6 = 0b111000 # 11.1000

total_mod = 1 << 11  # PP(6) || MQ(5)
combo = (0 << 5) | y5
extra = 0

print("5趟, 前4趟加减+移位, 第5趟仅移位")
for i in range(5):
    mq = combo & 0b11111
    pp = (combo >> 5) & 0b111111
    mq_lsb = mq & 1
    judge = (mq_lsb << 1) | extra
    
    if i == 4:
        pp_new = pp
        op = "仅移位"
    elif judge == 0b01:
        pp_new = (pp + x6) & 0b111111  # 用双符号位扩展的x
        op = "+[x]补"
    elif judge == 0b10:
        pp_new = (pp + neg_x6) & 0b111111  # 用双符号位扩展的-x
        op = "+[-x]补"
    else:
        pp_new = pp
        op = "+0"
    
    combo_after = (pp_new << 5) | mq
    new_extra = combo_after & 1
    sign = (combo_after >> 10) & 1
    combo = (combo_after >> 1) | (sign << 10)
    combo &= 0b11111111111
    extra = new_extra
    
    pp_s = (combo >> 5) & 0b111111
    mq_s = combo & 0b11111
    print(f"步{i+1}: j={format(judge,'02b')}, {op}, PP加减={format(pp_new,'06b')}, 移后PP={format(pp_s,'06b')}, MQ={format(mq_s,'05b')}, ext={extra}")

pp_f = (combo >> 5) & 0b111111
mq_f = combo & 0b11111
prod10 = ((pp_f & 0b011111) << 5) | mq_f
v = prod10
if v >= 512: v -= 1024
val = Fraction(v, 512)
print(f"\nPP={format(pp_f,'06b')}, MQ={format(mq_f,'05b')}")
print(f"乘积10位={format(prod10,'010b')}, 真值={val}={float(val)}")
print(f"期望={Fraction(-5,16)}={float(Fraction(-5,16))}")
print(f"匹配={val==Fraction(-5,16)}")
