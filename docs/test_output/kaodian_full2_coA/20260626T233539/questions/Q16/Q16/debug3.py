from fractions import Fraction

def booth_decode(val, nbits):
    val = val % (1 << nbits)
    if val >= (1 << (nbits - 1)):
        val -= (1 << nbits)
    return Fraction(val, 1 << (nbits - 1))

# -5/16 in various precisions
for nb in range(6, 12):
    intval = int(Fraction(-5,16) * (1 << (nb-1))) % (1 << nb)
    decoded = booth_decode(intval, nb)
    print(f"-5/16 in {nb}-bit: {format(intval, '0{}b'.format(nb))} = {intval}, decode={decoded}")

# The fundamental issue: 
# In Booth multiplication for FRACTIONAL numbers,
# the multiplier y = 1.0110 = -5/8, multiplicand x = 0.1000 = +1/2
# Product = -5/16

# In integer Booth (same bits as unsigned integers):
# x_int = 8, y_int = 22, product = 176
# 176 in 10 bits = 0010110000
# But these are COMPLEMENT integers, so:
# x = +8 (positive), y = 22-32 = -10 (5-bit complement)
# product = 8 * (-10) = -80
# -80 in 10 bits = 10110000 * ... wait
# -80 mod 1024 = 944 = 1110110000
print(f"\nx_int*y_int (complement) = {8 * (-10)} = -80")
print(f"-80 in 10-bit = {format(-80 % 1024, '010b')} = {booth_decode(-80%1024, 10)}")
# 1110110000 = -80/512 = -5/32. WRONG for fractions.

# For FRACTIONAL: x=0.1000=+0.5, y=1.0110=-0.625
# product = -0.3125 = -5/16
# -5/16 in 10-bit fraction = -5/16 * 2^9 = -160 → mod 1024 = 864 = 1101100000
print(f"\nCorrect 10-bit: 1101100000 = {booth_decode(864, 10)}")

# The Booth algorithm produces the product PP||MQ where PP and MQ are the 
# register contents after all iterations. The ISSUE is interpretation.
# 
# In fractional Booth: after n iterations (n=5 for 5-bit multiplier),
# PP||MQ = 11 bits. But the RESULT is only the lower 10 bits of a 2n-bit product.
# Actually wait, PP has 6 bits (double sign) + MQ has 5 bits = 11 bits.
# The product = PP_low5 || MQ = 10 bits.
#
# BUT: 1110110000 = -5/32 ≠ -5/16
#
# The issue must be that we need n iterations for n-bit multiplier,
# and the result IS PP(6)||MQ(5)=11 bits, and we should decode as 11 bits!
# Let's try:
prod11 = 0b11110110000  # PP(6)||MQ(5)
print(f"\nPP||MQ as 11-bit: {format(prod11,'011b')} = {booth_decode(prod11, 11)}")
# -5/16 in 11 bits: -5/16 * 2^10 = -320 → mod 2048 = 1728 = 11011000000
print(f"-5/16 in 11-bit: {format(-5*64 % 2048, '011b')} = {booth_decode(-5*64%2048,11)}")

# Hmm, prod11 = 11110110000 decodes to -80/1024 = -5/64. Still wrong.
# The correct 11-bit for -5/16 = 11011000000

# OK let me think differently. In INTEGER Booth multiplication:
# multiplier has n bits. We do n iterations. Result has 2n bits = PP(n)||MQ(n)
# For 5-bit multiplier: 5 iterations, result = 10 bits = PP_low5||MQ5
# 
# In FRACTIONAL Booth, the multiplication is the SAME, but the 
# binary point is at position n from the right.
# Integer product of x=8, y=-10 (complement) = -80
# -80 in 10 bits = 10110000... = 
# -80 + 256 = 176? No, 10-bit: -80 mod 1024 = 944 = 1110110000
# But 1110110000 as fraction (binary point after 5 bits from MSB): 
# = -80/2^5 = -80/32 = -5/2 ← that's also wrong
# 
# Wait. If x and y are 5-bit fractionals:
# x = 0.1000 = 8/16 = 1/2, y = 1.0110 = -10/16 = -5/8
# As integers they represent: x_int = 8 (meaning 8*2^(-4)), y_int = -10 (meaning -10*2^(-4))
# Product = (8 * 2^(-4)) * (-10 * 2^(-4)) = -80 * 2^(-8) = -80/256 = -5/16
# 
# The INTEGER product is 8 * (-10) = -80
# -80 in 10-bit complement = 1110110000 (= 944 unsigned)
# As a FRACTIONAL result with 10 bits and binary point after bit 5:
# 11101.10000 → complement decode
# 11101 = -(32-29) = -3... hmm

# Actually the fractional result: 10 bits, binary point between bit 5 and bit 4
# = upper 5 bits . lower 5 bits
# 11101.10000
# integer value = 944 - 1024 = -80 (10-bit signed)
# as fraction = -80 / 2^5 = -80/32 = -5/2. WRONG.

# No wait. The product of two (1+4)-bit fractions is a (2+8)=10-bit fraction.
# Binary point is between bit 9 and bit 8 (MSB position).
# 1110110000 as 10-bit complement fraction = 
# -(2^9) + remaining bits
# 944 - 1024 = -80
# fraction = -80 / 2^9 = -80/512 = -5/32

# So Booth gives -5/32 for integer computation of 8 * (-10) = -80.
# But x*y = 1/2 * (-5/8) = -5/16.
# 
# -5/16 = -80/256 = -80 * 2^(-8)
# Integer product = -80 = 8 * (-10)
# But Booth registers after 5 shifts has divided by 2^5 = 32
# So the register holds -80/32 = -5/2? No...
# 
# Actually I think the issue is simpler. Let me reconsider.
# In Booth, PP starts at 0. Each step adds x or -x (the FULL value, not shifted),
# then shifts RIGHT. After n steps, the accumulated partial products have been
# shifted right n times total. The product = PP||MQ.
#
# For integer multiplication of n-bit × n-bit:
# After n steps, PP(n-bit)||MQ(n-bit) = 2n-bit product. ✓
# For x=8, y=-10: after 5 steps, result = 1110110000 = -80 (as 10-bit signed). ✓
#
# For FRACTIONAL: x = 8 (represents 1/2), y = -10 (represents -5/8)
# The Booth hardware treats them as integers, gives -80.
# But -80 as a 10-bit SIGNED FRACTION (1 sign + 9 mantissa) = -80/2^9 = -5/32
# This is WRONG. The actual product is -5/16.
#
# THE REAL ISSUE: In fractional Booth, the result PP||MQ has 
# 2 sign bits worth of extra scaling. The correct reading is:
# PP(6)||MQ(5) = 11 bits. Drop one redundant sign bit → 10 bits.
# 10-bit = 1110110000 → -80/512 = -5/32 ← STILL WRONG

# Let me just try: what if we DON'T shift on the last iteration?
print("\n=== 5 iterations, last one: add but NO shift ===")
x6 = 8   # 00.1000
nx6 = 56 # 11.1000
y5 = 22  # 1.0110

COMBO = y5  # PP=0, so just MQ
EXTRA = 0
PP_BITS=6; MQ_BITS=5; COMBO_BITS=11

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
    
    if step < 4:  # shift on first 4
        sign = (combo_after >> 10) & 1
        combo_shifted = (combo_after >> 1) | (sign << 10)
        new_extra = combo_after & 1
    else:  # no shift on last
        combo_shifted = combo_after
        new_extra = EXTRA  # unchanged
    
    COMBO = combo_shifted
    EXTRA = new_extra
    pp_sh = (COMBO >> MQ_BITS) % 64
    mq_sh = COMBO % 32
    print(f"Step{step+1}: pair={pair} op={op} → PP={format(pp_sh,'06b')} MQ={format(mq_sh,'05b')}")

pp_final = (COMBO >> MQ_BITS) % 64
mq_final = COMBO % 32
print(f"\nFinal: PP={format(pp_final,'06b')} MQ={format(mq_final,'05b')}")
print(f"PP as 6-bit = {booth_decode(pp_final, 6)}")
# The product for fractions is PP (6-bit, double sign) decoded as 5-bit
print(f"PP low 5 as fraction = {booth_decode(pp_final & 0b11111, 5)}")
# Full 11-bit
prod11 = (pp_final << 5) | mq_final
print(f"11-bit: {format(prod11,'011b')} = {booth_decode(prod11, 11)}")
