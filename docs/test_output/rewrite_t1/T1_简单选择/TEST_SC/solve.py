import heapq

weights = [3, 5, 7, 8, 12]

# Build Huffman tree using min-heap
# Each element: (weight, is_leaf, children_depth_info)
# We'll track depth of each leaf

heap = []
for w in weights:
    heapq.heappush(heap, (w, [w]))  # (combined_weight, list_of_leaf_weights)

# Merge nodes
while len(heap) > 1:
    w1, leaves1 = heapq.heappop(heap)
    w2, leaves2 = heapq.heappop(heap)
    combined = w1 + w2
    new_leaves = leaves1 + leaves2
    heapq.heappush(heap, (combined, new_leaves))

# The final tree root
total_weight, all_leaves = heap[0]

# Now compute WPL by tracking depths
# Rebuild with depth tracking
heap2 = []
for w in weights:
    heapq.heappush(heap2, (w, [(w, 0)]))  # (combined_weight, list_of (leaf_weight, depth))

while len(heap2) > 1:
    w1, items1 = heapq.heappop(heap2)
    w2, items2 = heapq.heappop(heap2)
    combined = w1 + w2
    # Increase depth by 1 for all leaves in both subtrees
    new_items = [(lw, d+1) for lw, d in items1] + [(lw, d+1) for lw, d in items2]
    heapq.heappush(heap2, (combined, new_items))

_, final_items = heap2[0]
wpl = sum(lw * d for lw, d in final_items)

print(f"WPL: {wpl}")
print(f"Details: {final_items}")
