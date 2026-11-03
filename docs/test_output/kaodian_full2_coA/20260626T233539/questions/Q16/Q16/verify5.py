"""
最终验证：找到让 Rule4(乘积正确) 和 Rule6(第5趟仅移位) 同时成立的方案

已知：5次判断加减+4次移位 → PP=-5/16 ✓（这就是x*y）
但 Rule6 要求第5趟"仅移位不加减"

如果题干真的要求第5趟不加减：
  那4次判断加减+4次移位 → PP=3/16 ✗

所以题干的Rule6"第5趟仅移位"与Rule4矛盾？
除非...第5趟的"移位"不是右移PP，而是某种最终对齐？

或者：把5次循环理解为
  前4次: 判断+加减+右移
  第5次: 判断+加减(但不右移)
然后题干把"不右移"表达为"仅移位"是笔误？

不，我不应该改题干意图。让我看通过的方案：
  正确的Booth: 5次判断, 4次移位, 最后一次不移位
  → 第5趟有加减但无移位
  
但题干说"第5趟仅移位不加减" → 相反

最合理的解释：题干的"趟"指的就是"移位"次数。
标准Booth: n+1=5位乘数，做n+1=5次判断，但只有n=4次右移。
题干把它表述为"5趟"但其实是5次判断，最后那次判断后不移位。
题干说"第5趟仅移位"可能是指流程上有一个最后的"不操作"步。

但我不能改题干。让我找一个实际能同时满足Rule4和Rule6的方案。

方案：做5次循环，每次都判断+加减+右移
  → PP=-5/32, 然后拼接10位乘积
  → 看10位拼接能否=x*y
"""
from fractions import Fraction

# 检查：5次判断+5次移位，然后乘积=PP(6位)||MQ(5位)去掉冗余符号位
# PP=-5/32 → 用6位双符号位表示
# -5/32 * 64 = -10 → 补码: 64-10=54=110110 → 11.0110 = -10/16... 不对
# PP是定点小数 SS.xxxx, 值 = 整数/16
# -5/32 = -2.5/16 → 不能用4位数值精确表示！

# 所以5次移位后PP=-5/32无法用6位双符号位精确表示
# 这条路不通

# 唯一正确的方案：5次判断+4次移位
# PP=-5/16 → 6位: -5/16*16=-5 → 补码64-5=59=111011 → 11.1011
# 不对，-5/16 在双符号位中: 整数值=-5, 6位补码=64-5=59=111011=11.1011
# 但-5/16 = 11.1011? 验证: 11.1011 → -(2^5-0b1011)/16... 
# 双符号位补码: 111011, 值 = -(64-59)/16? 不对
# 6位补码: 如果>=32则减64: 59-64=-5, 值=-5/16 ✓

# PP最终=11.1011, MQ最终需要确定
# 但在5次判断+4次移位的方案中，第5次不移位，MQ是什么状态？

# 让我精确模拟5次判断+4次移位的联合寄存器
x_comp_5 = 0b01000    # [x]补 5位
neg_x_5 = 0b11000     # [-x]补 5位
y_comp_5 = 0b10110    # [y]补 5位

x_dbl = 0b001000      # [x]补 6位双符号位
neg_x_dbl = 0b111000  # [-x]补 6位双符号位

pp_mod = 64
total_mod = 1 << 11  # PP(6) || MQ(5) = 11位

combo = (0 << 5) | y_comp_5
extra = 0

print("=== 5次判断+4次移位(第5次不移位) ===")
print(f"初始: PP=00.0000, MQ={format(y_comp_5,'05b')}, 附加位=0")

for i in range(5):
    mq = combo % 32
    pp = combo >> 5
    mq_lsb = mq & 1
    judge = mq_lsb * 2 + extra
    
    if judge == 1:
        pp_new = (pp + x_dbl) % pp_mod
        op = "+[x]补"
    elif judge == 2:
        pp_new = (pp + neg_x_dbl) % pp_mod
        op = "+[-x]补"
    else:
        pp_new = pp
        op = "+0"
    
    combo_after = (pp_new << 5) | mq
    new_extra = combo_after & 1
    
    if i < 4:  # 前4次移位
        sign = (combo_after >> 10) & 1
        combo = (combo_after >> 1) | (sign << 10)
        combo %= total_mod
        extra = new_extra
        shifted = "右移"
    else:
        combo = combo_after  # 第5次不移位
        extra = new_extra
        shifted = "不移位"
    
    pp_s = combo >> 5
    mq_s = combo % 32
    b = format(pp_s % 64, '06b')
    print(f"  步{i+1}: judge={format(judge,'02b')}, {op}, PP加减后={format(pp_new,'06b')}, {shifted}后PP={b[0:2]}.{b[2:]}, MQ={format(mq_s,'05b')}, 附加位={extra}")

pp_f = combo >> 5
mq_f = combo % 32
b = format(pp_f % 64, '06b')
print(f"\n最终: PP={b[0:2]}.{b[2:]}, MQ={format(mq_f,'05b')}")

# 乘积 = PP(6位) || MQ(5位) = 11位, 去掉最高冗余符号位 = 10位
prod11 = (pp_f << 5) | mq_f
prod10 = prod11 & 0b01111111111  # 去掉最高位
print(f"乘积11位 = {format(prod11, '011b')}")
print(f"乘积10位 = {format(prod10, '010b')}")

# 解码10位补码小数
v = prod10
if v >= 512:
    v -= 1024
prod_val = Fraction(v, 512)
print(f"乘积真值 = {prod_val} = {float(prod_val)}")
print(f"期望 x*y = {Fraction(1,2)*Fraction(-5,8)} = {float(Fraction(1,2)*Fraction(-5,8))}")
print(f"匹配: {prod_val == Fraction(1,2)*Fraction(-5,8)}")

# 注意：第5趟有加减（+[-x]补）但没有移位
# 这与题干"第5趟仅移位不加减"矛盾
# 但这是数学上唯一正确的Booth流程
print(f"\n注意: 第5趟执行了加减(+[-x]补)但没有移位")
print(f"题干说'第5趟仅移位不加减'，但数学上第5趟必须有加减")
