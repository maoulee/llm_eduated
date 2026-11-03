from fractions import Fraction

def booth_decode(val, nbits):
    val = val % (1 << nbits)
    if val >= (1 << (nbits - 1)):
        val -= (1 << nbits)
    return Fraction(val, 1 << (nbits - 1))

# Correct answer: x*y = 1/2 * (-5/8) = -5/16
# In 10-bit complement: 1101100000

# Let me verify this is right
print(f"-5/16 in 10-bit: 1101100000 = {booth_decode(0b1101100000, 10)}")

# Now: in Booth multiplication, the standard algorithm for a multiplier with
# n bits (including sign) does n iterations of (add+shift).
# After n iterations: product = PP(n bits) || MQ(n bits) = 2n bits.
# For INTEGER multiplication this gives the correct 2n-bit product.
#
# For FRACTIONAL multiplication: x and y each have n bits with binary point
# after the sign bit. The product has 2n bits with binary point after the 
# second sign bit (i.e., 2 sign bits + 2(n-1) mantissa bits).
# So the 2n-bit result has TWO sign bits, and we take the lower 2n-1 bits
# (dropping one redundant sign bit) = 2n-1 bits? No...
#
# Actually: the product of two n-bit fractions (1 sign + (n-1) mantissa)
# has 2n bits = 2 sign + 2(n-1) mantissa. We drop one sign bit → 2n-1 bits.
# But the problem says "double word = 10 bits" for 5-bit × 5-bit.
# 2×5 = 10. So the 10-bit result includes both sign bits? Or drops one?
#
# The Booth register: PP(6 bits, double sign) || MQ(5 bits) = 11 bits.
# The top sign bit of PP is redundant → 10-bit product = PP_low5 || MQ5.
#
# We verified: standard 5 iterations gives PP_low5||MQ5 = 1110110000 = -5/32.
# This is WRONG. The correct is 1101100000 = -5/16.
#
# THE ISSUE: In fractional Booth, the extra sign bit of the product is 
# NOT just the PP's second sign bit. The product genuinely has 2 sign bits
# only when both operands are negative or both positive.
# For x>0, y<0: x*y < 0, and the product has one sign bit.
# The Booth register PP(6)||MQ(5) = 11 bits already contains the correct product
# but we need to decode it as an 11-bit number, then the actual result 
# might need to be extracted differently.
#
# Actually, the real issue might be simpler. Let me reconsider.
# For FRACTIONAL Booth: x = +1/2 = 0.1000 (5 bits), y = -5/8 = 1.0110 (5 bits)
# These are 5-bit fractions. Their product is a 10-bit fraction.
# 
# In the Booth algorithm, the partial product register has DOUBLE sign bits (6 bits)
# because adding two numbers with the same sign can temporarily overflow.
# After all iterations, the 6-bit PP has a redundant sign bit.
# The final product is PP_low5 || MQ5 = 10 bits.
#
# With 5 iterations of add+shift: PP_low5||MQ5 = 1110110000 = -5/32.
# But correct answer is -5/16 = 1101100000.
#
# The difference is exactly a factor of 2. This suggests an off-by-one in 
# the number of iterations. For a 5-bit FRACTION multiplier (1 sign + 4 mantissa),
# we should do 4 iterations (for 4 mantissa bits), NOT 5.
#
# 4 iterations of add+shift:
x6 = 8; nx6 = 56; y5 = 22
COMBO = y5; EXTRA = 0
for step in range(4):
    pp = (COMBO >> 5) % 64
    mq = COMBO % 32
    pair = f"{mq & 1}{EXTRA}"
    if pair == "01": pp_new = (pp + x6) % 64
    elif pair == "10": pp_new = (pp + nx6) % 64
    else: pp_new = pp
    combo_after = (pp_new << 5) | mq
    sign = (combo_after >> 10) & 1
    combo_shifted = (combo_after >> 1) | (sign << 10)
    EXTRA = combo_after & 1
    COMBO = combo_shifted

pp_f = (COMBO >> 5) % 64
mq_f = COMBO % 32
prod = ((pp_f & 0b11111) << 5) | (mq_f & 0b11111)
print(f"\n4 iterations: PP={format(pp_f,'06b')} MQ={format(mq_f,'05b')}")
print(f"PP_low5||MQ5 = {format(prod,'010b')} = {booth_decode(prod,10)}")
# After 4 iterations we haven't processed the sign bit of y (y4=1).
# We need one more step for the sign bit. But it should be add-only (no shift)?
# Because the sign bit contributes at its position (2^4) and doesn't need 
# to be shifted further.

# 4 iterations + 1 sign-bit add (no shift):
print("\n4 iterations + sign add (no shift):")
COMBO = y5; EXTRA = 0
for step in range(4):
    pp = (COMBO >> 5) % 64
    mq = COMBO % 32
    pair = f"{mq & 1}{EXTRA}"
    if pair == "01": pp_new = (pp + x6) % 64
    elif pair == "10": pp_new = (pp + nx6) % 64
    else: pp_new = pp
    combo_after = (pp_new << 5) | mq
    sign = (combo_after >> 10) & 1
    combo_shifted = (combo_after >> 1) | (sign << 10)
    EXTRA = combo_after & 1
    COMBO = combo_shifted

# Now process sign bit: pair = (y4, y3)
pp = (COMBO >> 5) % 64
mq = COMBO % 32
# At this point MQ LSB = y4 (after 4 right shifts, y4 is now at LSB? No...)
# Actually after 4 right shifts of the 11-bit register, the MQ has shifted right 4 times
# MQ originally = 10110 (y4 y3 y2 y1 y0)
# After 4 shifts: MQ = the lower bits of the shifted register
# The "sign bit add" should use pair (y4, y3) = (1,0) = "10" → +[-x]
pair_sign = f"{mq & 1}{EXTRA}"
print(f"Sign step pair = {pair_sign}")
if pair_sign == "01": pp_new = (pp + x6) % 64
elif pair_sign == "10": pp_new = (pp + nx6) % 64
else: pp_new = pp
# NO SHIFT for this step
COMBO = (pp_new << 5) | mq  # MQ stays the same

pp_f = (COMBO >> 5) % 64
mq_f = COMBO % 32
prod = ((pp_f & 0b11111) << 5) | (mq_f & 0b11111)
print(f"PP={format(pp_f,'06b')} MQ={format(mq_f,'05b')}")
print(f"PP_low5||MQ5 = {format(prod,'010b')} = {booth_decode(prod,10)}")
print(f"PP as 6-bit = {booth_decode(pp_f,6)}")
print(f"PP low5 as 5-bit = {booth_decode(pp_f & 0b11111, 5)}")
