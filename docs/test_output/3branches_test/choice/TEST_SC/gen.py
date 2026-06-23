"""
哈夫曼树WPL计算题参数生成器（修正版）
- 搜索满足约束的叶子权值集合（4个叶子）
- 构造哈夫曼树并计算WPL
- 生成四类选项（正确值 + 三种干扰模式）
"""

import heapq


def build_huffman_tree(weights):
    """
    构造哈夫曼树，返回树结构和各叶子节点的深度
    使用最小堆模拟贪心策略
    """
    node_id = 0
    heap = []
    leaf_depths = {}  # 叶子原始权值 -> 深度
    
    # 初始化叶子节点
    for w in sorted(weights):
        heapq.heappush(heap, (w, node_id, None, None, True, w))
        node_id += 1
    
    # 贪心合并
    while len(heap) > 1:
        w1, id1, left1, right1, is_leaf1, orig1 = heapq.heappop(heap)
        w2, id2, left2, right2, is_leaf2, orig2 = heapq.heappop(heap)
        new_w = w1 + w2
        # 合并后的节点，left/right保存完整子节点元组
        heapq.heappush(heap, (new_w, node_id, (w1, id1, left1, right1, is_leaf1, orig1), (w2, id2, left2, right2, is_leaf2, orig2), False, None))
        node_id += 1
    
    # 从根节点计算深度
    root = heap[0]
    
    def get_depths(node, depth):
        if node is None:
            return
        w, nid, left, right, is_leaf, orig = node
        if is_leaf:
            leaf_depths[orig] = depth
        else:
            get_depths(left, depth + 1)
            get_depths(right, depth + 1)
    
    get_depths(root, 0)
    return leaf_depths


def compute_wpl(weights, depths):
    """计算WPL = Σ(权值 × 深度)"""
    return sum(w * d for w, d in depths.items())


def compute_wpl_off_by_one(weights, depths):
    """干扰项B：深度计数off-by-one（根深度计为1而非0）"""
    return sum(w * (d + 1) for w, d in depths.items())


def compute_wpl_wrong_strategy(weights):
    """
    干扰项C：哈夫曼构造策略错误
    模拟错误策略：每次合并最大的两个权值（而非最小的两个）
    """
    node_id = 0
    # 使用负权值模拟最大堆
    heap = []
    leaf_depths = {}
    
    for w in sorted(weights):
        heapq.heappush(heap, (-w, node_id, None, None, True, w))
        node_id += 1
    
    while len(heap) > 1:
        w1, id1, left1, right1, is_leaf1, orig1 = heapq.heappop(heap)
        w2, id2, left2, right2, is_leaf2, orig2 = heapq.heappop(heap)
        new_w = w1 + w2  # 负值相加
        # 修复：保持完整的6元组结构，避免 get_depths 解包失败
        heapq.heappush(heap, (new_w, node_id, (w1, id1, left1, right1, is_leaf1, orig1), (w2, id2, left2, right2, is_leaf2, orig2), False, None))
        node_id += 1
    
    root = heap[0]
    
    def get_depths(node, depth):
        if node is None:
            return
        w, nid, left, right, is_leaf, orig = node
        if is_leaf:
            leaf_depths[orig] = depth
        else:
            get_depths(left, depth + 1)
            get_depths(right, depth + 1)
    
    get_depths(root, 0)
    return sum(w * d for w, d in leaf_depths.items())


def compute_sum_depths(weights, depths):
    """干扰项D：概念混淆，计算路径长度之和（Σ深度）而非带权路径长度"""
    return sum(d for d in depths.values())


def validate_constraints(weights):
    """验证权值集合是否满足约束"""
    # 约束1：4个叶子节点（题干明确指定 w1-w4）
    if len(weights) != 4:
        return False, "叶子节点数量不为4"
    
    # 约束2：权值不重复
    if len(weights) != len(set(weights)):
        return False, "权值有重复"
    
    # 约束3：权值大小适中（1-20）
    if not all(1 <= w <= 20 for w in weights):
        return False, "权值超出1-20范围"
    
    return True, "通过"


def search_parameters():
    """搜索满足约束的参数"""
    # 候选权值集合（4个叶子，权值不重复，大小适中）
    candidates = [
        [2, 3, 5, 7],
        [3, 5, 7, 10],
        [1, 3, 5, 8],
        [2, 4, 6, 9],
        [4, 6, 8, 10],
        [1, 4, 7, 10],
        [3, 6, 9, 12],
        [2, 5, 8, 11],
        [1, 2, 5, 8],
        [3, 4, 6, 9],
    ]
    
    for weights in candidates:
        valid, msg = validate_constraints(weights)
        if not valid:
            continue
        
        # 构造哈夫曼树
        depths = build_huffman_tree(weights)
        wpl_correct = compute_wpl(weights, depths)
        
        # 计算干扰项
        wpl_b = compute_wpl_off_by_one(weights, depths)
        wpl_c = compute_wpl_wrong_strategy(weights)
        wpl_d = compute_sum_depths(weights, depths)
        
        # 检查选项是否互不相同
        options = {wpl_correct, wpl_b, wpl_c, wpl_d}
        if len(options) != 4:
            print(f"权值{weights}: 选项有重复 {options}，跳过")
            continue
        
        # 检查数值合理性（WPL在20-200之间）
        if not (20 <= wpl_correct <= 200):
            print(f"权值{weights}: WPL={wpl_correct}超出范围，跳过")
            continue
        
        print(f"=== 找到有效参数 ===")
        print(f"叶子权值: {sorted(weights)}")
        print(f"叶子深度: {dict(sorted(depths.items()))}")
        print(f"正确WPL (A): {wpl_correct}")
        print(f"干扰B (off-by-one): {wpl_b}")
        print(f"干扰C (构造错误): {wpl_c}")
        print(f"干扰D (Σ深度): {wpl_d}")
        print(f"选项集合: {sorted(options)}")
        
        # 输出求解数据流
        print("\n=== 求解数据流 ===")
        print(f"weights = {sorted(weights)}")
        print(f"depths = {dict(sorted(depths.items()))}")
        print(f"wpl_correct = {wpl_correct}")
        print(f"wpl_b = {wpl_b}")
        print(f"wpl_c = {wpl_c}")
        print(f"wpl_d = {wpl_d}")
        
        return weights, depths, wpl_correct, wpl_b, wpl_c, wpl_d
    
    return None


if __name__ == "__main__":
    result = search_parameters()
    if result:
        weights, depths, wpl_correct, wpl_b, wpl_c, wpl_d = result
        print("\n=== 最终参数 ===")
        print(f"weights = {sorted(weights)}")
        print(f"option_A = {wpl_correct}")
        print(f"option_B = {wpl_b}")
        print(f"option_C = {wpl_c}")
        print(f"option_D = {wpl_d}")
    else:
        print("未找到满足约束的参数")
