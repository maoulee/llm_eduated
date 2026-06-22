def solve():
    # ================= 参数定义 =================
    rpm = 7200
    seek_time_ms = 10.0
    sector_size_B = 512
    sectors_per_track = 128
    num_sectors = 16
    dma_bus_time_per_sector_us = 25
    dma_interrupt_us = 60
    pio_time_per_sector_us = 120

    print("=== 磁盘参数与I/O模式参数 ===")
    print(f"转速: {rpm} RPM")
    print(f"平均寻道时间: {seek_time_ms} ms")
    print(f"扇区大小: {sector_size_B} B")
    print(f"每磁道扇区数: {sectors_per_track}")
    print(f"需读取扇区数: {num_sectors}")
    print(f"DMA每扇区总线占用: {dma_bus_time_per_sector_us} μs")
    print(f"DMA中断处理开销: {dma_interrupt_us} μs")
    print(f"PIO每扇区耗时: {pio_time_per_sector_us} μs")
    print()

    # ================= (1) 磁盘物理访问时间 T_disk 与 DMA 总线占用时间 T_bus =================
    print("=== (1) 磁盘物理访问时间 T_disk 与 DMA 总线占用时间 T_bus ===")
    
    # 1. 旋转周期与平均旋转延迟
    t_rot_ms = 60000 / rpm
    t_rot_avg_ms = t_rot_ms / 2
    t_rot_ms_r = round(t_rot_ms, 2)
    t_rot_avg_ms_r = round(t_rot_avg_ms, 2)
    print(f"1. 旋转周期 T_rot = 60000 / {rpm} ≈ {t_rot_ms_r} ms")
    print(f"   平均旋转延迟 T_rot_avg = T_rot / 2 ≈ {t_rot_avg_ms_r} ms")

    # 2. 传输时间
    t_trans_ms = (num_sectors / sectors_per_track) * t_rot_ms
    t_trans_ms_r = round(t_trans_ms, 2)
    print(f"2. 传输时间 T_trans = ({num_sectors} / {sectors_per_track}) × {t_rot_ms_r} ≈ {t_trans_ms_r} ms")

    # 3. 磁盘物理访问时间
    t_disk_ms = seek_time_ms + t_rot_avg_ms_r + t_trans_ms_r
    t_disk_ms_r = round(t_disk_ms, 2)
    print(f"3. 磁盘物理访问时间 T_disk = T_seek + T_rot_avg + T_trans")
    print(f"   T_disk = {seek_time_ms} + {t_rot_avg_ms_r} + {t_trans_ms_r} = {t_disk_ms_r} ms")

    # 4. DMA总线占用总时间
    t_bus_us = num_sectors * dma_bus_time_per_sector_us
    t_bus_ms = t_bus_us / 1000
    t_bus_ms_r = round(t_bus_ms, 2)
    print(f"4. DMA总线占用总时间 T_bus = {num_sectors} × {dma_bus_time_per_sector_us} μs = {t_bus_us} μs = {t_bus_ms_r} ms")
    print(f"   【答案】T_disk = {t_disk_ms_r} ms, T_bus = {t_bus_ms_r} ms")
    print()

    # ================= (2) 有效吞吐率计算与性能分析 =================
    print("=== (2) 有效吞吐率计算与性能分析 ===")
    
    # 1. DMA模式有效吞吐率
    print("1. DMA模式有效吞吐率:")
    t_dma_transfer_ms = max(t_trans_ms_r, t_bus_ms_r)
    t_int_ms = dma_interrupt_us / 1000
    t_int_ms_r = round(t_int_ms, 2)
    t_dma_total_ms = seek_time_ms + t_rot_avg_ms_r + t_dma_transfer_ms + t_int_ms_r
    t_dma_total_ms_r = round(t_dma_total_ms, 2)
    print(f"   - 传输阶段耗时取 max(T_trans, T_bus) = max({t_trans_ms_r}, {t_bus_ms_r}) = {t_dma_transfer_ms} ms")
    print(f"   - DMA总耗时 T_DMA = T_seek + T_rot_avg + max(T_trans, T_bus) + T_int")
    print(f"     T_DMA = {seek_time_ms} + {t_rot_avg_ms_r} + {t_dma_transfer_ms} + {t_int_ms_r} = {t_dma_total_ms_r} ms")
    
    data_size_B = num_sectors * sector_size_B
    throughput_dma_Bps = data_size_B / (t_dma_total_ms_r / 1000)
    throughput_dma_MBs = throughput_dma_Bps / 10**6
    throughput_dma_MBs_r = round(throughput_dma_MBs, 2)
    print(f"   - 数据总量 D = {num_sectors} × {sector_size_B} = {data_size_B} B")
    print(f"   - 有效吞吐率 Throughput_DMA = {data_size_B} / ({t_dma_total_ms_r} × 10^-3) ≈ {throughput_dma_Bps:.0f} B/s ≈ {throughput_dma_MBs_r} MB/s")

    # 2. PIO模式有效吞吐率
    print("2. PIO模式有效吞吐率:")
    t_pio_trans_us = num_sectors * pio_time_per_sector_us
    t_pio_trans_ms = t_pio_trans_us / 1000
    t_pio_trans_ms_r = round(t_pio_trans_ms, 2)
    print(f"   - PIO每扇区耗时 {pio_time_per_sector_us} μs，{num_sectors} 扇区总耗时 T_pio_trans = {num_sectors} × {pio_time_per_sector_us} = {t_pio_trans_us} μs = {t_pio_trans_ms_r} ms")
    t_pio_transfer_ms = max(t_trans_ms_r, t_pio_trans_ms_r)
    t_pio_total_ms = seek_time_ms + t_rot_avg_ms_r + t_pio_transfer_ms
    t_pio_total_ms_r = round(t_pio_total_ms, 2)
    print(f"   - PIO传输阶段耗时取 max(T_trans, T_pio_trans) = max({t_trans_ms_r}, {t_pio_trans_ms_r}) = {t_pio_transfer_ms} ms")
    print(f"   - PIO总耗时 T_PIO = {seek_time_ms} + {t_rot_avg_ms_r} + {t_pio_transfer_ms} = {t_pio_total_ms_r} ms")
    
    throughput_pio_Bps = data_size_B / (t_pio_total_ms_r / 1000)
    throughput_pio_MBs = throughput_pio_Bps / 10**6
    throughput_pio_MBs_r = round(throughput_pio_MBs, 2)
    print(f"   - 有效吞吐率 Throughput_PIO = {data_size_B} / ({t_pio_total_ms_r} × 10^-3) ≈ {throughput_pio_Bps:.0f} B/s ≈ {throughput_pio_MBs_r} MB/s")

    # 3. 性能差异分析
    print("3. 性能差异分析:")
    print(f"   - 两者吞吐率数值接近（{throughput_dma_MBs_r} vs {throughput_pio_MBs_r} MB/s），说明磁盘 I/O 的瓶颈主要在于机械延迟（寻道与旋转），而非 CPU 或总线带宽。")
    print(f"   - DMA 优势：在传输阶段（{t_trans_ms_r} ms），DMA 控制器独立搬运数据，CPU 可并行执行其他进程指令，仅在中断时（{t_int_ms_r} ms）介入，CPU 利用率高，系统并发能力强。")
    print(f"   - PIO 劣势：CPU 需全程参与数据搬运（{t_pio_trans_ms_r} ms），严重占用 CPU 时间片，导致系统整体吞吐量下降，适用于低速设备或数据量极小的场景。")
    print(f"   【答案】DMA 吞吐率约 {throughput_dma_MBs_r} MB/s，PIO 吞吐率约 {throughput_pio_MBs_r} MB/s。差异主因在于 DMA 释放了 CPU，提升了系统并发处理能力，而磁盘机械延迟主导了 I/O 总耗时。")


if __name__ == "__main__":
    solve()
