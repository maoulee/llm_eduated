import heapq

# Huffman tree construction to compute WPL
weights = [2, 3, 4, 5, 7, 9]

# Use a min-heap: each element is (weight, depth_contribution)
# We build the tree and compute WPL

# Approach: simulate Huffman tree, track WPL
# WPL = sum of (leaf_weight * leaf_depth)

# Build tree using heap of (weight, node_id)
# Each node: (weight, children)
nodes = []
heap = []
for w in weights:
    heapq.heappush(heap, (w, len(nodes)))
    nodes.append({'weight': w, 'left': None, 'right': None})

while len(heap) > 1:
    w1, id1 = heapq.heappop(heap)
    w2, id2 = heapq.heappop(heap)
    new_w = w1 + w2
    new_id = len(nodes)
    nodes.append({'weight': new_w, 'left': id1, 'right': id2})
    heapq.heappush(heap, (new_w, new_id))

root_id = heap[0][1]

# Compute WPL: sum of weight * depth for all leaves
def compute_wpl(node_id, depth):
    node = nodes[node_id]
    if node['left'] is None and node['right'] is None:
        return node['weight'] * depth
    total = 0
    total += compute_wpl(node['left'], depth + 1)
    total += compute_wpl(node['right'], depth + 1)
    return total

wpl = compute_wpl(root_id, 0)
print(f"正确: {wpl}")
