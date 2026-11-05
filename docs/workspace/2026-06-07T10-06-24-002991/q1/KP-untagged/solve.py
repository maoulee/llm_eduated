# ===== 题目参数定义 =====
processes = [
    {"name": "P1", "arrival": 0, "service": 6},
    {"name": "P2", "arrival": 2, "service": 2},
    {"name": "P3", "arrival": 4, "service": 1},
    {"name": "P4", "arrival": 6, "service": 4},
]

# ===== SJF（短作业优先，非抢占式）调度 =====
def sjf_schedule(processes):
    n = len(processes)
    remaining = [p.copy() for p in processes]
    completed = []
    current_time = 0
    finished_count = 0
    
    while finished_count < n:
        # 找出当前时刻已到达且未完成的进程中，服务时间最短的
        available = [i for i in range(n) if remaining[i]["arrival"] <= current_time and "done" not in remaining[i]]
        
        if not available:
            # 没有可用进程，跳到下一个进程到达时间
            next_arrival = min(remaining[i]["arrival"] for i in range(n) if "done" not in remaining[i])
            current_time = next_arrival
            continue
        
        # 选择服务时间最短的
        chosen = min(available, key=lambda i: remaining[i]["service"])
        
        # 执行该进程（非抢占，一直执行完）
        start_time = current_time
        current_time += remaining[chosen]["service"]
        remaining[chosen]["done"] = True
        remaining[chosen]["completion"] = current_time
        remaining[chosen]["start"] = start_time
        finished_count += 1
    
    return remaining

# ===== SRTN（最短剩余时间优先，抢占式）调度 =====
def srtf_schedule(processes):
    n = len(processes)
    remaining_time = [p["service"] for p in processes]
    completion_time = [None] * n
    current_time = 0
    finished_count = 0
    running = -1  # 当前运行的进程索引
    
    while finished_count < n:
        # 找出当前时刻已到达且未完成的进程
        available = [i for i in range(n) if processes[i]["arrival"] <= current_time and remaining_time[i] > 0]
        
        if not available:
            # 没有可用进程，跳到下一个进程到达时间
            next_arrival = min(processes[i]["arrival"] for i in range(n) if remaining_time[i] > 0)
            current_time = next_arrival
            continue
        
        # 选择剩余时间最短的
        chosen = min(available, key=lambda i: remaining_time[i])
        
        # 执行1个时间单位
        remaining_time[chosen] -= 1
        current_time += 1
        
        if remaining_time[chosen] == 0:
            completion_time[chosen] = current_time
            finished_count += 1
    
    return completion_time

# ===== 计算SJF =====
sjf_result = sjf_schedule(processes)
print("===== SJF 调度结果 =====")
sjf_turnaround = []
for p in sjf_result:
    ta = p["completion"] - p["arrival"]
    sjf_turnaround.append(ta)
    print(f"  {p['name']}: 到达={p['arrival']}, 服务={p['service']}, 完成={p['completion']}, 周转={ta}")

sjf_avg = sum(sjf_turnaround) / len(sjf_turnaround)
print(f"  SJF 平均周转时间: {sjf_avg}")

# ===== 计算SRTN =====
srtf_completion = srtf_schedule(processes)
print("\n===== SRTN 调度结果 =====")
srtf_turnaround = []
for i, p in enumerate(processes):
    ta = srtf_completion[i] - p["arrival"]
    srtf_turnaround.append(ta)
    print(f"  {p['name']}: 到达={p['arrival']}, 服务={p['service']}, 完成={srtf_completion[i]}, 周转={ta}")

srtf_avg = sum(srtf_turnaround) / len(srtf_turnaround)
print(f"  SRTN 平均周转时间: {srtf_avg}")

# ===== 计算差值 =====
diff = abs(sjf_avg - srtf_avg)
print(f"\n===== 最终结果 =====")
print(f"  SJF 平均周转时间: {sjf_avg}")
print(f"  SRTN 平均周转时间: {srtf_avg}")
print(f"  两者之差: {diff}")
