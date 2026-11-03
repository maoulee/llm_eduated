from fractions import Fraction

def booth_decode(val, nbits):
    val = val % (1 << nbits)
    if val >= (1 << (nbits - 1)):
        val -= (1 << nbits)
    return Fraction(val, 1 << (nbits - 1))

# In the standard 5-step model (all add+shift):
# PP=111101, MQ=10000
# PP_low5 = 11101, MQ = 10000
# PP_low5 || MQ = 11101_10000 = 1110110000

val = 0b11101_10000
print(f"11101||10000 = {format(val,'010b')} = {booth_decode(val, 10)}")
# But 11101||10000 = 1110110000... let me check
print(f"bin = {bin(val)}")
# 1110110000 = ?
print(f"Manual: {format(val, '010b')}")

# Wait, I need to be careful. PP=111101 (6 bits). PP_low5 = drop MSB = 11101.
# MQ = 10000 (5 bits).
# PP_low5 || MQ = 11101 concatenated with 10000 = 1110110000 (10 bits)
print(f"\nConcatenation: {'11101'}{'10000'} = {int('1110110000', 2)}")
print(f"Decoded: {booth_decode(int('1110110000', 2), 10)}")

# YES! This is -5/16 = correct!
# So the standard 5-step model IS correct, but we need to take PP_low5 (drop MSB)
# and concatenate with MQ, where PP_low5 is the LOWER 5 bits of the 6-bit PP
# (not the upper 5 bits!)
#
# Wait, PP=111101. Lower 5 bits = 11101. Upper 5 bits = 11110.
# The earlier code used `pp_final & 0b011111` which masks to lower 5 bits.
# 111101 & 011111 = 011101 = 11101. Same thing.
# 
# But earlier debug showed PP_low5||MQ = 1110110000 = -5/32 with 5-step model.
# Let me recheck...
# PP=111101, PP&0b011111 = 011101 = 29. MQ = 10000 = 16.
# (29 << 5) | 16 = 928 + 16 = 944. 
# 944 = 1110110000. booth_decode(944, 10) = (944 - 1024)/512 = -80/512 = -5/32.
#
# Hmm, that's -5/32, not -5/16. Let me verify the concatenation again.
print(f"\n29 << 5 | 16 = {(29 << 5) | 16}")
print(f"format: {format((29<<5)|16, '010b')}")
print(f"decode: {booth_decode((29<<5)|16, 10)}")

# So 1110110000 = 944 = -80/512 = -5/32. NOT -5/16.
# But -5/16 = 1101100000 = 864.
# 1110110000 ≠ 1101100000. They're different!
# 11101_10000 vs 11011_00000
# 
# Wait, 1101100000 split as 5+5: 11011_00000
# PP_low5 would be 11011, MQ = 00000.
# But our PP=111101, PP_low5=11101, MQ=10000. These don't match.
#
# Let me try the OTHER concatenation: take the LOWER 5 bits of PP (6-bit)
# but that's 11101. The correct answer needs PP_low5 = 11011.
# 11011 = -5/16 as a 5-bit fraction. 11101 = -3/16 as a 5-bit fraction.
#
# So standard 5-step gives PP=111101. Its lower 5 bits = 11101 = -3/16.
# The correct answer PP should have lower 5 bits = 11011 = -5/16.
# These are genuinely different.
#
# So the 5-step model with all shifts is WRONG for this problem.
# The "4+1 no-shift" model gives PP=111011, lower 5 bits = 11011 = -5/16. ✓

# Let me verify: in the 4+1 model, what's the proper 10-bit product?
# PP = 111011 (6-bit double sign), MQ = 00001 (from last non-shift step)
# Product should be 10-bit. 
# In the "4+1" model, after 4 shifts + 1 add (no shift):
# PP_low5 || MQ5? MQ after 4 shifts contains what?
# Let me retrace:
x6=8; nx6=56; y5=22
COMBO = y5; EXTRA = 0
for step in range(5):
    pp = (COMBO >> 5) % 64
    mq = COMBO % 32
    pair = f"{mq & 1}{EXTRA}"
    if step < 4:
        if pair == "01": pp_new = (pp + x6) % 64
        elif pair == "10": pp_new = (pp + nx6) % 64
        else: pp_new = pp
        combo_after = (pp_new << 5) | mq
        sign = (combo_after >> 10) & 1
        COMBO = ((combo_after >> 1) | (sign << 10)) % 2048
        EXTRA = combo_after & 1
    else:
        # Last step: add only, no shift
        if pair == "01": pp_new = (pp + x6) % 64
        elif pair == "10": pp_new = (pp + nx6) % 64
        else: pp_new = pp
        COMBO = (pp_new << 5) | mq  # no shift
        EXTRA = EXTRA  # unchanged
    pp_now = (COMBO >> 5) % 64
    mq_now = COMBO % 32
    print(f"Step{step+1}: pair={pair} PP={format(pp_now,'06b')} MQ={format(mq_now,'05b')} ext={EXTRA}")

pp_f = (COMBO >> 5) % 64
mq_f = COMBO % 32
print(f"\nFinal PP={format(pp_f,'06b')} MQ={format(mq_f,'05b')}")
# 10-bit product = PP_low5 || MQ5
prod = ((pp_f & 0b011111) << 5) | (mq_f & 0b11111)
print(f"PP_low5||MQ5 = {format(prod,'010b')} = {booth_decode(prod,10)}")
# This should give -5/16
print(f"Expected -5/16 = {format(864,'010b')} = {booth_decode(864,10)}")
