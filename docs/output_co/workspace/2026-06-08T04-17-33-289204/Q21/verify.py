# ===== 题目参数 =====
hit_rate = 0.95        # Cache命中率
cache_access_time = 10  # Cache访问时间(ns)
main_memory_access_time = 100  # 主存访问时间(ns)

# ===== 校验1：参数封闭性 =====
# 所有子问题所需参数都在题干中给出：命中率、Cache访问时间、主存访问时间 ✓

# ===== 校验2：参数合理性 =====
assert 0 <= hit_rate <= 1, f"命中率不在[0,1]范围内: {hit_rate}"
assert cache_access_time > 0, f"Cache访问时间必须为正: {cache_access_time}"
assert main_memory_access_time > 0, f"主存访问时间必须为正: {main_memory_access_time}"
assert cache_access_time < main_memory_access_time, "Cache访问时间应小于主存访问时间"

# ===== 校验3：缺失率计算 =====
miss_rate = 1 - hit_rate
print(f"命中率: {hit_rate}")
print(f"缺失率: {miss_rate}")

print("参数校验通过")
