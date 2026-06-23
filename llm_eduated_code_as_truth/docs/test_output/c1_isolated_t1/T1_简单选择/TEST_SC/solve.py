import heapq

# 哈夫曼树构造 + WPL计算
weights = [5, 10, 15, 20, 30]
heap = weights[:]
heapq.heapify(heap)

# 合并过程中累加WPL：每次合并两个节点，它们的权值之和会被计入WPL
# 因为合并后的新节点在后续每向上走一层，这两个子节点的深度都+1
# 所以WPL = 所有中间合并产生的新节点权值之和
wpl = 0
while len(heap) > 1:
    a = heapq.heappop(heap)
    b = heapq.heappop(heap)
    merged = a + b
    wpl += merged
    heapq.heappush(heap, merged)

print(f"WPL: {wpl}")
