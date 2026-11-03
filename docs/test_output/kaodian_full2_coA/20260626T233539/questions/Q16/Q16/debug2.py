from fractions import Fraction

def booth_decode(val, nbits):
    val = val % (1 << nbits)
    if val >= (1 << (nbits - 1)):
        val -= (1 << nbits)
    return Fraction(val, 1 << (nbits - 1))

# What is -5/16 in 10-bit complement?
# -5/16 = -5 * 2^8 / 2^9 = ... 
# 10-bit complement fraction: value = integer / 2^9
# -5/16 = -5/16, so integer = -5/16 * 2^9 = -5/16 * 512 = -160
# -160 mod 1024 = 864 = 1101100000
val10 = 864
print(f"-5/16 as 10-bit: {bin(val10)} = {val10}")
print(f"decode: {booth_decode(val10, 10)}")
print(f"expected: {Fraction(-5,16)}")
print()

# So correct 10-bit product should be 1101100000
# Now let's trace Booth carefully
# Standard Booth for n-bit multiplier (n=5 including sign): n iterations of (add+shift)
# After n iterations, product = PP_low(5) || MQ(5) = 10 bits

# But wait - in standard Booth, we iterate n times for n-bit multiplier
# For a 5-bit multiplier fraction (1 sign + 4 magnitude), 
# we look at pairs (y0,y-1), (y1,y0), (y2,y1), (y3,y2), (y4,y3) = 5 pairs
# That's 5 iterations, each: add/sub based on pair, then shift
# After 5 iterations: PP has 6 bits (double sign), MQ has 5 bits
# Product = PP(6) with double sign, or PP_low5 || MQ = 10 bits

# Let me trace with proper add-then-shift for all 5 steps:
x_true = Fraction(1,2)
y_true = Fraction(-5,8)

# [x]5 = 0.1000 = 8, [-x]5 = 1.1000 = 24
# [y]5 = 1.0110 = 22
x5 = 8
nx5 = 24
y5 = 22

# Double-sign versions (6 bit): 00.1000=8, 11.1000=56
x6 = 8
nx6 = 56

PP_BITS = 6
MQ_BITS = 5
COMBO_BITS = 11

PP = 0  # 00.0000
COMBO = (PP << MQ_BITS) | y5  # 000000_10110
EXTRA = 0

# y bits from LSB: y0=0, y1=1, y2=1, y3=0, y4=1
# pairs: (y0,0)=00, (y1,y0)=10, (y2,y1)=11, (y3,y2)=01, (y4,y3)=10

for step in range(5):
    pp = (COMBO >> MQ_BITS) % 64
    mq = COMBO % 32
    pair = f"{mq & 1}{EXTRA}"
    
    if pair == "01":
        pp_new = (pp + x6) % 64
        op = "+[x]"
    elif pair == "10":
        pp_new = (pp + nx6) % 64
        op = "+[-x]"
    else:
        pp_new = pp
        op = "+0"
    
    combo_after = (pp_new << MQ_BITS) | mq
    sign = (combo_after >> 10) & 1
    combo_shifted = (combo_after >> 1) | (sign << 10)
    new_extra = combo_after & 1
    
    pp_sh = (combo_shifted >> MQ_BITS) % 64
    mq_sh = combo_shifted % 32
    
    pp_str = format(pp_new, '06b')
    pp_sh_str = format(pp_sh, '06b')
    mq_str = format(mq, '05b')
    mq_sh_str = format(mq_sh, '05b')
    
    print(f"Step{step+1}: pair={pair} op={op} PP_after={pp_str[0:2]}.{pp_str[2:]} → PP_sh={pp_sh_str[0:2]}.{pp_sh_str[2:]} MQ={mq_sh_str} ext={new_extra}")
    
    COMBO = combo_shifted
    EXTRA = new_extra

pp_final = (COMBO >> MQ_BITS) % 64
mq_final = COMBO % 32

# 10-bit product = PP_low5 || MQ5
ph = pp_final & 0b011111  # low 5 bits of PP
pl = mq_final & 0b11111
prod10 = (ph << 5) | pl
print(f"\nFinal PP={format(pp_final,'06b')}, MQ={format(mq_final,'05b')}")
print(f"PP_low5||MQ = {format(prod10,'010b')} = {booth_decode(prod10,10)}")
print(f"Expected: {x_true * y_true}")

# The issue: 5 iterations with add+shift gives -5/32, not -5/16
# Let me try 4 iterations add+shift + 1 final shift without add
print("\n=== 4 iterations + final shift-only ===")
PP = 0
COMBO = (PP << MQ_BITS) | y5
EXTRA = 0

for step in range(5):
    pp = (COMBO >> MQ_BITS) % 64
    mq = COMBO % 32
    pair = f"{mq & 1}{EXTRA}"
    
    if step == 4:
        pp_new = pp  # no add on last step
        op = "+0 (shift only)"
    elif pair == "01":
        pp_new = (pp + x6) % 64
        op = "+[x]"
    elif pair == "10":
        pp_new = (pp + nx6) % 64
        op = "+[-x]"
    else:
        pp_new = pp
        op = "+0"
    
    combo_after = (pp_new << MQ_BITS) | mq
    sign = (combo_after >> 10) & 1
    combo_shifted = (combo_after >> 1) | (sign << 10)
    new_extra = combo_after & 1
    
    pp_sh = (combo_shifted >> MQ_BITS) % 64
    mq_sh = combo_shifted % 32
    print(f"Step{step+1}: pair={pair} op={op} → PP_sh={format(pp_sh,'06b')} MQ={format(mq_sh,'05b')}")
    
    COMBO = combo_shifted
    EXTRA = new_extra

pp_final = (COMBO >> MQ_BITS) % 64
mq_final = COMBO % 32
ph = pp_final & 0b011111
pl = mq_final & 0b11111
prod10 = (ph << 5) | pl
print(f"PP_low5||MQ = {format(prod10,'010b')} = {booth_decode(prod10,10)}")

# Try: 4 iterations add+shift, NO final shift, product = PP only
print("\n=== 4 iterations only, product = PP_final ===")
PP = 0
COMBO = (PP << MQ_BITS) | y5
EXTRA = 0

for step in range(4):
    pp = (COMBO >> MQ_BITS) % 64
    mq = COMBO % 32
    pair = f"{mq & 1}{EXTRA}"
    
    if pair == "01":
        pp_new = (pp + x6) % 64
    elif pair == "10":
        pp_new = (pp + nx6) % 64
    else:
        pp_new = pp
    
    combo_after = (pp_new << MQ_BITS) | mq
    sign = (combo_after >> 10) & 1
    combo_shifted = (combo_after >> 1) | (sign << 10)
    new_extra = combo_after & 1
    
    COMBO = combo_shifted
    EXTRA = new_extra

pp_final = (COMBO >> MQ_BITS) % 64
mq_final = COMBO % 32
print(f"Final PP={format(pp_final,'06b')}, MQ={format(mq_final,'05b')}")
print(f"PP as 6-bit value = {booth_decode(pp_final, 6)}")
# -5/16 in 6-bit = 11.1011 = ?
# value = -5/16 → integer = -5/16 * 2^5 = -10 → mod 64 = 54 = 110110 = 11.0110? 
# No: 11.1011 = -(1/4 - 1/8 - 1/16) = -(4/16-2/16-1/16)=... 
# 11.1011 = value where 6-bit: sign at bit5
# 111011 → -(2^5) + (2^4+2^3+2^1+2^0) = -32+16+8+2+1=-5 → /2^5 = -5/32. No that's 6-bit decode.
print(f"PP(6-bit decoded) = {booth_decode(pp_final,6)}")
print(f"PP(5-bit, low5) = {booth_decode(pp_final & 0b011111, 5)}")
