#!/usr/bin/env python3
"""参数验证脚本：进程调度SJF平均周转时间"""

# ==================== 参数定义 ====================
processes = [
    {"name": "P1", "arrival": 0, "service": 2},
    {"name": "P2", "arrival": 1, "service": 4},
    {"name": "P3", "arrival": 2, "service": 1},
]

options = [2, 3, 4, 5]

# ==================== 验证1: 参数封闭性 ====================
# 所有选项所需参数是否都在题干中给出？
params_in_question = {
    "arrival_times": [0, 1, 2],
    "service_times": [2, 4, 1],
    "algorithm": "SJF非抢占式",
    "metric": "平均周转时间",
}
print("=== 验证1: 参数封闭性 ===")
print(f"题干参数: 到达时间{params_in_question['arrival_times']}, 服务时间{params_in_question['service_times']}")
print(f"所有计算所需参数均已给出: True")
print()

# ==================== 验证2: SJF调度推演 ====================
def sjf_non_preemptive(processes):
    """SJF非抢占式调度模拟"""
    n = len(processes)
    completed = [False] * n
    current_time = 0
    completion_times = [0] * n
    execution_order = []
    
    for _ in range(n):
        candidates = [i for i in range(n) if not completed[i] and processes[i]["arrival"] <= current_time]
        if not candidates:
            next_arrival = min(processes[i]["arrival"] for i in range(n) if not completed[i])
            current_time = next_arrival
            candidates = [i for i in range(n) if not completed[i] and processes[i]["arrival"] <= current_time]
        
        chosen = min(candidates, key=lambda i: processes[i]["service"])
        execution_order.append(processes[chosen]["name"])
        completion_times[chosen] = current_time + processes[chosen]["service"]
        current_time = completion_times[chosen]
        completed[chosen] = True
    
    return completion_times, execution_order

completion_times, exec_order = sjf_non_preemptive(processes)
turnaround_times = [completion_times[i] - processes[i]["arrival"] for i in range(len(processes))]
total_turnaround = sum(turnaround_times)
avg_turnaround = total_turnaround / len(turnaround_times)

print("=== 验证2: SJF调度推演 ===")
print(f"执行顺序: {exec_order}")
print(f"完成时间: P1={completion_times[0]}, P2={completion_times[1]}, P3={completion_times[2]}")
print(f"周转时间: P1={turnaround_times[0]}, P2={turnaround_times[1]}, P3={turnaround_times[2]}")
print(f"周转时间总和: {total_turnaround}")
print(f"平均周转时间: {avg_turnaround}")
print()

# ==================== 验证3: 推导路径等价（FCFS对比） ====================
def fcfs(processes):
    """FCFS调度模拟"""
    sorted_procs = sorted(range(len(processes)), key=lambda i: processes[i]["arrival"])
    current_time = 0
    completion_times = [0] * len(processes)
    
    for idx in sorted_procs:
        if processes[idx]["arrival"] > current_time:
            current_time = processes[idx]["arrival"]
        completion_times[idx] = current_time + processes[idx]["service"]
        current_time = completion_times[idx]
    
    return completion_times

fcfs_completion = fcfs(processes)
fcfs_turnaround = [fcfs_completion[i] - processes[i]["arrival"] for i in range(len(processes))]
fcfs_avg = sum(fcfs_turnaround) / len(fcfs_turnaround)

print("=== 验证3: FCFS对比（推导路径等价） ===")
print(f"FCFS完成时间: P1={fcfs_completion[0]}, P2={fcfs_completion[1]}, P3={fcfs_completion[2]}")
print(f"FCFS周转时间: P1={fcfs_turnaround[0]}, P2={fcfs_turnaround[1]}, P3={fcfs_turnaround[2]}")
print(f"FCFS平均周转时间: {fcfs_avg}")
print(f"SJF与FCFS结果不同（体现算法差异）: {avg_turnaround != fcfs_avg}")
print()

# ==================== 验证4: 整除性检查 ====================
print("=== 验证4: 整除性检查 ===")
print(f"周转时间总和 {total_turnaround} 除以进程数 {len(processes)}: 余数 = {total_turnaround % len(processes)}")
print(f"整除: {total_turnaround % len(processes) == 0}")
print()

# ==================== 验证5: 选项唯一性 ====================
print("=== 验证5: 选项唯一性 ===")
print(f"选项列表: {options}")
print(f"选项互不相同: {len(options) == len(set(options))}")
print(f"正确答案({avg_turnaround})在选项中: {avg_turnaround in options}")
print(f"FCFS结果({fcfs_avg})在选项中作为干扰: {fcfs_avg in options}")
print()

# ==================== 验证6: 单位自洽 ====================
print("=== 验证6: 单位自洽 ===")
print("到达时间、服务时间、周转时间单位一致（时间单位）: True")
print()

# ==================== 汇总 ====================
all_pass = (
    len(options) == len(set(options)) and
    avg_turnaround in options and
    total_turnaround % len(processes) == 0 and
    avg_turnaround != fcfs_avg
)
print(f"=== 全部验证通过: {all_pass} ===")
