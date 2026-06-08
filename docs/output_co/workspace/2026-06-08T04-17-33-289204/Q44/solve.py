from fractions import Fraction

# ===== 题目参数定义 =====
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

# ===== 基础计算 =====
# CPU时钟周期（ns）
clock_period_ns = Fraction(1000, cpu_freq_MHz)  # 25 ns
# 总线周期（ns）
bus_period_ns = Fraction(1000, bus_freq_MHz)    # 25 ns
# 单条指令执行时间（ns）
instruction_time_ns = cpi * clock_period_ns     # 100 ns

# 旋转周期（秒）
rotation_period_s = Fraction(60, rpm)           # 1/120 秒
# 旋转周期（ns）
rotation_period_ns = rotation_period_s * 10**9  # 8333333.333 ns
# 平均旋转延迟（ns）
avg_rotation_latency_ns = rotation_period_ns / 2  # 4166666.667 ns
# 平均旋转延迟（ms）
avg_rotation_latency_ms = avg_rotation_latency_ns / 10**6

# 扇区传输时间（ns）
sector_transfer_time_ns = rotation_period_ns / num_sectors  # 32552.083 ns
# 扇区传输时间（ms）
sector_transfer_time_ms = sector_transfer_time_ns / 10**6

# 平均寻道时间（ns）
avg_seek_time_ns = avg_seek_time_ms * 10**6  # 4000000 ns

# ===== 子问题(1) =====
print("=" * 60)
print("子问题(1): 磁盘地址字段位数和平均存取时间")
print("=" * 60)

# 地址字段位数
import math
surface_bits = math.ceil(math.log2(num_surfaces))  # 3位
track_bits = math.ceil(math.log2(num_tracks))       # 14位
sector_bits = math.ceil(math.log2(num_sectors))     # 8位

print(f"  盘面号字段: {num_surfaces}个盘面 → {surface_bits}位")
print(f"  磁道号字段: {num_tracks}个磁道 → {track_bits}位")
print(f"  扇区号字段: {num_sectors}个扇区 → {sector_bits}位")

# 平均存取时间
avg_access_time_ns = avg_seek_time_ns + avg_rotation_latency_ns + sector_transfer_time_ns
avg_access_time_ms = avg_access_time_ns / 10**6

print(f"\n  平均寻道时间: {avg_seek_time_ms} ms")
print(f"  平均旋转延迟: {float(avg_rotation_latency_ms):.4f} ms")
print(f"  传输时间: {float(sector_transfer_time_ms):.6f} ms")
print(f"  平均存取时间: {float(avg_access_time_ms):.4f} ms")

# ===== 子问题(2) =====
print("\n" + "=" * 60)
print("子问题(2): DMA总线请求次数、占用总线时间、CPU可执行指令条数")
print("=" * 60)

# DMA请求次数
sector_size_bits = sector_size_bytes * 8  # 4096 bits
dma_requests = sector_size_bits // dma_buffer_bits  # 64次
print(f"  扇区大小: {sector_size_bytes}字节 = {sector_size_bits}位")
print(f"  每次DMA请求传输: {dma_buffer_bits}位")
print(f"  DMA总线请求次数: {sector_size_bits} / {dma_buffer_bits} = {dma_requests}次")

# 每次DMA请求的总线传输次数
bus_transfers_per_dma = dma_buffer_bits // bus_width_bits  # 2次
total_bus_transfers = dma_requests * bus_transfers_per_dma  # 128次
print(f"  每次DMA请求的总线传输次数: {dma_buffer_bits} / {bus_width_bits} = {bus_transfers_per_dma}次")
print(f"  总线传输总次数: {dma_requests} × {bus_transfers_per_dma} = {total_bus_transfers}次")

# DMA占用总线时间
dma_bus_time_ns = total_bus_transfers * bus_period_ns  # 3200 ns
dma_bus_time_us = dma_bus_time_ns / 1000
print(f"  DMA占用总线时间: {total_bus_transfers} × {float(bus_period_ns)} ns = {float(dma_bus_time_ns)} ns = {float(dma_bus_time_us)} μs")

# CPU可执行指令条数（周期挪用方式）
# 在传输时间内，CPU在DMA不占用总线时可以执行指令
cpu_available_time_ns = sector_transfer_time_ns - dma_bus_time_ns
cpu_instructions_during_transfer = int(cpu_available_time_ns / instruction_time_ns)
print(f"\n  传输时间: {float(sector_transfer_time_ns):.4f} ns")
print(f"  DMA占用总线时间: {float(dma_bus_time_ns)} ns")
print(f"  CPU可用时间: {float(cpu_available_time_ns):.4f} ns")
print(f"  单条指令执行时间: {float(instruction_time_ns)} ns")
print(f"  CPU可执行指令条数: {float(cpu_available_time_ns):.4f} / {float(instruction_time_ns)} = {float(cpu_available_time_ns / instruction_time_ns):.4f} → {cpu_instructions_during_transfer}条")

# ===== 子问题(3) =====
print("\n" + "=" * 60)
print("子问题(3): 总时间和CPU利用率")
print("=" * 60)

# 设置DMA控制器指令数
setup_instructions = 100
# 处理结束中断指令数
interrupt_instructions = 50

# 各阶段时间（ns）
setup_time_ns = setup_instructions * instruction_time_ns  # 10000 ns
transfer_time_ns = sector_transfer_time_ns  # 32552.083 ns
interrupt_time_ns = interrupt_instructions * instruction_time_ns  # 5000 ns

# 总时间
total_time_ns = setup_time_ns + transfer_time_ns + interrupt_time_ns
total_time_us = total_time_ns / 1000

# CPU执行时间
cpu_busy_time_ns = setup_time_ns + cpu_available_time_ns + interrupt_time_ns
cpu_busy_time_us = cpu_busy_time_ns / 1000

# CPU利用率
cpu_utilization = cpu_busy_time_ns / total_time_ns

print(f"  设置DMA时间: {setup_instructions} × {float(instruction_time_ns)} ns = {float(setup_time_ns)} ns = {float(setup_time_ns/1000)} μs")
print(f"  DMA传输时间: {float(transfer_time_ns):.4f} ns = {float(transfer_time_ns/1000):.4f} μs")
print(f"  处理中断时间: {interrupt_instructions} × {float(instruction_time_ns)} ns = {float(interrupt_time_ns)} ns = {float(interrupt_time_ns/1000)} μs")
print(f"\n  总时间: {float(total_time_ns):.4f} ns = {float(total_time_us):.4f} μs")
print(f"  CPU执行时间: {float(cpu_busy_time_ns):.4f} ns = {float(cpu_busy_time_us):.4f} μs")
print(f"  CPU利用率: {float(cpu_busy_time_ns):.4f} / {float(total_time_ns):.4f} = {float(cpu_utilization):.6f} = {float(cpu_utilization * 100):.2f}%")

# ===== 最终输出 =====
print("\n" + "=" * 60)
print("最终答案汇总")
print("=" * 60)
print(f"(1) 盘面号: {surface_bits}位, 磁道号: {track_bits}位, 扇区号: {sector_bits}位")
print(f"    平均存取时间: {float(avg_access_time_ms):.4f} ms")
print(f"(2) DMA总线请求次数: {dma_requests}次")
print(f"    DMA占用总线时间: {float(dma_bus_time_us)} μs")
print(f"    CPU可执行指令条数: {cpu_instructions_during_transfer}条")
print(f"(3) 总时间: {float(total_time_us):.4f} μs")
print(f"    CPU利用率: {float(cpu_utilization * 100):.2f}%")
