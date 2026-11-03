"""
精确分数追踪 Booth 乘法，彻底搞清楚正确流程
x = +0.5, [x]补 = 0.1000 (5位), 双符号位 00.1000
y = -0.625, [y]补 = 1.0110 (5位), 双符号位 11.0110
-x = -0.5, [-x]补 = 1.1000 (5位), 双符号位 11.1000

Booth补码一位乘法标准流程(教材):
- 部分积PP用双符号位
- 乘数MQ用单符号位(5位)
- 判断位 = MQ最低位 + 附加位(在右侧)
- n+1=5趟？还是n=4趟？

教材标准: 小数Booth乘法，n位数值位，做n+1步(含符号位共n+1位乘数)
但也有教材说做n步。关键看结果对不对。
"""
from fractions import Fraction

# 用精确的定点分数表示，PP = 整数值 / 2^4 (6位中2符号+4数值)
# PP 是 6位，其中低4位是数值位，高2位是符号位
# PP的真值 = (6位补码整数) / 16

def pp_decode(val6):
    """6位双符号位补码小数 -> 真值"""
    v = val6 % 64
    if v >= 32:
        v -= 64
    return Fraction(v, 16)

def pp_format(val6):
    v = val6 % 64
    b = format(v, '06b')
    return b[0:2] + '.' + b[2:]

# 常量(6位双符号位)
X_DBL = 0b001000    # [x]补 双符号位 = 00.1000 = +0.5
NEG_X_DBL = 0b111000 # [-x]补 双符号位 = 11.1000 = -0.5
Y_COMP = 0b10110     # [y]补 = 1.0110 (5位)

print(f"[x]补 = {pp_format(X_DBL)} = {pp_decode(X_DBL)}")
print(f"[-x]补 = {pp_format(NEG_X_DBL)} = {pp_decode(NEG_X_DBL)}")
print(f"[y]补 = {format(Y_COMP, '05b')}")

# Booth 迭代
# PP(6位) || MQ(5位) 级联，共11位
total_bits = 11
total_mod = 1 << total_bits

combo = (0 << 5) | Y_COMP  # PP=00.0000, MQ=1.0110
extra = 0

print(f"\n初始: PP={pp_format(0)}, MQ={format(Y_COMP,'05b')}, 附加位={extra}")

results = {}
for n_steps in [4, 5]:
    combo = (0 << 5) | Y_COMP
    extra = 0
    trace = []
    for i in range(n_steps):
        mq = combo % 32
        pp = combo >> 5
        mq_lsb = mq & 1
        judge = mq_lsb * 2 + extra  # 高位=mq_lsb, 低位=extra
        
        if judge == 1:   # 01: +[x]补
            pp_new = (pp + X_DBL) % 64
        elif judge == 2:  # 10: +[-x]补
            pp_new = (pp + NEG_X_DBL) % 64
        else:
            pp_new = pp
        
        combo_after = (pp_new << 5) | mq
        new_extra = combo_after & 1
        sign = (combo_after >> 10) & 1
        combo = (combo_after >> 1) | (sign << 10)
        combo %= total_mod
        extra = new_extra
        
        pp_s = combo >> 5
        mq_s = combo % 32
        trace.append((i+1, format(judge,'02b'), pp_new, pp_s, mq_s, extra))
    
    pp_f = combo >> 5
    mq_f = combo % 32
    results[n_steps] = (pp_f, mq_f, trace)

# 打印4步
print("\n=== 4步 ===")
for t in results[4][2]:
    print(f"  步{t[0]}: judge={t[1]}, PP加减后={pp_format(t[2])}={pp_decode(t[2])}, 右移PP={pp_format(t[3])}={pp_decode(t[3])}, MQ={format(t[4],'05b')}, 附加位={t[5]}")
pp4, mq4, _ = results[4]
print(f"最终: PP={pp_format(pp4)}={pp_decode(pp4)}, MQ={format(mq4,'05b')}")

# 拼接乘积
# 乘积 = PP(6位双符号位,取低5位含1符号) || MQ(5位) = 10位
# 或 PP(6位) || MQ(5位) = 11位，去掉最高冗余符号位 = 10位
for n_steps in [4, 5]:
    pp_f, mq_f, _ = results[n_steps]
    # 方式1: PP低5位 || MQ 5位
    p1 = ((pp_f & 0b011111) << 5) | mq_f
    # 方式2: PP 6位 || MQ高4位(去掉MQ最低位)
    p2 = (pp_f << 4) | ((mq_f >> 1) & 0b1111)
    # 方式3: PP高5位(含双符号位最高) || MQ 5位
    p3 = ((pp_f >> 1) << 5) | mq_f
    
    def dec10(v):
        v = v % 1024
        if v >= 512: v -= 1024
        return Fraction(v, 512)
    
    print(f"\n{n_steps}步最终 PP={pp_format(pp_f)}={pp_decode(pp_f)}, MQ={format(mq_f,'05b')}")
    print(f"  方式1(PP低5||MQ5): {format(p1,'010b')} = {dec10(p1)} = {float(dec10(p1))}")
    print(f"  方式2(PP6||MQ高4): {format(p2,'010b')} = {dec10(p2)} = {float(dec10(p2))}")
    print(f"  方式3(PP高5||MQ5): {format(p3,'010b')} = {dec10(p3)} = {float(dec10(p3))}")

print(f"\n期望 x*y = -5/16 = {float(Fraction(-5,16))}")

# 让我检查：如果乘积 = PP真值(6位) 本身就是结果？
# 4步: PP真值 = pp_decode(pp4)
print(f"\n4步PP真值 = {pp_decode(pp4)} (右移4次后，实际值应乘2^4)")
print(f"  PP真值 * 16 = {pp_decode(pp4) * 16} (应该=x*y)")
