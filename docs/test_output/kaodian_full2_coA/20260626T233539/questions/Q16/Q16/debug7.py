from fractions import Fraction

def booth_decode(val, nbits):
    val = val % (1 << nbits)
    if val >= (1 << (nbits - 1)):
        val -= (1 << nbits)
    return Fraction(val, 1 << (nbits - 1))

# The question's convention: 4 iterations of (add+shift), 5th iteration shift only.
# Let me trace this carefully:
x6=8; nx6=56; y5=22  # x=0.1000→00.1000=8, -x=1.1000→11.1000=56, y=1.0110=22

COMBO = (0 << 5) | y5  # PP=0, MQ=y5
EXTRA = 0

print("Question convention: 4 add+shift + 1 shift-only")
print(f"Initial: PP=00.0000, MQ={format(y5,'05b')}, ext={EXTRA}")
print()

for step in range(5):
    pp = (COMBO >> 5) % 64
    mq = COMBO % 32
    pair = f"{mq & 1}{EXTRA}"
    
    if step < 4:  # first 4: add+shift
        if pair == "01": pp_new = (pp + x6) % 64; op = "+[x]"
        elif pair == "10": pp_new = (pp + nx6) % 64; op = "+[-x]"
        else: pp_new = pp; op = "+0"
        shift = True
    else:  # 5th: shift only (no add)
        pp_new = pp; op = "shift only"
        shift = True
    
    combo_after = (pp_new << 5) | mq
    sign = (combo_after >> 10) & 1
    combo_shifted = ((combo_after >> 1) | (sign << 10)) % 2048
    new_extra = combo_after & 1
    
    pp_sh = (combo_shifted >> 5) % 64
    mq_sh = combo_shifted % 32
    
    print(f"Step {step+1}: pair={pair}, op={op}")
    print(f"  PP after add={format(pp_new,'06b')}, after shift={format(pp_sh,'06b')}")
    print(f"  MQ={format(mq_sh,'05b')}, ext={new_extra}")
    
    COMBO = combo_shifted
    EXTRA = new_extra

pp_f = (COMBO >> 5) % 64
mq_f = COMBO % 32

# 10-bit product
ph = pp_f & 0b011111  # PP low 5
pl = mq_f & 0b11111   # MQ 5
prod10 = (ph << 5) | pl

print(f"\nFinal: PP={format(pp_f,'06b')}, MQ={format(mq_f,'05b')}")
print(f"PP_low5||MQ5 = {format(prod10,'010b')} = {prod10}")
print(f"Decoded (1 sign): {booth_decode(prod10, 10)}")
print(f"Expected x*y: {Fraction(1,2)*Fraction(-5,8)}")

# Result: 0000110000 = 3/32. WRONG (expected -5/16).
# This confirms: question convention (4+1 shift-only) gives 3/32 for y=-0.625.

# ============================================
# CONCLUSION: The problem's parameters and convention are INCOMPATIBLE.
# The question says "5趟（4趟加减+移位，第5趟仅移位）" but for y=-0.625,
# the 5th pair is "10" which REQUIRES +[-x], not shift-only.
#
# For the "4+1 shift-only" convention to work, the 5th pair must be "00" or "11".
# The 5th pair is (y4, y3) where y4 is the sign bit of y and y3 is the bit below.
# For pair to be "00": y4=0 (y positive) and y3=0
# For pair to be "11": y4=1 (y negative) and y3=1
#
# For y=-0.625: y=1.0110, y4=1, y3=0 → pair=(1,0)="10". WRONG.
# We need y4=y3, i.e., the sign bit equals the MSB of mantissa.
#
# For NEGATIVE y: y4=1, need y3=1. y = 1.1xxx (mantissa starts with 1).
# Examples: y=-0.25=1.1100, y=-0.375=1.1010... 
# Wait y=-0.375=1.1010: y4=1,y3=1 → pair=11. ✓ but need 01 and 10 in the bits too.
#
# For POSITIVE y: y4=0, need y3=0. y=0.0xxx (mantissa starts with 0).
#
# OR: the correct model is standard 5-step Booth (all add+shift), and the
# "第5趟仅移位" description in the question is actually about a DIFFERENT 
# thing: after the sign bit is processed (step 5 includes add), the final 
# result needs one more alignment.
#
# Actually, let me reconsider: maybe for fractions with n=4 mantissa bits,
# we do n=4 iterations of add+shift. The 5th "shift" is the FINAL shift to 
# align the result, and the sign bit is handled as part of the 4th iteration's
# pair or implicitly.
# 
# Wait. In some textbooks, for a (1+n)-bit multiplier, Booth does n iterations
# (not n+1). The sign bit is implicitly handled. Let me try n=4 iterations:

print("\n\n=== n=4 iterations only (4 add+shift), then decode ===")
COMBO = (0 << 5) | y5
EXTRA = 0
for step in range(4):
    pp = (COMBO >> 5) % 64
    mq = COMBO % 32
    pair = f"{mq & 1}{EXTRA}"
    if pair == "01": pp_new = (pp + x6) % 64
    elif pair == "10": pp_new = (pp + nx6) % 64
    else: pp_new = pp
    combo_after = (pp_new << 5) | mq
    sign = (combo_after >> 10) & 1
    combo_shifted = ((combo_after >> 1) | (sign << 10)) % 2048
    EXTRA = combo_after & 1
    COMBO = combo_shifted
    print(f"Step{step+1}: pair={pair}, PP_sh={format((COMBO>>5)%64,'06b')}, MQ={format(COMBO%32,'05b')}")

pp_f = (COMBO >> 5) % 64
mq_f = COMBO % 32
prod10 = ((pp_f & 0b011111) << 5) | (mq_f & 0b11111)
print(f"PP={format(pp_f,'06b')} MQ={format(mq_f,'05b')}")
print(f"10-bit: {format(prod10,'010b')} = {booth_decode(prod10,10)}")

# The 4-iteration model doesn't process the sign bit → gives wrong partial result.
# Only the 5-iteration model (with the 5th being add+shift) gives the correct
# integer product, but the fractional decoding is off by 2x.

# THE RESOLUTION: In fractional Booth, we need n+1 iterations (5 for 5-bit 
# multiplier), but the LAST iteration's shift is the "final alignment shift"
# that the question calls "第5趟仅移位". The ADD for the sign bit pair happens
# in the 4th iteration or earlier... no, that doesn't work either.

# Let me try: 5 iterations where step 5 does add (for pair "10") then shift.
# This is standard. Result = 1110110000.
# If decoded as 10-bit with the understanding that the MSB is a redundant sign:
# value = (lower 9 bits decoded as 9-bit complement) where MSB confirms sign
# 1110110000: MSB=1 (negative). Lower 9 bits = 110110000.
# 110110000 as 9-bit: 432 - 512 = -80. As fraction: -80/2^8 = -80/256 = -5/16. ✓!

val9 = 0b110110000
print(f"\nLower 9 bits of 1110110000 = {format(val9,'09b')} = {val9}")
print(f"9-bit decode: {booth_decode(val9, 9)}")
# That gives -80/256 = -5/16. ✓
