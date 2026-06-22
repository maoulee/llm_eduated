# ===== 题目参数定义 =====
page_sequence = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
frame_sizes = [3, 4]

def fifo_simulation(page_seq, num_frames):
    """
    模拟FIFO页面置换算法
    返回缺页次数和每次访问时的内存状态
    """
    frames = []  # 当前内存中的页面（按进入顺序）
    fault_count = 0
    details = []
    
    for page in page_seq:
        if page in frames:
            # 命中，不缺页
            details.append(f"访问{page}: 命中, 内存={frames}")
        else:
            # 缺页
            fault_count += 1
            if len(frames) < num_frames:
                # 物理块未满，直接放入
                frames.append(page)
                details.append(f"访问{page}: 缺页(空块), 内存={frames}")
            else:
                # 物理块已满，替换最早进入的页面（FIFO）
                frames.pop(0)  # 移除最早进入的
                frames.append(page)
                details.append(f"访问{page}: 缺页(置换), 内存={frames}")
    
    return fault_count, details

# ===== 子问题：物理块数为3时的缺页次数 =====
fault_3, details_3 = fifo_simulation(page_sequence, 3)
print(f"=== 物理块数 = 3 ===")
for d in details_3:
    print(f"  {d}")
print(f"缺页次数: {fault_3}")
print()

# ===== 子问题：物理块数为4时的缺页次数 =====
fault_4, details_4 = fifo_simulation(page_sequence, 4)
print(f"=== 物理块数 = 4 ===")
for d in details_4:
    print(f"  {d}")
print(f"缺页次数: {fault_4}")
print()

# ===== 最终输出 =====
print(f"ANSWER: 物理块数3时缺页{fault_3}次, 物理块数4时缺页{fault_4}次")

# 匹配选项
options = {
    "A": (8, 9),
    "B": (9, 10),
    "C": (9, 9),
    "D": (10, 11)
}
for opt, (f3, f4) in options.items():
    if f3 == fault_3 and f4 == fault_4:
        print(f"匹配选项: {opt}")
