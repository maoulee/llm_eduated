# ===== 题目参数 =====
page_sequence = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]

def fifo_simulation(pages, num_frames):
    """FIFO页面置换算法模拟"""
    frames = []  # 当前物理块中的页面（按进入顺序）
    page_table = {}  # 页面 -> 进入时间戳
    fault_count = 0
    time = 0
    
    print(f"\n=== FIFO算法，{num_frames}块物理块 ===")
    
    for page in pages:
        time += 1
        if page in frames:
            # 命中
            print(f"  访问页面 {page}: 命中")
        else:
            # 缺页
            fault_count += 1
            if len(frames) < num_frames:
                # 物理块未满，直接加入
                frames.append(page)
                page_table[page] = time
                print(f"  访问页面 {page}: 缺页! 物理块未满, 直接加入. 当前物理块: {frames}")
            else:
                # 物理块已满，需要置换
                # 找到最早进入的页面
                oldest_page = min(frames, key=lambda p: page_table[p])
                print(f"  访问页面 {page}: 缺页! 置换页面 {oldest_page}(最早进入). 当前物理块: {frames}")
                frames.remove(oldest_page)
                del page_table[oldest_page]
                frames.append(page)
                page_table[page] = time
                print(f"  置换后物理块: {frames}")
    
    return fault_count

def lru_simulation(pages, num_frames):
    """LRU页面置换算法模拟"""
    frames = []  # 当前物理块中的页面（按最近使用顺序，末尾是最近使用的）
    fault_count = 0
    time = 0
    
    print(f"\n=== LRU算法，{num_frames}块物理块 ===")
    
    for page in pages:
        time += 1
        if page in frames:
            # 命中，更新最近使用时间
            frames.remove(page)
            frames.append(page)
            print(f"  访问页面 {page}: 命中. 更新后物理块: {frames}")
        else:
            # 缺页
            fault_count += 1
            if len(frames) < num_frames:
                # 物理块未满，直接加入
                frames.append(page)
                print(f"  访问页面 {page}: 缺页! 物理块未满, 直接加入. 当前物理块: {frames}")
            else:
                # 物理块已满，置换最久未使用的（队首）
                victim = frames.pop(0)
                print(f"  访问页面 {page}: 缺页! 置换页面 {victim}(最久未使用). 当前物理块: {frames}")
                frames.append(page)
                print(f"  置换后物理块: {frames}")
    
    return fault_count

# ===== 子问题验证 =====

# I. FIFO算法，3块物理块
fifo_3 = fifo_simulation(page_sequence, 3)
print(f"\nFIFO(3块) 缺页次数: {fifo_3}")

# II. FIFO算法，4块物理块
fifo_4 = fifo_simulation(page_sequence, 4)
print(f"\nFIFO(4块) 缺页次数: {fifo_4}")

# 检查是否出现Belady异常
print(f"\nFIFO(3块)={fifo_3}, FIFO(4块)={fifo_4}")
if fifo_4 > fifo_3:
    print("出现Belady异常：4块比3块缺页更多")
else:
    print("未出现Belady异常")

# III. LRU算法验证
print("\n" + "="*50)
print("验证LRU不会出现Belady异常")
print("="*50)

lru_2 = lru_simulation(page_sequence, 2)
lru_3 = lru_simulation(page_sequence, 3)
lru_4 = lru_simulation(page_sequence, 4)

print(f"\nLRU(2块) 缺页次数: {lru_2}")
print(f"LRU(3块) 缺页次数: {lru_3}")
print(f"LRU(4块) 缺页次数: {lru_4}")

# 验证LRU缺页次数随物理块增加而减少（或不变）
assert lru_3 <= lru_2, "LRU: 3块缺页应<=2块"
assert lru_4 <= lru_3, "LRU: 4块缺页应<=3块"
print("\nLRU验证通过：缺页次数随物理块增加而减少（或不变）")

# ===== 最终答案 =====
print("\n" + "="*50)
print("最终答案分析")
print("="*50)

# I: FIFO 3块缺页次数是否为9
I_correct = (fifo_3 == 9)
print(f"I. FIFO(3块)缺页次数为9: {'正确' if I_correct else '错误'} (实际: {fifo_3})")

# II: FIFO 4块缺页次数是否比3块更多
II_correct = (fifo_4 > fifo_3)
print(f"II. FIFO(4块)缺页比3块更多: {'正确' if II_correct else '错误'} (3块={fifo_3}, 4块={fifo_4})")

# III: LRU不会出现缺页次数随物理块增加而增多
III_correct = True  # LRU理论上不会出现Belady异常
print(f"III. LRU不会出现Belady异常: {'正确' if III_correct else '错误'}")

# 确定选项
if I_correct and II_correct and not III_correct:
    answer = "A"
elif I_correct and not II_correct and III_correct:
    answer = "B"
elif not I_correct and II_correct and III_correct:
    answer = "C"
elif I_correct and II_correct and III_correct:
    answer = "D"
else:
    answer = "需要重新分析"

print(f"\n正确答案: {answer}")
print(f"  I: {'正确' if I_correct else '错误'}")
print(f"  II: {'正确' if II_correct else '错误'}")
print(f"  III: {'正确' if III_correct else '错误'}")
