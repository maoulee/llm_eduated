"""
彻底重做：标准Booth补码一位乘法（教材标准流程）

教材标准（以n=4数值位为例）：
1. 被乘数[x]补、乘数[y]补，均为n+1=5位（含1符号+n数值）
2. 部分积初始为0，采用双符号位（n+2=6位）
3. 乘数寄存器：n+1=5位 + 1位附加位（初始0）
4. 判断位 = 乘数最低位 + 附加位
5. 做n+1=5步循环：
   - 每步：根据判断位对部分积加减，然后部分积+乘数级联算术右移1位
   - 注意：有些教材是n步，有些是n+1步
6. 乘积 = 部分积(高位) || 乘数(低位)

关键：标准Booth做n+1步，每步都移位。
但5步5移位后，PP右移了5次，相当于除了2^5=32。
初始PP每次加减的量是±x（值±1/2），5次加减后累积...
不对，每次加减后移位，所以加减的权重不同。

让我用完全不同的方法：直接追踪乘积寄存器的位
"""
from fractions import Fraction

# 标准Booth：直接模拟11位联合寄存器 PP(6) || MQ(5)
# 附加位在联合寄存器外部

# 参数
x_true = Fraction(1, 2)
y_true = Fraction(-5, 8)

# 补码
x5 = 0b01000    # [x]补 = 0.1000
neg_x5 = 0b11000 # [-x]补 = 1.1000
y5 = 0b10110    # [y]补 = 1.0110

# 双符号位扩展
x6 = 0b001000   # 00.1000
neg_x6 = 0b111000 # 11.1000

# 联合寄存器 PP(6位) || MQ(5位) = 11位
# 附加位 EXTRA 初始0

def run_booth(n_steps, all_shift=True):
    """运行Booth算法
    n_steps: 循环步数
    all_shift: True=每步都移位, False=最后一步不移位
    """
    combo = (0 << 5) | y5  # PP=0, MQ=[y]补
    extra = 0
    trace = []
    
    for i in range(n_steps):
        mq = combo & 0b11111
        pp = (combo >> 5) & 0b111111
        mq_lsb = mq & 1
        judge = (mq_lsb << 1) | extra  # 高位=mq_lsb, 低位=extra
        
        if judge == 0b01:
            pp_new = (pp + x6) & 0b111111
            op = "+[x]补"
        elif judge == 0b10:
            pp_new = (pp + neg_x6) & 0b111111
            op = "+[-x]补"
        else:
            pp_new = pp
            op = "+0"
        
        combo_after = (pp_new << 5) | mq
        new_extra = mq_lsb  # 移位后附加位 = 移位前的MQ最低位
        
        do_shift = all_shift or (i < n_steps - 1)
        if do_shift:
            # 算术右移：符号扩展
            sign = (combo_after >> 10) & 1
            combo = (combo_after >> 1) | (sign << 10)
            combo &= 0b11111111111
            extra = new_extra
            shifted = True
        else:
            combo = combo_after & 0b11111111111
            extra = new_extra
            shifted = False
        
        trace.append((i+1, judge, op, pp_new, combo, extra, shifted))
    
    pp_f = (combo >> 5) & 0b111111
    mq_f = combo & 0b11111
    return pp_f, mq_f, extra, trace

def decode_10bit(val):
    v = val % 1024
    if v >= 512:
        v -= 1024
    return Fraction(v, 512)

# 穷举所有可能的方案
print("穷举Booth方案 (寻找乘积=-5/16)")
print("=" * 60)

target = Fraction(-5, 16)

for n_steps in range(3, 8):
    for all_shift in [True, False]:
        pp_f, mq_f, extra_f, trace = run_booth(n_steps, all_shift)
        
        # 尝试多种拼接
        products = {
            "PP低5||MQ5": ((pp_f & 0b011111) << 5) | mq_f,
            "PP6||MQ高4": (pp_f << 4) | ((mq_f >> 1) & 0b1111),
            "PP6||MQ5去冗余": ((pp_f << 5) | mq_f) & 0b01111111111,
        }
        
        for pname, prod in products.items():
            val = decode_10bit(prod)
            if val == target:
                print(f"\n✓✓✓ FOUND!")
                print(f"  steps={n_steps}, all_shift={all_shift}, concat={pname}")
                print(f"  PP={format(pp_f,'06b')}, MQ={format(mq_f,'05b')}")
                print(f"  乘积={format(prod,'010b')} = {val}")
                for t in trace:
                    s = "移位" if t[6] else "不移位"
                    print(f"    步{t[0]}: judge={format(t[1],'02b')}, {t[2]}, PP={format(t[3],'06b')}, combo后={format(t[4],'011b')}, ext={t[5]}, {s}")

# 如果没找到，打印所有结果供分析
print("\n\n所有方案结果:")
for n_steps in [4, 5]:
    for all_shift in [True, False]:
        pp_f, mq_f, extra_f, trace = run_booth(n_steps, all_shift)
        p1 = ((pp_f & 0b011111) << 5) | mq_f
        val1 = decode_10bit(p1)
        print(f"  steps={n_steps}, all_shift={all_shift}: PP={format(pp_f,'06b')}, MQ={format(mq_f,'05b')}, 乘积(PP低5||MQ5)={format(p1,'010b')}={val1}")
