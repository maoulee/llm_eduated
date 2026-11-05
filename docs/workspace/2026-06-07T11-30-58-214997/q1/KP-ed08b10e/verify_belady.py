"""验证Belady异常场景的页面置换推演"""

def fifo(page_sequence, num_frames):
    """FIFO页面置换，返回缺页次数和每次状态"""
    frames = []
    faults = 0
    details = []
    
    for page in page_sequence:
        if page in frames:
            details.append(f"访问{page}: 命中, 状态={frames.copy()}")
        else:
            faults += 1
            if len(frames) < num_frames:
                frames.append(page)
            else:
                frames.pop(0)  # 淘汰最先进入的
                frames.append(page)
            details.append(f"访问{page}: 缺页, 状态={frames.copy()}")
    
    return faults, details

def lru(page_sequence, num_frames):
    """LRU页面置换，返回缺页次数"""
    frames = []  # 索引越大越最近使用
    faults = 0
    
    for page in page_sequence:
        if page in frames:
            frames.remove(page)
            frames.append(page)
        else:
            faults += 1
            if len(frames) < num_frames:
                frames.append(page)
            else:
                frames.pop(0)  # 淘汰最久未使用的
                frames.append(page)
    
    return faults

# 经典Belady异常序列
seq = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]

print("=== 页面访问序列 ===")
print(seq)
print()

for n in [3, 4]:
    faults, details = fifo(seq, n)
    print(f"=== {n}块 FIFO ===")
    for d in details:
        print(d)
    print(f"缺页次数: {faults}")
    print()

print("=== LRU验证（不会出现Belady异常）===")
for n in [3, 4]:
    faults = lru(seq, n)
    print(f"{n}块 LRU 缺页次数: {faults}")
