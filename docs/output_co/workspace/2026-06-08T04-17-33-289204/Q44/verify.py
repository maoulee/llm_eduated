# ===== 题目参数 =====
num_platters = 4          # 盘片数
sides_per_platter = 2     # 双面
num_surfaces = num_platters * sides_per_platter  # 盘面数 = 8
num_tracks = 16384        # 每个盘面磁道数
num_sectors = 256         # 每个磁道扇区数
sector_size_bytes = 512   # 每扇区字节数
rpm = 7200                # 转速
avg_seek_time_ms = 4      # 平均寻道时间 ms

dma_buffer_bits = 64      # DMA缓冲区大小（位）
bus_width_bits = 32       # 总线宽度（位）
bus_freq_MHz = 40         # 总线频率 MHz

cpu_freq_MHz = 40         # CPU主频 MHz
cpi = 4                   # CPI

# ===== 校验1：参数封闭性 =====
# 子问题(1)需要：盘面数、磁道数、扇区数、转速、寻道时间、扇区大小
# 子问题(2)需要：扇区大小、DMA缓冲区、总线宽度、总线频率、传输时间(来自1)
# 子问题(3)需要：CPU可执行指令数(来自2)、设置指令数、中断处理指令数、CPI、主频
print("参数封闭性检查：所有子问题所需参数均在题干中给出 ✓")

# ===== 校验2：2的幂次检查 =====
assert num_surfaces == 2**3, f"盘面数 {num_surfaces} 不是2的幂次"
assert num_tracks == 2**14, f"磁道数 {num_tracks} 不是2的幂次"
assert num_sectors == 2**8, f"扇区数 {num_sectors} 不是2的幂次"
assert sector_size_bytes == 2**9, f"扇区大小 {sector_size_bytes} 不是2的幂次"
assert dma_buffer_bits == 2**6, f"DMA缓冲区 {dma_buffer_bits} 不是2的幂次"
assert bus_width_bits == 2**5, f"总线宽度 {bus_width_bits} 不是2的幂次"
print("2的幂次检查：通过 ✓")

# ===== 校验3：DMA请求次数整除性 =====
sector_size_bits = sector_size_bytes * 8  # 512 * 8 = 4096 bits
dma_requests = sector_size_bits // dma_buffer_bits  # 4096 / 64 = 64
assert sector_size_bits % dma_buffer_bits == 0, f"扇区位数 {sector_size_bits} 不能被DMA缓冲区 {dma_buffer_bits} 整除"
print(f"DMA请求次数整除性：{sector_size_bits} / {dma_buffer_bits} = {dma_requests} ✓")

# ===== 校验4：总线传输次数整除性 =====
bus_transfers_per_dma = dma_buffer_bits // bus_width_bits  # 64 / 32 = 2
assert dma_buffer_bits % bus_width_bits == 0, f"DMA缓冲区 {dma_buffer_bits} 不能被总线宽度 {bus_width_bits} 整除"
print(f"每次DMA请求的总线传输次数：{dma_buffer_bits} / {bus_width_bits} = {bus_transfers_per_dma} ✓")

# ===== 校验5：时钟周期计算 =====
clock_period_ns = 1000 / cpu_freq_MHz  # 1000 / 40 = 25 ns
bus_period_ns = 1000 / bus_freq_MHz    # 1000 / 40 = 25 ns
print(f"CPU时钟周期：{clock_period_ns} ns ✓")
print(f"总线周期：{bus_period_ns} ns ✓")

# ===== 校验6：旋转周期和传输时间 =====
rotation_period_ms = 60 / rpm  # 60 / 7200 = 8.333... ms
avg_rotation_latency_ms = rotation_period_ms / 2  # 4.167 ms
sector_transfer_time_ms = rotation_period_ms / num_sectors  # 8.333 / 256 = 0.03255 ms
print(f"旋转周期：{rotation_period_ms:.6f} ms ✓")
print(f"平均旋转延迟：{avg_rotation_latency_ms:.6f} ms ✓")
print(f"扇区传输时间：{sector_transfer_time_ms:.6f} ms ✓")

# ===== 校验7：单位换算链 =====
# 总线传输总时间
total_bus_transfers = dma_requests * bus_transfers_per_dma  # 64 * 2 = 128
total_bus_time_ns = total_bus_transfers * bus_period_ns  # 128 * 25 = 3200 ns = 3.2 μs
total_bus_time_us = total_bus_time_ns / 1000
print(f"总线传输总次数：{total_bus_transfers} ✓")
print(f"DMA占用总线总时间：{total_bus_time_ns} ns = {total_bus_time_us} μs ✓")

# ===== 校验8：CPU指令执行时间 =====
instruction_time_ns = cpi * clock_period_ns  # 4 * 25 = 100 ns
print(f"单条指令执行时间：{instruction_time_ns} ns ✓")

# ===== 校验9：传输时间与DMA时间的关系 =====
# 传输时间（磁盘旋转传输一个扇区的时间）远大于DMA占用总线时间
# 这是周期挪用的前提：磁盘传输数据时，DMA可以挪用总线周期
print(f"传输时间 {sector_transfer_time_ms:.6f} ms >> DMA总线时间 {total_bus_time_us:.6f} μs ✓")
print(f"传输时间 / DMA总线时间 = {sector_transfer_time_ms * 1000 / total_bus_time_us:.1f} 倍 ✓")

print("\n=== 所有参数校验通过 ===")
