"""
Key realization: Maybe the issue is how we handle the 5th step.

The problem says "4位数值位对应4趟加减+移位，第5趟仅移位".
This means: for n=4 mantissa bits, do 4 iterations of (judge+add+shift),
then a 5th iteration of (shift only, no add).

But mathematically, for y=[y]补=10110, the 5th judgment pair is (1,0)=10 which REQUIRES +[-x]补.
So with these specific parameters, the 5th step can't be "shift only".

HOWEVER - re-reading the problem: the problem defines 5 趟 with the 5th being shift-only.
This is a DESIGN CHOICE by the problem author. The question is: does it produce the right answer?

From test_all.py: 
- 5 steps, shift_all=True (5th also shifts), dbl_sign=True:
  PP=111101, MQ=10000, product(PP_low5||MQ5)=1110110000 = -5/32 ≠ -5/16

- 5 steps, shift_all=False (5th no shift), dbl_sign=True:
  PP=111011, product = -5/16 but via PP-as-product, not PP||MQ

The correct standard Booth for n+1=5 bits does n+1=5 iterations with n+1 shifts.
After 5 shifts, PP has been right-shifted 5 times total.
The product = PP(6 bits) || MQ(5 bits) = 11 bits, take low 10 bits.

Let me check: 5 shifts, dbl_sign, product = combo & 0x3FF (low 10 of 11)
"""
from fractions import Fraction

x5 = 0b01000
neg_x5 = 0b11000
y5 = 0b10110
x6 = 0b001000
neg_x6 = 0b111000

total_mod = 1 << 11

# 5 iterations, ALL shift, double-sign
combo = (0 << 5) | y5
extra = 0
for i in range(5):
    mq = combo & 0b11111
    pp = (combo >> 5) & 0b111111
    mq_lsb = mq & 1
    judge = (mq_lsb << 1) | extra
    
    if judge == 0b01:
        pp_new = (pp + x6) & 0b111111
        op = "+[x]补"
    elif judge == 0b10:
        pp_new = (pp + neg_x6) & 0b111111
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
    print(f"步{i+1}: j={format(judge,'02b')}, {op}, PP={format(pp_new,'06b')}→{format(pp_s,'06b')}, MQ={format(mq_s,'05b')}, ext={extra}")

print(f"\nFinal combo(11位) = {format(combo, '011b')}")
# Method 1: combo low 10 bits
p_low10 = combo & 0b01111111111
v1 = p_low10
if v1 >= 512: v1 -= 1024
print(f"combo低10位 = {format(p_low10,'010b')} = {Fraction(v1,512)}")

# Method 2: PP(6) || MQ(5), take PP low5 || MQ5 
pp_f = (combo >> 5) & 0b111111
mq_f = combo & 0b11111
p2 = ((pp_f & 0b011111) << 5) | mq_f
v2 = p2
if v2 >= 512: v2 -= 1024
print(f"PP低5||MQ5 = {format(p2,'010b')} = {Fraction(v2,512)}")

# Method 3: just PP low 5 bits (ignore MQ, PP IS the product after all shifts)
# But PP is 6 bits double-sign, the actual n+1=5 bit value
# PP = 111101, as 6-bit double sign, low 5 bits = 11101, value = -(32-29)/16 = -3/16
ppv5 = pp_f & 0b011111
if ppv5 >= 16: ppv5 -= 32
print(f"PP低5位解码 = {Fraction(ppv5, 16)}")

# Method 4: After n+1 shifts, PP holds upper n+1 bits, MQ holds lower n+1 bits
# Product(10 bits) = PP(5 bits, low of double sign) || MQ(5 bits) 
# BUT this is what method 2 is. And it gives -5/32.

# The answer -5/32 is x*y/2. This means one extra shift happened.
# Standard Booth: n iterations for n mantissa bits, NOT n+1!

print("\n\n=== TRY: 4 iterations (n=4 mantissa bits), all shift ===")
combo = (0 << 5) | y5
extra = 0
for i in range(4):
    mq = combo & 0b11111
    pp = (combo >> 5) & 0b111111
    mq_lsb = mq & 1
    judge = (mq_lsb << 1) | extra
    
    if judge == 0b01:
        pp_new = (pp + x6) & 0b111111
        op = "+[x]补"
    elif judge == 0b10:
        pp_new = (pp + neg_x6) & 0b111111
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
    print(f"步{i+1}: j={format(judge,'02b')}, {op}, PP={format(pp_new,'06b')}→{format(pp_s,'06b')}, MQ={format(mq_s,'05b')}, ext={extra}")

pp_f = (combo >> 5) & 0b111111
mq_f = combo & 0b11111
# Method: PP low5 || MQ 5
p = ((pp_f & 0b011111) << 5) | mq_f
v = p
if v >= 512: v -= 1024
print(f"4步 PP低5||MQ5 = {format(p,'010b')} = {Fraction(v,512)} = {float(Fraction(v,512))}")

# Also: PP low5 shifted left by 4 || MQ high4 (since 4 shifts, MQ has 4 valid low bits)
p_b = (pp_f << 4) | ((mq_f >> 1) & 0b1111)
p_b &= 0b1111111111
v2 = p_b
if v2 >= 512: v2 -= 1024
print(f"4步 PP6||MQ高4 = {format(p_b,'010b')} = {Fraction(v2,512)} = {float(Fraction(v2,512))}")

# The correct answer is -5/16 = -160/512 = -0.3125
# -160 in 10-bit two's complement = 1024-160 = 864 = 1101100000
print(f"\n期望: -5/16 = {format(864, '010b')}")
