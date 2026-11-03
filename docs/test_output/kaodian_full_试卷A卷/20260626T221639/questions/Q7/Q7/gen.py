"""
IEEE 754 单精度浮点数编码转换：将 -54.375 转换为 32 位机器数。
场景规则通过 assert 在数据流中验证（打特征，禁恒真）。
"""


def int_part_to_binary(n):
    """整数部分除2取余，返回二进制字符串（不含前导0b）。"""
    if n == 0:
        return "0"
    bits = []
    while n > 0:
        bits.append(str(n % 2))
        n //= 2
    bits.reverse()
    return "".join(bits)


def frac_part_to_binary(frac, max_bits=60):
    """小数部分乘2取整，返回二进制字符串。遇到精确终止或达到 max_bits 停止。"""
    bits = []
    for _ in range(max_bits):
        frac *= 2
        if frac >= 1:
            bits.append("1")
            frac -= 1
        else:
            bits.append("0")
        if frac == 0:
            break
    return "".join(bits)


def solve(decimal_val, bias=127):
    # ---- 参数 ----
    sign_bit = 1 if decimal_val < 0 else 0
    abs_val = abs(decimal_val)
    int_part = int(abs_val)          # 54
    frac_part = abs_val - int_part   # 0.375

    # ---- 十进制转二进制 ----
    int_bin = int_part_to_binary(int_part)
    frac_bin = frac_part_to_binary(frac_part)
    binary_full = f"{int_bin}.{frac_bin}"

    # ---- 规格化：1.xxx × 2^E ----
    # 把整数部分的二进制和小数部分拼成 "1.xxxxx" 形式，阶码=整数部分位数-1
    # 合并整数部分和小数部分为一条 bit 串，再移小数点到第一个 1 后面
    all_bits = int_bin + frac_bin          # "110110.011" -> "110110011"
    # 找到第一个 1 的位置（隐含前导1）
    first_one = all_bits.index("1")
    # 去掉前导零后的纯有效位
    sig_bits = all_bits[first_one:]
    # 规格化后整数部分只有一个 1，其余进小数部分
    mantissa_bits = sig_bits[1:]           # 去掉前导 1
    E = len(int_bin) - first_one - 1      # 阶码真值

    normalized_form = f"1.{mantissa_bits} × 2^{E}"

    # ---- IEEE 754 字段 ----
    S = sign_bit
    exp_field_val = E + bias              # 阶码字段数值
    exp_field_bin = f"{exp_field_val:08b}"  # 8 位阶码

    # 尾数字段取前 23 位，不足补零
    if len(mantissa_bits) >= 23:
        mantissa_field = mantissa_bits[:23]
        # 检查是否需要舍入（本题数据在23位内精确）
        dropped = mantissa_bits[23:]
    else:
        mantissa_field = mantissa_bits + "0" * (23 - len(mantissa_bits))
        dropped = ""

    machine_32 = f"{S}{exp_field_bin}{mantissa_field}"  # 32 位完整

    # 32 位转十六进制
    hex_val = f"{int(machine_32, 2):08X}"

    # ============== 数据流 ==============
    print("=" * 60)
    print("PARAMS:")
    print(f"  输入十进制数   = {decimal_val}")
    print(f"  符号 sign_bit  = {sign_bit}")
    print(f"  绝对值 abs_val = {abs_val}")
    print(f"  整数部分       = {int_part}")
    print(f"  小数部分       = {frac_part}")
    print(f"  bias           = {bias}")
    print()
    print("PROCESS:")
    print(f"  整数部分二进制 (除2取余)  = {int_bin}")
    print(f"  小数部分二进制 (乘2取整)  = {frac_bin}")
    print(f"  合并二进制                 = {binary_full}")
    print(f"  有效位串 sig_bits          = {sig_bits}")
    print(f"  去前导1后 mantissa_bits    = {mantissa_bits}")
    print(f"  阶码真值 E                 = {E}  (= 整数部分位数{len(int_bin)} - 1)")
    print(f"  规格化形式                 = {normalized_form}")
    print(f"  阶码字段值 E+bias          = {exp_field_val}")
    print(f"  阶码字段 8 位二进制        = {exp_field_bin}")
    print(f"  尾数 bits（原始，去隐含1）  = {mantissa_bits}")
    print(f"  尾数字段 23 位（补零后）    = {mantissa_field}")
    print(f"  被截断/舍入位              = '{dropped}' (空=无需舍入)")
    print(f"  32 位机器数                = {machine_32}")
    print(f"  十六进制                   = {hex_val}")
    print()
    print("RESULT:")
    print(f"  S={S}  阶码={exp_field_bin}  尾数={mantissa_field}")
    print(f"  32位机器数 = {machine_32}")
    print(f"  十六进制   = {hex_val}")
    print("=" * 60)

    # ============== 场景规则 assert ==============
    # 规则1: 二进制等价性 —— 二进制还原十进制必须严格等于原始绝对值
    reconstructed = int(int_bin, 2) + sum(
        int(b) * (2 ** -(i + 1)) for i, b in enumerate(frac_bin)
    )
    assert abs(reconstructed - abs_val) < 1e-12, \
        f"规则1失败: 二进制还原={reconstructed} != {abs_val}"
    print(f"规则1 通过: 二进制还原 {reconstructed} == {abs_val}")

    # 规则2: 规格化正确性 —— 小数点左仅1位且为1；E=整数位数-1
    assert sig_bits[0] == "1", "规则2失败: 隐含前导位不是1"
    assert E == len(int_bin) - 1, \
        f"规则2失败: E={E} != 整数位数{len(int_bin)}-1={len(int_bin)-1}"
    print(f"规则2 通过: 隐含前导1=1, E={E}={len(int_bin)}-1")

    # 规则3: 阶码字段 1~254
    assert 1 <= exp_field_val <= 254, \
        f"规则3失败: E+bias={exp_field_val} 不在1~254范围"
    print(f"规则3 通过: E+bias={exp_field_val} 在 1~254 范围内")

    # 规则4: 符号位正确性 —— 负数S=1，阶码尾数取绝对值
    assert S == (1 if decimal_val < 0 else 0), "规则4失败: 符号位与输入符号不符"
    print(f"规则4 通过: 输入为{'负' if decimal_val<0 else '正'}数, S={S}, 字段取绝对值部分")

    # 规则5: 尾数字段恰好23位，且隐含前导1不写入
    assert len(mantissa_field) == 23, \
        f"规则5失败: 尾数字段位数={len(mantissa_field)} != 23"
    assert mantissa_field != sig_bits[:23] or sig_bits[0] != "0", \
        "规则5失败: 检查隐含1未写入"
    # 更直接：尾数字段是 sig_bits 去掉第1位(隐含1)后的前23位
    assert mantissa_field == mantissa_bits[:23].ljust(23, "0"), \
        "规则5失败: 尾数字段内容与去隐含1后不符"
    print(f"规则5 通过: 尾数字段恰好23位, 隐含前导1未写入")

    # 规则6: 32位拼接自洽
    assert len(machine_32) == 32, \
        f"规则6失败: 机器数位数={len(machine_32)} != 32"
    assert machine_32[0] == str(S), "规则6失败: 首位≠符号位"
    assert machine_32[1:9] == exp_field_bin, "规则6失败: 2~9位≠阶码字段"
    assert machine_32[9:32] == mantissa_field, "规则6失败: 10~32位≠尾数字段"
    print(f"规则6 通过: 总位数=32, S(1)+E(8)+M(23)拼接自洽")

    # 规则7: 十六进制与32位二进制一一对应（8位hex）
    assert len(hex_val) == 8, \
        f"规则7失败: 十六进制位数={len(hex_val)} != 8"
    assert int(hex_val, 16) == int(machine_32, 2), \
        "规则7失败: 十六进制值与二进制值不一致"
    print(f"规则7 通过: 十六进制 {hex_val} 与32位二进制严格一一对应")

    return {
        "binary_full": binary_full,
        "normalized_form": normalized_form,
        "E": E,
        "S": S,
        "exp_field_bin": exp_field_bin,
        "mantissa_field": mantissa_field,
        "machine_32": machine_32,
        "hex_val": hex_val,
    }


if __name__ == "__main__":
    result = solve(-54.375, bias=127)
