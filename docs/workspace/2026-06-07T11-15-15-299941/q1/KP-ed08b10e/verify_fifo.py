def fifo_simulation(sequence, num_frames):
    memory = []
    faults = 0
    for page in sequence:
        if page in memory:
            pass  # hit
        else:
            faults += 1
            if len(memory) < num_frames:
                memory.append(page)
            else:
                memory.pop(0)  # FIFO: remove oldest
                memory.append(page)
    return faults

sequence = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
faults_3 = fifo_simulation(sequence, 3)
faults_4 = fifo_simulation(sequence, 4)
print(f"物理块数3: 缺页{faults_3}次")
print(f"物理块数4: 缺页{faults_4}次")
print(f"答案: {faults_3}和{faults_4}")
