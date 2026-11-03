import struct

A_hex = 0x41E00000
B_hex = 0x40FFFFFF

def to_float(x):
    return struct.unpack('>f', struct.pack('>I', x))[0]

A = to_float(A_hex)
B = to_float(B_hex)
C = A + B

print(f"A = {A}")
print(f"B = {B}")
print(f"A + B = {C}")
print(f"result hex = 0x{struct.unpack('>I', struct.pack('>f', C))[0]:08X}")
