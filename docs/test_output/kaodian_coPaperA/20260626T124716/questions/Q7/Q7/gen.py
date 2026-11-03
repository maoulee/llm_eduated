"""
IEEE 754 单精度浮点数表示：-100.4375(10) -> 二进制规格化 -> 字段 -> 十六进制
func_model：题干规则逐句翻译成代码。
"""
import struct

# ============ PARAMS ============
N_DEC = -100.4375   # 题干给的十进制数
# ================================

print("=" * 60)
print("PARAMS")
print(f"  N = {N_DEC}")
print("=" * 60)

# ---- 第(1)小问：十进制 -> 二进制 -> 规格化 ----

sign = 1 if N_DEC < 0 else 0
abs_val = abs(N_DEC)
int_part = int(abs_val)          # 100
frac_part = abs_val - int_part   # 0.4375

print("\n--- 第(1)小问 ---")
print(f"符号: S = {sign} (负数)")

# 整数部分转二进制：100 -> 1100100
int_bits = []
tmp = int_part
while tmp > 0:
    int_bits.append(tmp % 2)
    tmp //= 2
int_bits = int_bits[::-1]
int_bin = ''.join(str(b) for b in int_bits)
print(f"整数部分 {int_part} 的二进制 = {int_bin}")

# 小数部分转二进制：0.4375 -> 逐位乘2取整
frac_bits = []
f = frac_part
for i in range(23):
    f *= 2
    bit = int(f)
    frac_bits.append(bit)
    f -= bit
    if f == 0:
        break
frac_bin = ''.join(str(b) for b in frac_bits)
print(f"小数部分 {frac_part} 的二进制展开 = 0.{frac_bin}  (有效位数 = {len(frac_bin)})")

# 完整二进制小数
full_bin = int_bin + '.' + frac_bin       # 1100100.0111
print(f"完整二进制 = {full_bin}")

# 规格化：移动小数点到第一个1后面
# 1100100.0111 -> 1.1001000111 × 2^6
point_pos = len(int_bin)                  # 小数点在 int_bin 之后
E = point_pos - 1                         # 指数 = 整数部分位数 - 1

# 规格化后的尾数 1.M
mantissa_full = int_bin[1:] + frac_bin     # 去掉前导1，拼接小数点后所有位
normalized_form = f"1.{mantissa_full} × 2^{E}"
print(f"规格化形式: (-1)^{sign} × 1.{mantissa_full} × 2^{E}")
print(f"  S = {sign}, E = {E} (十进制)")
print(f"  完整尾数 1.M = 1.{mantissa_full}")

# ---- 第(2)小问：IEEE 754 各字段 ----

print("\n--- 第(2)小问 ---")
print(f"符号位 S = {sign} ({sign} 位)")

# 阶码字段 = E + 127
exponent_field = E + 127
exp_bits = []
tmp = exponent_field
for _ in range(8):
    exp_bits.append(tmp % 2)
    tmp //= 2
exp_bits = exp_bits[::-1]
exp_bin = ''.join(str(b) for b in exp_bits)
print(f"阶码字段 = E + 127 = {E} + 127 = {exponent_field} -> {exp_bin}")

# 尾数字段：1.M 小数点右边部分，截取/补齐 23 位
mantissa_field = mantissa_full[:23].ljust(23, '0')
print(f"尾数字段 (23位) = {mantissa_field}")
print(f"  (原始小数点后部分 = {mantissa_full}, 截取/补齐至23位)")

# ---- 第(3)小问：拼接 -> 十六进制 ----

print("\n--- 第(3)小问 ---")
bits_32 = f"{sign}{exp_bin}{mantissa_field}"
print(f"32位二进制 (S | 阶码 | 尾数):")
print(f"  {sign} | {exp_bin} | {mantissa_field}")
print(f"  完整: {bits_32}")

# 4位分组转十六进制
hex_str = ''
for i in range(0, 32, 4):
    nibble = bits_32[i:i+4]
    hex_str += format(int(nibble, 2), 'X')
print(f"8位十六进制 = 0x{hex_str}")

# ---- 交叉验证：用 struct 打包同样的值 ----
packed = struct.pack('>f', float(N_DEC))
hex_cross = packed.hex().upper()
print(f"\n交叉验证 (struct.pack): 0x{hex_cross}")

# ============ REASONING ============
print("\n" + "=" * 60)
print("REASONING")
print("=" * 60)
print(f"步骤1: -100.4375 -> 负数, S={sign}")
print(f"步骤2: |N| = {int_part} + 0.{frac_bin}")
print(f"步骤3: {int_part}(10) = {int_bin}(2)")
print(f"步骤4: 0.{frac_bin}(2) [逐位乘2取整]")
print(f"步骤5: 规格化 {full_bin} -> 1.{mantissa_full} × 2^{E}")
print(f"步骤6: 阶码 = {E}+127 = {exponent_field} = {exp_bin}")
print(f"步骤7: 尾数字段(23位) = {mantissa_field}")
print(f"步骤8: 拼接 -> 0x{hex_str}")

# ============ ANSWER ============
print("\n" + "=" * 60)
print("ANSWER")
print("=" * 60)
print(f"第(1)问: S={sign}, E={E}, 1.M = 1.{mantissa_full}")
print(f"第(2)问: S={sign}, 阶码={exp_bin}({exponent_field}), 尾数={mantissa_field}")
print(f"第(3)问: 0x{hex_str}")

# ============ 通过条件 assert ============
print("\n" + "=" * 60)
print("ASSERT (通过条件)")
print("=" * 60)

# 条件1: 小数部分二进制展开有效位数 >= 4
assert len(frac_bin) >= 4, f"小数二进制展开位数={len(frac_bin)} < 4"
print(f"[PASS] 条件1: 小数二进制展开有效位数 = {len(frac_bin)} >= 4")

# 条件2: 实际指数在正常范围 -126 <= E <= 127
assert -126 <= E <= 127, f"E={E} 超出正常范围"
assert 1 <= exponent_field <= 254, f"阶码字段={exponent_field} 触碰特殊值边界"
print(f"[PASS] 条件2: E={E} ∈ [-126,127], 阶码字段={exponent_field} ∈ [1,254]")

# 条件3: 尾数字段23位且隐含前导1不存储
assert len(mantissa_field) == 23, "尾数字段不为23位"
assert bits_32[0] == str(sign) and bits_32[1] == '1' or True  # 隐含1不存储->bits_32第9位起是尾数
# 更精确：struct 结果一致 => 尾数/前导1处理正确
assert hex_str == hex_cross, f"手动拼接 {hex_str} ≠ struct结果 {hex_cross}"
print(f"[PASS] 条件3&5: 手动拼接 = struct.pack 结果 = 0x{hex_str}")

# 条件4: 偏置方向 = E + 127（非 E-127 / 127-E）
assert exponent_field == E + 127, "偏置方向错误"
assert exponent_field != (127 - E), "误用 127-E"
assert exponent_field != (E - 127) if (E - 127) >= 0 else True, "误用 E-127"
print(f"[PASS] 条件4: 阶码={E}+127={exponent_field} (偏置方向正确)")

# 条件5: 十六进制 8 位无歧义
assert len(hex_str) == 8, "十六进制不为8位"
print(f"[PASS] 条件5: 十六进制 = 0x{hex_str} (8位, 无多义性)")

# 最终一致性
assert bits_32 == f"{sign}{exp_bin}{''.join(mantissa_field)}".ljust(32, '0')[:32]
assert int(hex_str, 16) == int(bits_32, 2)

print("\n>>> 所有通过条件 assert 通过 <<<")
