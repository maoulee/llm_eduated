# ===== 题目参数定义 =====
processes = [
    {"name": "P1", "arrival": 0, "service": 8},
    {"name": "P2", "arrival": 2, "service": 2},
    {"name": "P3", "arrival": 3, "service": 5},
    {"name": "P4", "arrival": 5, "service": 1},
]

# ===== FCFS 调度 =====
print("=" * 50)
print("FCFS 调度过程")
print("=" * 50)

# FCFS: 按到达时间顺序执行
fcfs_order = sorted(processes, key=lambda p: p["arrival"])
current_time = 0
fcfs_turnaround = []

for p in fcfs_order:
    # 如果当前时间小于到达时间，需要等待
    if current_time < p["arrival"]:
        current_time = p["arrival"]
    start_time = current_time
    finish_time = start_time + p["service"]
    turnaround = finish_time - p["arrival"]
    fcfs_turnaround.append(turnaround)
    print(f"  {p['name']}: 到达={p['arrival']}, 服务={p['service']}, "
          f"开始={start_time}, 完成={finish_time}, 周转={turnaround}")
    current_time = finish_time

fcfs_avg = sum(fcfs_turnaround) / len(fcfs_turnaround)
print(f"  FCFS 平均周转时间 = {sum(fcfs_turnaround)}/{len(fcfs_turnaround)} = {fcfs_avg}")

# ===== SRTF 调度 =====
print("\n" + "=" * 50)
print("SRTF 调度过程")
print("=" * 50)

# SRTF: 最短剩余时间优先（抢占式）
# 复制进程数据，跟踪剩余时间
srtf_procs = []
for p in processes:
    srtf_procs.append({
        "name": p["name"],
        "arrival": p["arrival"],
        "remaining": p["service"],
        "service": p["service"],
        "finished": False,
        "finish_time": None
    })

current_time = 0
completed = 0
total = len(srtf_procs)
srtf_turnaround = []

# 模拟每个时间单位
time_log = []
while completed < total:
    # 找出当前已到达且未完成的进程中剩余时间最短的
    available = [p for p in srtf_procs 
                 if p["arrival"] <= current_time and not p["finished"]]
    
    if not available:
        # 没有可用进程，跳到下一个到达时间
        next_arrival = min(p["arrival"] for p in srtf_procs if not p["finished"])
        current_time = next_arrival
        continue
    
    # 选择剩余时间最短的进程
    current_proc = min(available, key=lambda p: p["remaining"])
    
    # 执行1个时间单位
    current_proc["remaining"] -= 1
    current_time += 1
    
    if current_proc["remaining"] == 0:
        current_proc["finished"] = True
        current_proc["finish_time"] = current_time
        turnaround = current_time - current_proc["arrival"]
        srtf_turnaround.append(turnaround)
        completed += 1
        print(f"  时间{current_time-1}->{current_time}: 执行{current_proc['name']} "
              f"(剩余从{current_proc['remaining']+1}到0), {current_proc['name']}完成, "
              f"周转时间={turnaround}")
    else:
        # 检查是否有新进程到达且剩余时间更短（抢占判断）
        newly_arrived = [p for p in srtf_procs 
                         if p["arrival"] == current_time and not p["finished"]]
        if newly_arrived:
            shortest_new = min(newly_arrived, key=lambda p: p["remaining"])
            if shortest_new["remaining"] < current_proc["remaining"]:
                print(f"  时间{current_time-1}->{current_time}: 执行{current_proc['name']} "
                      f"(剩余从{current_proc['remaining']+1}到{current_proc['remaining']}), "
                      f"{shortest_new['name']}到达(剩余{shortest_new['remaining']}), 发生抢占")
            else:
                print(f"  时间{current_time-1}->{current_time}: 执行{current_proc['name']} "
                      f"(剩余从{current_proc['remaining']+1}到{current_proc['remaining']}), "
                      f"{shortest_new['name']}到达但不抢占")
        else:
            print(f"  时间{current_time-1}->{current_time}: 执行{current_proc['name']} "
                  f"(剩余从{current_proc['remaining']+1}到{current_proc['remaining']})")

srtf_avg = sum(srtf_turnaround) / len(srtf_turnaround)
print(f"  SRTF 平均周转时间 = {sum(srtf_turnaround)}/{len(srtf_turnaround)} = {srtf_avg}")

# ===== 比较 =====
print("\n" + "=" * 50)
print("结果对比")
print("=" * 50)
diff = fcfs_avg - srtf_avg
print(f"  FCFS 平均周转时间: {fcfs_avg}")
print(f"  SRTF 平均周转时间: {srtf_avg}")
print(f"  差值 (FCFS - SRTF): {diff}")
print(f"  SRTF 比 FCFS 少: {diff}")

# 验证选项
print(f"\n  选项A (少1.25): {'匹配' if abs(diff - 1.25) < 0.01 else '不匹配'}")
print(f"  选项B (少2.75): {'匹配' if abs(diff - 2.75) < 0.01 else '不匹配'}")
print(f"  选项C (少3.25): {'匹配' if abs(diff - 3.25) < 0.01 else '不匹配'}")
print(f"  选项D (少3.00): {'匹配' if abs(diff - 3.00) < 0.01 else '不匹配'}")
