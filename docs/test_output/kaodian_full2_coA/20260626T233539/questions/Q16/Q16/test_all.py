"""
Definitive test: what does STANDARD textbook Booth actually do?

Key insight: for n-bit mantissa (n=4), Booth does n+1=5 iterations.
But the PRODUCT is formed differently depending on the textbook.

Textbook A (most common): n+1 iterations, each = judge+add+shift
  Product = PP(low n+1 bits) || MQ(n+1 bits) = 2(n+1) bits

Textbook B: n iterations judge+add+shift, then the product is just PP||MQ

The real question: does the last shift matter?
In textbook Booth, after n+1 shifts, the result is correct because
the n+1-th shift aligns the sign properly.

Let me test: 5 iterations with ALL shifts (including 5th), using
double-sign [x]补 and [-x]补, and check the 10-bit product.
"""
from fractions import Fraction

x5 = 0b01000
neg_x5 = 0b11000
y5 = 0b10110
x6 = 0b001000
neg_x6 = 0b111000

total_mod = 1 << 11

def run(n_steps, shift_all, use_dbl_sign):
    """Run Booth, return (pp_final, mq_final, combo_final)"""
    combo = (0 << 5) | y5
    extra = 0
    xa = x6 if use_dbl_sign else x5
    nxa = neg_x6 if use_dbl_sign else neg_x5
    pp_mask = 0b111111
    
    for i in range(n_steps):
        mq = combo & 0b11111
        pp = (combo >> 5) & 0b111111
        mq_lsb = mq & 1
        judge = (mq_lsb << 1) | extra
        
        if judge == 0b01:
            pp_new = (pp + xa) & pp_mask
        elif judge == 0b10:
            pp_new = (pp + nxa) & pp_mask
        else:
            pp_new = pp
        
        combo_after = (pp_new << 5) | mq
        new_extra = combo_after & 1
        
        do_shift = shift_all or (i < n_steps - 1)
        if do_shift:
            sign = (combo_after >> 10) & 1
            combo = (combo_after >> 1) | (sign << 10)
            combo &= 0b11111111111
            extra = new_extra
        else:
            combo = combo_after & 0b11111111111
            extra = new_extra
    
    pp_f = (combo >> 5) & 0b111111
    mq_f = combo & 0b11111
    return pp_f, mq_f, combo

def decode10(val):
    v = val % 1024
    if v >= 512: v -= 1024
    return Fraction(v, 512)

target = Fraction(-5, 16)

print("Testing all combinations:")
print(f"Target: {target} = {float(target)}\n")

for n_steps in [4, 5]:
    for shift_all in [True, False]:
        for use_dbl in [True, False]:
            pp_f, mq_f, combo = run(n_steps, shift_all, use_dbl)
            # Try all concatenation methods
            methods = {
                "PP_low5||MQ5": ((pp_f & 0b011111) << 5) | mq_f,
                "PP_full6||MQ_high4": (pp_f << 4) | ((mq_f >> 1) & 0b1111),
                "combo11_low10": combo & 0b01111111111,
            }
            for mname, prod in methods.items():
                val = decode10(prod)
                if val == target:
                    print(f"✓ MATCH: steps={n_steps}, shift_all={shift_all}, dbl_sign={use_dbl}, concat={mname}")
                    print(f"  PP={format(pp_f,'06b')}, MQ={format(mq_f,'05b')}, prod={format(prod,'010b')}={val}")

# Also try: what if PP itself IS the product (just PP decoded as the result)?
print("\n--- PP-as-product check ---")
for n_steps in [4, 5]:
    for shift_all in [True, False]:
        for use_dbl in [True, False]:
            pp_f, mq_f, combo = run(n_steps, shift_all, use_dbl)
            # PP is 6-bit double-sign, decode as 6-bit → divide by 16
            ppv = pp_f
            if ppv >= 32: ppv -= 64
            pp_val = Fraction(ppv, 16)
            # If shifted n_steps times, actual = pp_val * 2^(n_steps) ?
            # No... the PP value already reflects the shifts
            # Actually product = pp_val if it equals x*y
            if pp_val == target:
                print(f"✓ PP-AS-PRODUCT: steps={n_steps}, shift_all={shift_all}, dbl_sign={use_dbl}")
                print(f"  PP={format(pp_f,'06b')} = {pp_val}")

print("\n--- Summary of all combos (steps=5, dbl_sign=True) ---")
for shift_all in [True, False]:
    pp_f, mq_f, combo = run(5, shift_all, True)
    p1 = ((pp_f & 0b011111) << 5) | mq_f
    print(f"shift_all={shift_all}: PP={format(pp_f,'06b')}, MQ={format(mq_f,'05b')}, PP低5||MQ5={format(p1,'010b')}={decode10(p1)}")

print("\n--- Summary of all combos (steps=4, dbl_sign=True) ---")
for shift_all in [True, False]:
    pp_f, mq_f, combo = run(4, shift_all, True)
    p1 = ((pp_f & 0b011111) << 5) | mq_f
    print(f"shift_all={shift_all}: PP={format(pp_f,'06b')}, MQ={format(mq_f,'05b')}, PP低5||MQ5={format(p1,'010b')}={decode10(p1)}")
