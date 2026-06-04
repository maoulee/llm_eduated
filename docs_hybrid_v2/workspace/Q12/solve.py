import math

# ===== 题目参数定义 =====
main_memory_address_bits = 32          # 主存地址位数
cache_total_lines = 128                # Cache 共有 128 行
main_memory_block_size_bytes = 64      # 每个主存块大小为 64B
access_address = 0x1234ABCD            # 本次访问的主存地址

options = {
    "A": {"cache_line_number": 47, "tag_bits": 19},
    "B": {"cache_line_number": 47, "tag_bits": 25},
    "C": {"cache_line_number": 45, "tag_bits": 19},
    "D": {"cache_line_number": 95, "tag_bits": 18},
}

# ===== 基本参数校验与字段位数计算 =====
offset_bits = int(math.log2(main_memory_block_size_bytes))
index_bits = int(math.log2(cache_total_lines))
tag_bits = main_memory_address_bits - index_bits - offset_bits

print("===== Cache 地址划分计算 =====")
print(f"主存地址位数: {main_memory_address_bits}")
print(f"Cache 行数: {cache_total_lines}")
print(f"主存块大小: {main_memory_block_size_bytes}B")
print(f"访问地址: 0x{access_address:08X}")
print(f"Offset 位数 = log2({main_memory_block_size_bytes}) = {offset_bits}")
print(f"Index 位数 = log2({cache_total_lines}) = {index_bits}")
print(f"Tag 位数 = {main_memory_address_bits} - {index_bits} - {offset_bits} = {tag_bits}")

# ===== Cache 行号计算 =====
main_memory_block_number = access_address >> offset_bits
cache_line_number_by_mod = main_memory_block_number % cache_total_lines
index_mask = cache_total_lines - 1
cache_line_number_by_bits = (access_address >> offset_bits) & index_mask

print()
print("===== Cache 行号计算 =====")
print(f"主存块号 = 地址 >> Offset位数 = 0x{access_address:08X} >> {offset_bits} = {main_memory_block_number}")
print(f"直接映射 Cache 行号 = 主存块号 mod Cache行数 = {main_memory_block_number} mod {cache_total_lines} = {cache_line_number_by_mod}")
print(f"Index 掩码 = Cache行数 - 1 = {cache_total_lines} - 1 = 0x{index_mask:X}")
print(f"按位提取 Index = (0x{access_address:08X} >> {offset_bits}) & 0x{index_mask:X} = {cache_line_number_by_bits}")
print(f"Cache 行号二进制 = {cache_line_number_by_bits:0{index_bits}b}")

# ===== 逐选项验证 =====
computed_answer = {
    "cache_line_number": cache_line_number_by_bits,
    "tag_bits": tag_bits,
}

print()
print("===== 逐选项验证 =====")
correct_letters = []

for option_letter, option_value in options.items():
    option_cache_line_number = option_value["cache_line_number"]
    option_tag_bits = option_value["tag_bits"]

    cache_line_match = option_cache_line_number == computed_answer["cache_line_number"]
    tag_bits_match = option_tag_bits == computed_answer["tag_bits"]
    option_is_correct = cache_line_match and tag_bits_match

    print(f"选项 {option_letter}: 行号={option_cache_line_number}, Tag位数={option_tag_bits}")
    print(f"  行号验证: {option_cache_line_number} == {computed_answer['cache_line_number']} -> {cache_line_match}")
    print(f"  Tag位数验证: {option_tag_bits} == {computed_answer['tag_bits']} -> {tag_bits_match}")
    print(f"  选项 {option_letter} 是否正确: {option_is_correct}")

    if option_is_correct:
        correct_letters.append(option_letter)

# ===== 最终答案 =====
if len(correct_letters) != 1:
    raise ValueError(f"正确选项数量异常: {correct_letters}")

final_answer = correct_letters[0]
print()
print(f"最终计算结果: Cache行号={computed_answer['cache_line_number']}, Tag字段位数={computed_answer['tag_bits']}")
print(f"ANSWER: {final_answer}")
