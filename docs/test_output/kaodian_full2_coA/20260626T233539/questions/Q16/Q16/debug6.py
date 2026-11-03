from fractions import Fraction

# Mathematical Booth algorithm for fractions
# x = 1/2, y = -5/8
# y in binary (5-bit): 1.0110 = bits: y4=1, y3=0, y2=1, y1=1, y0=0
# y_{-1} = 0 (extra bit)

x = Fraction(1, 2)
y = Fraction(-5, 8)

# Booth recoding: look at pairs (y_i, y_{i-1}) for i=0,1,2,3,4
# y bits from LSB: y0=0, y1=1, y2=1, y3=0, y4=1
y_bits = [0, 1, 1, 0, 1]  # y0..y4
y_bits_ext = y_bits + [0]  # y_{-1} = 0

# Booth encoding: for each i, coefficient c_i = y_{i-1} - y_i
coeffs = []
for i in range(5):
    c = y_bits_ext[i-1] - y_bits_ext[i] if i > 0 else 0 - y_bits[i]
    # Actually: c_i = y_{i-1} - y_i
    # For i=0: c_0 = y_{-1} - y_0 = 0 - 0 = 0
    # For i=1: c_1 = y_0 - y_1 = 0 - 1 = -1
    # For i=2: c_2 = y_1 - y_2 = 1 - 1 = 0
    # For i=3: c_3 = y_2 - y_3 = 1 - 0 = +1
    # For i=4: c_4 = y_3 - y_4 = 0 - 1 = -1
    coeffs.append(c)

print("Booth coefficients (c_i = y_{i-1} - y_i):")
for i, c in enumerate(coeffs):
    print(f"  c_{i} = y_{'{-1}' if i==0 else i-1} - y_{i} = {c}")

# Product = x * sum(c_i * 2^{-i}) for i=0..4... wait, this isn't right for fractions
# In Booth for fractions:
# y = sum(y_i * 2^{-i}) where y_0 is the sign bit at 2^0 position? No.
# Actually y = -y_4*1 + y_3*2^{-1} + y_2*2^{-2} + y_1*2^{-3} + y_0*2^{-4}
# = -1 + 0*0.5 + 1*0.25 + 1*0.125 + 0*0.0625
# = -1 + 0.375 = -0.625 ✓

# In Booth, product = x * y where y is decomposed via Booth recoding:
# y = sum over i of (y_{i-1} - y_i) * 2^{-i} ... hmm this needs the right scaling
# Actually for a fraction with bits y4.y3y2y1y0:
# y = -y4 + y3/2 + y2/4 + y1/8 + y0/16
# Booth recoding writes y as sum of d_i * 2^{-i} where d_i = y_{i-1} - y_i
# but the positions are: bit i is at position 2^{-(4-i)} for i=0..4

# Let me think in terms of integer representation.
# y_int = 22 (5-bit complement for -10/16 = -5/8)
# Booth: y_int = sum(c_i * 2^i) where c_i = y_{i-1} - y_i (integer Booth)
# Then x_int * y_int = sum(c_i * x_int * 2^i) = the integer product

# For fractions: x * y = (x_int/16) * (y_int/16) where x_int, y_int are the 
# 5-bit complement integers. x_int=8, y_int=-10.
# Product = -80/256 = -5/16.

# In Booth hardware: PP accumulates c_i * x, then shifts right.
# Each iteration: add c_i * x to PP, shift PP right.
# After processing all bits of y (5 bits), PP contains the product / 2^5.
# No wait...

# Let me just think about what the hardware does step by step:
# PP starts at 0. MQ = [y] = 10110.
# Each step:
#   1. Look at (MQ_LSB, extra)
#   2. Add x, -x, or 0 to PP
#   3. Shift PP and MQ right by 1 (PP LSB goes to MQ MSB, MQ LSB goes to extra)
# After 5 steps, all bits of y have been examined.
# Product = PP(6) || MQ(5), drop one redundant sign → 10 bits.

# The key question: for fractional Booth, after n=5 steps, does PP||MQ 
# give the correct result?

# For INTEGER Booth with n-bit operands: after n steps, PP||MQ = 2n-bit product. ✓
# The integer product of x_int=8 and y_int=-10 is -80.
# -80 in 10 bits = 1110110000 (= 944 unsigned, -80 signed).
# PP||MQ after 5 steps = 1110110000 = -80 as integer. ✓

# For FRACTIONAL: the 10-bit result 1110110000 represents 
# -80 * 2^{-(2*(5-1))} = -80 * 2^{-8} = -80/256 = -5/16. ✓✓✓

# THE ANSWER IS CORRECT: 1110110000 = -5/16 when properly decoded!
# The issue was my booth_decode function uses nbits-1 as the power,
# which gives -80/512 = -5/32 for 10 bits.
# But for a product of two 5-bit fractions, the 10-bit result should be
# decoded as 2 sign bits + 8 mantissa bits, NOT 1 sign + 9 mantissa.

# Let me verify: 
def frac_product_decode(val, operand_bits):
    """Decode product of two operand_bits-bit fractions (2*operand_bits bit result)
    with 2 sign bits and 2*(operand_bits-1) mantissa bits."""
    nbits = 2 * operand_bits
    val = val % (1 << nbits)
    if val >= (1 << (nbits - 1)):
        val -= (1 << nbits)
    return Fraction(val, 1 << (nbits - 2))  # 2 sign bits, so /2^(nbits-2)

print(f"\n-80 decoded with 2 sign bits: {frac_product_decode(944, 5)}")
print(f"Expected: {x * y}")

# YES! -80/256 = -5/16. The 10-bit result 1110110000 = -5/16 when decoded
# with 2 sign bits (which is correct for product of two 5-bit fractions).

# So the standard 5-step Booth IS correct. The bug was in decoding.
# The 10-bit product has TWO sign bits (because both operands contribute one).
# PP has 6 bits = 2 sign + 4 mantissa. MQ has 5 bits = 1 sign + 4 mantissa.
# Combined 10 bits after dropping 1 redundant sign = ... 
# Actually PP_low5(1 sign + 4 mantissa) || MQ(4 mantissa + 1 sign) doesn't work.

# The correct interpretation: 
# PP(6 bits) || MQ(5 bits) = 11 bits. Drop the top sign bit → 10 bits.
# But PP_low5 = bits 4..0 of PP. Then PP_low5 || MQ = 10 bits.
# PP=111101 → PP_low5=11101. MQ=10000.
# 11101||10000 = 1110110000.
# This is the 10-bit product. Decoded with 2 sign bits: -5/16. ✓

print(f"\nFinal verification:")
print(f"PP=111101, PP_low5=11101={0b11101}, MQ=10000={0b10000}")
prod = (0b11101 << 5) | 0b10000
print(f"PP_low5||MQ = {format(prod,'010b')} = {prod}")
print(f"Decoded (2 sign bits): {frac_product_decode(prod, 5)}")
print(f"Decoded (1 sign bit): {Fraction(prod-1024 if prod >= 512 else prod, 512)}")
print(f"Correct answer: {x*y}")
