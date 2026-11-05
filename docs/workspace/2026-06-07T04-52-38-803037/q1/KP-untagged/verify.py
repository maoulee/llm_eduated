"""
详细验证 FCFS 和 SJF 非抢占式调度
进程参数：
  P1: 到达0, 服务2
  P2: 到达1, 服务4
  P3: 到达2, 服务1
"""

processes = [
    {"name": "P1", "arrival": 0, "service": 2},
    {"name": "P2", "arrival": 1, "service": 4},
    {"name": "P3", "arrival": 2, "service": 1},
]

print("=" * 60)
print("FCFS 非抢占式调度（按到达时间顺序）")
print("=" * 60)

# FCFS: 按到达时间排序
fcfs_order = sorted(processes, key=lambda p: p["arrival"])
current_time = 0
fcfs_turnaround = []

for p in fcfs_order:
    start = max(current_time, p["arrival"])
    finish = start + p["service"]
    turnaround = finish - p["arrival"]
    fcfs_turnaround.append(turnaround)
    print(f"  {p['name']}: 到达={p['arrival']}, 开始={start}, 完成={finish}, 周转={turnaround}")
    current_time = finish

fcfs_total = sum(fcfs_turnaround)
fcfs_avg = fcfs_total / len(processes)
print(f"  FCFS 总周转 = {fcfs_total}, 平均 = {fcfs_total}/{len(processes)} = {fcfs_avg}")

print()
print("=" * 60)
print("SJF 非抢占式调度（短作业优先，非抢占）")
print("=" * 60)

# SJF 非抢占：每次从已到达但未执行的进程中选服务时间最短的
remaining = list(processes)
current_time = 0
sjf_turnaround = []
sjf_order = []

while remaining:
    # 找出已到达的进程
    available = [p for p in remaining if p["arrival"] <= current_time]
    if not available:
        # 没有进程到达，跳到下一个进程到达时间
        current_time = min(p["arrival"] for p in remaining)
        continue
    # 选服务时间最短的
    chosen = min(available, key=lambda p: p["service"])
    remaining.remove(chosen)
    start = current_time
    finish = start + chosen["service"]
    turnaround = finish - chosen["arrival"]
    sjf_turnaround.append(turnaround)
    sjf_order.append(chosen["name"])
    print(f"  {chosen['name']}: 到达={chosen['arrival']}, 开始={start}, 完成={finish}, 周转={turnaround}")
    current_time = finish

sjf_total = sum(sjf_turnaround)
sjf_avg = sjf_total / len(processes)
print(f"  SJF 调度顺序: {' -> '.join(sjf_order)}")
print(f"  SJF 总周转 = {sjf_total}, 平均 = {sjf_total}/{len(processes)} = {sjf_avg}")

print()
print("=" * 60)
print("差值计算")
print("=" * 60)
diff = fcfs_avg - sjf_avg
print(f"  FCFS平均周转 - SJF平均周转 = {fcfs_avg} - {sjf_avg} = {diff}")
print(f"  正确答案应为: {diff}")

print()
print("=" * 60)
print("选项验证")
print("=" * 60)
options = {"A": 0, "B": 1, "C": 2, "D": 3}
for label, val in options.items():
    marker = " <-- 正确" if val == diff else ""
    print(f"  {label} = {val}{marker}")

print()
print("=" * 60)
print("参数封闭性: 所有参数(到达时间0/1/2, 服务时间2/4/1)均在题干中给出 ✓")
print("整除性: FCFS总周转12÷3=4 ✓, SJF总周转9÷3=3 ✓")
print("选项唯一性: 0,1,2,3 互不相同 ✓")
print("正确答案唯一: 差值=1, 对应选项B ✓")
print("=" * 60)
