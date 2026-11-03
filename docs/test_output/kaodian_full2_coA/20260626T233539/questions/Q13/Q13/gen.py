"""
字位同时扩展——芯片数量计算
题干规则逐句翻译为代码，底部打印完整数据流供审核对照场景规则。

场景规则（通过条件）：
  R1 容量自洽: 目标字数 = C_target_bytes / (B_target / 8)
  R2 整除约束: B_target % B_chip == 0 且 目标字数 % W_chip == 0
  R3 地址线数 = log2(目标字数)  （按字编址）
  R4 数据线数 = B_target
  R5 芯片组数 G = 目标字数 / W_chip，G >= 2
  R6 每组芯片数 P = B_target / B_chip，P >= 2
  R7 总芯片数 = G * P
  R8 总量校验: G * W_chip == 目标字数 且 P * B_chip == B_target
"""

import math


def solve(C_target_bytes, B_target, W_chip, B_chip):
    # ---- 翻译场景规则（参数间约束忠实实现）----
    # R1 容量自洽：目标字数 = 容量字节数 ÷ 每字字节数
    bytes_per_word = B_target // 8          # 每字字节数 = 位宽 / 8
    target_words = C_target_bytes // bytes_per_word

    # R2 整除约束：建模时验证（换参数若不满足则本题为非法参数）
    assert B_target % B_chip == 0, "R2违反: B_target 不能被 B_chip 整除"
    assert target_words % W_chip == 0, "R2违反: 目标字数不能被芯片字数整除"

    # R3 地址线数 = log2(目标字数)（按字编址，每字一个地址）
    assert (target_words & (target_words - 1)) == 0, "R3前提: 目标字数须为2的幂（地址线取整数log2）"
    addr_lines = int(math.log2(target_words))

    # R4 数据线数 = B_target
    data_lines = B_target

    # R5 芯片组数（字扩展）= 目标字数 / 芯片字数，G >= 2
    G = target_words // W_chip
    assert G >= 2, "R5违反: 芯片组数 G < 2（无字扩展）"

    # R6 每组芯片数（位扩展）= B_target / B_chip，P >= 2
    P = B_target // B_chip
    assert P >= 2, "R6违反: 每组芯片数 P < 2（无位扩展）"

    # R7 总芯片数 = G × P
    total_chips = G * P

    # R8 总量校验：字扩展覆盖全部目标字数，位扩展覆盖全部目标位宽
    assert G * W_chip == target_words, "R8违反: 字扩展未覆盖全部目标字数"
    assert P * B_chip == B_target, "R8违反: 位扩展未覆盖全部目标位宽"

    return {
        "target_words": target_words,
        "addr_lines": addr_lines,
        "data_lines": data_lines,
        "G": G,
        "P": P,
        "total_chips": total_chips,
    }


# ---- 注入题干参数 ----
C_target_bytes = 64 * 1024   # 64KB = 65536 字节
B_target = 16                # 数据总线 16 位
W_chip = 8 * 1024            # 8K = 8192 字
B_chip = 8                   # 8 位

res = solve(C_target_bytes, B_target, W_chip, B_chip)

# ---- 底部：打印完整数据流（审核对照8条场景规则）----
print("=" * 60)
print("PARAMS:")
print("  C_target_bytes =", C_target_bytes, "(64KB)")
print("  B_target       =", B_target, "位 (数据总线宽度)")
print("  W_chip         =", W_chip, "(8K, 芯片字数)")
print("  B_chip         =", B_chip, "位 (芯片位宽)")

print("-" * 60)
print("PROCESS / 中间值:")
print("  每字字节数 bytes_per_word = B_target/8 =", B_target, "// 8 =", B_target // 8)
print("  [R1] 目标字数 = C_target_bytes / bytes_per_word =", C_target_bytes, "/", B_target // 8, "=", res["target_words"], "= 32K")
print("  [R2] B_target % B_chip = 16 % 8 =", 16 % 8, "（整除）")
print("  [R2] 目标字数 % W_chip = 32768 % 8192 =", 32768 % 8192, "（整除）")
print("  [R3] 地址线数 = log2(32768) =", res["addr_lines"])
print("  [R4] 数据线数 = B_target =", res["data_lines"])
print("  [R5] 芯片组数 G = 目标字数 / W_chip = 32768 / 8192 =", res["G"])
print("  [R6] 每组芯片数 P = B_target / B_chip = 16 / 8 =", res["P"])
print("  [R7] 总芯片数 = G × P =", res["G"], "×", res["P"], "=", res["total_chips"])

print("-" * 60)
print("RESULT:")
print("  (1) 地址线 =", res["addr_lines"], "根, 数据线 =", res["data_lines"], "根")
print("  (2) 芯片组数 G =", res["G"], ", 每组芯片数 P =", res["P"])
print("  (3) 总芯片数 =", res["total_chips"], "片")

print("-" * 60)
print("RULE_CHECK（对照8条场景规则，全部须成立）:")
print("  R1 容量自洽: 65536 / (16/8) =", 65536 // 2, "== 目标字数", res["target_words"], "→", 65536 // 2 == res["target_words"])
print("  R2 整除约束: 16%8==", 16 % 8, "且 32768%8192==", 32768 % 8192, "→", (16 % 8 == 0) and (32768 % 8192 == 0))
print("  R3 地址线:   log2(32768) =", res["addr_lines"], "→", 2**res["addr_lines"] == 32768)
print("  R4 数据线:   B_target =", B_target, "== 数据线", res["data_lines"], "→", B_target == res["data_lines"])
print("  R5 G>=2:     G =", res["G"], "→", res["G"] >= 2)
print("  R6 P>=2:     P =", res["P"], "→", res["P"] >= 2)
print("  R7 总芯片:   G*P =", res["G"] * res["P"], "==", res["total_chips"], "→", res["G"] * res["P"] == res["total_chips"])
print("  R8 总量校验: G*W_chip =", res["G"] * W_chip, "== 目标字数", res["target_words"],
      "→", res["G"] * W_chip == res["target_words"],
      "; P*B_chip =", res["P"] * B_chip, "== B_target", B_target,
      "→", res["P"] * B_chip == B_target)
print("=" * 60)
