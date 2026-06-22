def sjf_scheduling(processes):
    """SJF non-preemptive scheduling"""
    n = len(processes)
    completed = [False] * n
    time = 0
    completion_times = [0] * n
    
    while sum(completed) < n:
        # Find ready processes (arrived and not completed)
        ready = []
        for i in range(n):
            if not completed[i] and processes[i][1] <= time:
                ready.append(i)
        
        if not ready:
            # CPU idle, jump to next arrival
            next_arrival = min(processes[i][1] for i in range(n) if not completed[i])
            time = next_arrival
            continue
        
        # Select shortest job
        shortest = min(ready, key=lambda i: processes[i][2])
        burst = processes[shortest][2]
        time += burst
        completion_times[shortest] = time
        completed[shortest] = True
    
    return completion_times

def srtf_scheduling(processes):
    """SRTF preemptive scheduling"""
    n = len(processes)
    remaining = [p[2] for p in processes]
    completed = [False] * n
    completion_times = [0] * n
    time = 0
    
    while sum(completed) < n:
        # Find ready processes
        ready = []
        for i in range(n):
            if not completed[i] and processes[i][1] <= time and remaining[i] > 0:
                ready.append(i)
        
        if not ready:
            next_arrival = min(processes[i][1] for i in range(n) if not completed[i])
            time = next_arrival
            continue
        
        # Select shortest remaining time
        shortest = min(ready, key=lambda i: remaining[i])
        remaining[shortest] -= 1
        time += 1
        
        if remaining[shortest] == 0:
            completed[shortest] = True
            completion_times[shortest] = time
    
    return completion_times

# Process data: (name, arrival, burst)
processes = [
    ('P1', 0, 6),
    ('P2', 2, 2),
    ('P3', 4, 1),
    ('P4', 6, 4),
]

# SJF
sjf_completion = sjf_scheduling(processes)
print("===== SJF =====")
sjf_turnaround = []
for i, (name, arrival, burst) in enumerate(processes):
    ta = sjf_completion[i] - arrival
    sjf_turnaround.append(ta)
    print(f"  {name}: arrival={arrival}, burst={burst}, completion={sjf_completion[i]}, turnaround={ta}")
sjf_avg = sum(sjf_turnaround) / len(sjf_turnaround)
print(f"  SJF avg turnaround: {sjf_avg}")

# SRTF
srtf_completion = srtf_scheduling(processes)
print("\n===== SRTF =====")
srtf_turnaround = []
for i, (name, arrival, burst) in enumerate(processes):
    ta = srtf_completion[i] - arrival
    srtf_turnaround.append(ta)
    print(f"  {name}: arrival={arrival}, burst={burst}, completion={srtf_completion[i]}, turnaround={ta}")
srtf_avg = sum(srtf_turnaround) / len(srtf_turnaround)
print(f"  SRTF avg turnaround: {srtf_avg}")

print(f"\n===== Difference =====")
print(f"  SJF avg: {sjf_avg}")
print(f"  SRTF avg: {srtf_avg}")
print(f"  Difference: {sjf_avg - srtf_avg}")
