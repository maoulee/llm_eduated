# -*- coding: utf-8 -*-
"""
寻找满足通过条件的序列：逆序对∈[3,6]、冒泡>=4趟、8个互不相同正整数[10,99]
"""
import itertools, random

def inversion_count(arr):
    cnt = 0
    for i in range(len(arr)):
        for j in range(i + 1, len(arr)):
            if arr[i] > arr[j]:
                cnt += 1
    return cnt

def bubble_passes(arr):
    a = list(arr)
    cnt = 0
    is_sorted = False
    while not is_sorted:
        is_sorted = True
        for j in range(len(a) - 1):
            if a[j] > a[j+1]:
                a[j], a[j+1] = a[j+1], a[j]
                is_sorted = False
        cnt += 1
        if is_sorted:
            break
    return cnt

results = []
random.seed(42)
pool = list(range(10, 100))
random.shuffle(pool)

# 先枚举随机采样的
for _ in range(200000):
    seq = random.sample(pool, 8)
    inv = inversion_count(seq)
    if 3 <= inv <= 6:
        bp = bubble_passes(seq)
        if bp >= 4:
            results.append((seq, inv, bp))
            if len(results) >= 5:
                break

for seq, inv, bp in results[:5]:
    print(f"seq={seq}  inv={inv}  bubble_passes={bp}")
