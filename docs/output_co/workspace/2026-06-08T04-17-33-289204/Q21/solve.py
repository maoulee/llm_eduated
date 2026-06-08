# ===== 题目参数定义 =====
hit_rate = 0.95        # Cache命中率
cache_access_time = 10  # Cache访问时间(ns)
main_memory_access_time = 100  # 主存访问时间(ns)

# ===== 子问题：计算平均访问时间 =====
miss_rate = 1 - hit_rate

# 方法1：直接公式
# 命中时：只访问Cache，时间 = cache_access_time
# 缺失时：先访问Cache再访问主存，时间 = cache_access_time + main_memory_access_time
avg_access_time = hit_rate * cache_access_time + miss_rate * (cache_access_time + main_memory_access_time)
print(f"方法1：平均访问时间 = 命中率×命中时间 + 缺失率×(Cache时间+主存时间)")
print(f"  = {hit_rate} × {cache_access_time} + {miss_rate} × ({cache_access_time} + {main_memory_access_time})")
print(f"  = {hit_rate * cache_access_time} + {miss_rate} × {cache_access_time + main_memory_access_time}")
print(f"  = {hit_rate * cache_access_time} + {miss_rate * (cache_access_time + main_memory_access_time)}")
print(f"  答案: {avg_access_time} ns")

# 方法2：等价公式
# 每次访问都要先访问Cache，缺失时额外访问主存
avg_access_time_2 = cache_access_time + miss_rate * main_memory_access_time
print(f"\n方法2：平均访问时间 = Cache时间 + 缺失率×主存时间")
print(f"  = {cache_access_time} + {miss_rate} × {main_memory_access_time}")
print(f"  = {cache_access_time} + {miss_rate * main_memory_access_time}")
print(f"  答案: {avg_access_time_2} ns")

# ===== 最终输出 =====
print(f"\nANSWER: {avg_access_time} ns")
