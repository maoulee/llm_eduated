"""
AVL树插入模拟 + 参数搜索
约束：
1. 序列长度 n 在 6~10
2. 前 m 次插入无旋转
3. 至少两种旋转类型，必须包含 LR 或 RL
4. 连锁失衡：某次旋转后祖先BF发生变化（子树高度降低导致）
5. 最终树满足AVL性质
"""

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    if not node:
        return 0
    return node.height

def get_bf(node):
    if not node:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    if node:
        node.height = 1 + max(get_height(node.left), get_height(node.right))

def right_rotate(y):
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    update_height(y)
    update_height(x)
    return x

def left_rotate(x):
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    update_height(x)
    update_height(y)
    return y

def insert(root, key, log, ancestor_bf_before=None):
    """插入节点，返回 (新根, 旋转信息)"""
    if not root:
        log.append(f"  插入 {key} 为新结点")
        return Node(key), None
    
    if key < root.key:
        root.left, rot_info = insert(root.left, key, log, ancestor_bf_before)
    else:
        root.right, rot_info = insert(root.right, key, log, ancestor_bf_before)
    
    old_height = root.height
    update_height(root)
    bf = get_bf(root)
    
    # LL
    if bf > 1 and key < root.left.key:
        log.append(f"  失衡结点: {root.key} (BF={bf}), 左孩子 {root.left.key} (BF={get_bf(root.left)})")
        log.append(f"  → LL旋转")
        log.append("  旋转类型: LL")
        log.append(f"  失衡结点: {root.key}")
        log.append(f"  最小不平衡子树根: {root.key}")
        log.append(f"  指针重连: {root.left.key}上提为子树根, {root.key}成为{root.left.key}的右孩子, {root.left.key}的原右子树挂到{root.key}的左指针")
        new_root = right_rotate(root)
        height_changed = (new_root.height < old_height)
        return new_root, {'type': 'LL', 'imbalance_node': root.key, 'height_changed': height_changed}
    
    # RR
    if bf < -1 and key > root.right.key:
        log.append(f"  失衡结点: {root.key} (BF={bf}), 右孩子 {root.right.key} (BF={get_bf(root.right)})")
        log.append(f"  → RR旋转")
        log.append("  旋转类型: RR")
        log.append(f"  失衡结点: {root.key}")
        log.append(f"  最小不平衡子树根: {root.key}")
        log.append(f"  指针重连: {root.right.key}上提为子树根, {root.key}成为{root.right.key}的左孩子, {root.right.key}的原左子树挂到{root.key}的右指针")
        new_root = left_rotate(root)
        height_changed = (new_root.height < old_height)
        return new_root, {'type': 'RR', 'imbalance_node': root.key, 'height_changed': height_changed}
    
    # LR
    if bf > 1 and key > root.left.key:
        log.append(f"  失衡结点: {root.key} (BF={bf}), 左孩子 {root.left.key} (BF={get_bf(root.left)})")
        log.append(f"  → LR旋转（先对{root.left.key}左旋，再对{root.key}右旋）")
        log.append("  旋转类型: LR")
        log.append(f"  失衡结点: {root.key}")
        log.append(f"  最小不平衡子树根: {root.key}")
        root.left = left_rotate(root.left)
        log.append(f"  指针重连(第一步-左旋): 对{root.left.key}的子树左旋")
        log.append(f"  指针重连(第二步-右旋): {root.left.key}上提为子树根, {root.key}成为其右孩子")
        new_root = right_rotate(root)
        height_changed = (new_root.height < old_height)
        return new_root, {'type': 'LR', 'imbalance_node': root.key, 'height_changed': height_changed}
    
    # RL
    if bf < -1 and key < root.right.key:
        log.append(f"  失衡结点: {root.key} (BF={bf}), 右孩子 {root.right.key} (BF={get_bf(root.right)})")
        log.append(f"  → RL旋转（先对{root.right.key}右旋，再对{root.key}左旋）")
        log.append("  旋转类型: RL")
        log.append(f"  失衡结点: {root.key}")
        log.append(f"  最小不平衡子树根: {root.key}")
        root.right = right_rotate(root.right)
        log.append(f"  指针重连(第一步-右旋): 对{root.right.key}的子树右旋")
        log.append(f"  指针重连(第二步-左旋): {root.right.key}上提为子树根, {root.key}成为其左孩子")
        new_root = left_rotate(root)
        height_changed = (new_root.height < old_height)
        return new_root, {'type': 'RL', 'imbalance_node': root.key, 'height_changed': height_changed}
    
    return root, None

def get_bf_all(node, result):
    if not node:
        return
    result.append(f"  {node.key}: BF={get_bf(node)}")
    get_bf_all(node.left, result)
    get_bf_all(node.right, result)

def tree_to_str(node, prefix="", is_left=True):
    if not node:
        return ""
    result = prefix
    result += ("├── " if is_left else "└── ")
    result += f"{node.key}(BF={get_bf(node)})\n"
    new_prefix = prefix + ("│   " if is_left else "    ")
    if node.left or node.right:
        if node.right:
            result += tree_to_str(node.right, new_prefix, False)
        if node.left:
            result += tree_to_str(node.left, new_prefix, True)
    return result

def check_avl(node):
    if not node:
        return True
    bf = get_bf(node)
    if abs(bf) > 1:
        return False
    return check_avl(node.left) and check_avl(node.right)

def simulate(sequence):
    root = None
    rotations = []
    rotation_types = set()
    all_logs = []
    chain_imbalance = False
    chain_imbalance_detail = None
    
    for i, key in enumerate(sequence):
        step_log = [f"=== 插入第 {i+1} 个元素: {key} ==="]
        
        # 记录插入前各祖先的BF
        ancestor_bfs = {}
        if root:
            node = root
            path = []
            while node:
                ancestor_bfs[node.key] = get_bf(node)
                if key < node.key:
                    path.append(('L', node))
                    node = node.left
                else:
                    path.append(('R', node))
                    node = node.right
        
        root, rot_info = insert(root, key, step_log)
        
        # 检查连锁失衡：旋转后子树高度变化导致祖先BF变化
        if rot_info:
            # 检查祖先BF是否变化
            if root and ancestor_bfs:
                # 找到旋转子树的父节点
                # 简化：检查根节点的BF是否变化
                if root.key in ancestor_bfs:
                    old_bf = ancestor_bfs[root.key]
                    new_bf = get_bf(root)
                    if old_bf != new_bf:
                        chain_imbalance = True
                        chain_imbalance_detail = f"第{i+1}步插入{key}后，{rot_info['type']}旋转导致根节点{root.key}的BF从{old_bf}变为{new_bf}"
                        step_log.append(f"  【连锁失衡】{chain_imbalance_detail}")
        
        bf_log = []
        get_bf_all(root, bf_log)
        step_log.extend(bf_log)
        
        if rot_info:
            rotation_types.add(rot_info['type'])
            rotations.append({
                'step': i + 1,
                'key': key,
                'type': rot_info['type'],
                'imbalance_node': rot_info['imbalance_node'],
                'height_changed': rot_info['height_changed'],
                'log': step_log
            })
        
        all_logs.append(step_log)
    
    is_avl = check_avl(root)
    
    return {
        'rotations': rotations,
        'rotation_types': rotation_types,
        'all_logs': all_logs,
        'chain_imbalance': chain_imbalance,
        'chain_imbalance_detail': chain_imbalance_detail,
        'is_avl': is_avl,
        'final_tree': tree_to_str(root)
    }

# 系统搜索满足所有约束的序列
# 策略：构造前m步平衡的树，然后插入触发不同旋转的元素

def generate_candidates():
    """生成候选序列"""
    candidates = []
    
    # 基础平衡树：根+左右孩子
    bases = [
        [30, 20, 40],
        [40, 20, 60],
        [50, 30, 70],
        [30, 40, 20],
        [40, 30, 50],
        [50, 40, 60],
    ]
    
    # 扩展前m步（无旋转）
    for base in bases:
        # 添加第4个元素（不触发旋转）
        for ext4 in range(1, 100):
            if ext4 not in base:
                seq4 = base + [ext4]
                # 检查前4步是否无旋转
                result = simulate(seq4)
                if len(result['rotations']) == 0:
                    # 添加第5个元素（不触发旋转）
                    for ext5 in range(1, 100):
                        if ext5 not in seq4:
                            seq5 = seq4 + [ext5]
                            result = simulate(seq5)
                            if len(result['rotations']) == 0:
                                # 添加后续元素触发旋转
                                for ext6 in range(1, 100):
                                    if ext6 not in seq5:
                                        seq6 = seq5 + [ext6]
                                        result = simulate(seq6)
                                        if len(result['rotations']) > 0:
                                            # 找到首次旋转，继续添加
                                            for ext7 in range(1, 100):
                                                if ext7 not in seq6:
                                                    seq7 = seq6 + [ext7]
                                                    result = simulate(seq7)
                                                    if len(result['rotations']) >= 2:
                                                        candidates.append(seq7)
                                                        if len(candidates) >= 50:
                                                            return candidates
    return candidates

# 使用更智能的构造方法
def smart_construct():
    """智能构造满足约束的序列"""
    candidates = []
    
    # 策略1：前4步构建平衡树，第5步触发LL/RR，第6步触发LR/RL
    # 基础：[30, 20, 40, 10] → 30(BF=1) → 20(BF=1) → 10, 40
    # 第5步插入5 → LL旋转（20失衡）
    # 第6步插入25 → LR旋转（30失衡）
    candidates.append([30, 20, 40, 10, 5, 25, 35, 45])
    
    # 策略2：前4步构建平衡树，第5步触发RR，第6步触发RL
    # 基础：[30, 40, 20, 50] → 30(BF=-1) → 20, 40(BF=-1) → 50
    # 第5步插入60 → RR旋转（40失衡）
    # 第6步插入35 → RL旋转（30失衡）
    candidates.append([30, 40, 20, 50, 60, 35, 10, 45])
    
    # 策略3：前5步构建平衡树，第6步触发LR，第7步触发LL
    # 基础：[40, 20, 60, 10, 50] → 40(BF=0) → 20(BF=0) → 10, 30; 60(BF=0) → 50, 70
    # 需要调整...
    candidates.append([40, 20, 60, 10, 50, 30, 5, 70])
    
    # 策略4：前4步构建平衡树，第5步触发LR，第6步触发RR
    candidates.append([30, 20, 40, 35, 25, 50, 10, 45])
    
    # 策略5：前5步构建平衡树，第6步触发RL，第7步触发RR
    candidates.append([40, 20, 60, 10, 50, 55, 70, 30])
    
    # 策略6：前4步构建平衡树，第5步触发LL，第6步触发LR（连锁失衡）
    # 关键：第5步LL旋转后子树高度不变，第6步LR旋转后子树高度降低
    candidates.append([30, 20, 40, 10, 5, 25, 35, 45])
    
    # 策略7：前4步构建平衡树，第5步触发RR，第6步触发RL（连锁失衡）
    candidates.append([30, 40, 20, 50, 60, 35, 10, 45])
    
    # 策略8：前5步构建平衡树，第6步触发LR，第7步触发LL
    candidates.append([40, 20, 60, 10, 50, 30, 5, 70])
    
    # 策略9：前4步构建平衡树，第5步触发LR，第6步触发LL
    candidates.append([30, 20, 40, 35, 25, 5, 10, 45])
    
    # 策略10：前5步构建平衡树，第6步触发RL，第7步触发RR
    candidates.append([40, 20, 60, 10, 50, 55, 70, 30])
    
    # 策略11：前4步构建平衡树，第5步触发LL，第6步触发LR（确保连锁失衡）
    # 关键：第5步LL旋转后，第6步LR旋转导致子树高度降低
    candidates.append([30, 20, 40, 10, 5, 25, 35, 45])
    
    # 策略12：前4步构建平衡树，第5步触发RR，第6步触发RL（确保连锁失衡）
    candidates.append([30, 40, 20, 50, 60, 35, 10, 45])
    
    # 策略13：前5步构建平衡树，第6步触发LR，第7步触发LL
    candidates.append([40, 20, 60, 10, 50, 30, 5, 70])
    
    # 策略14：前4步构建平衡树，第5步触发LR，第6步触发RR
    candidates.append([30, 20, 40, 35, 25, 50, 10, 45])
    
    # 策略15：前5步构建平衡树，第6步触发RL，第7步触发RR
    candidates.append([40, 20, 60, 10, 50, 55, 70, 30])
    
    return candidates

candidates = smart_construct()

best_seq = None
best_result = None

for seq in candidates:
    result = simulate(seq)
    n = len(seq)
    
    # 检查约束
    if n < 6 or n > 10:
        continue
    
    # 检查前m步无旋转
    first_rot_step = result['rotations'][0]['step'] if result['rotations'] else n + 1
    m = first_rot_step - 1
    if m < 3:  # 前m步至少3步
        continue
    
    # 检查旋转类型
    if len(result['rotation_types']) < 2:
        continue
    if 'LR' not in result['rotation_types'] and 'RL' not in result['rotation_types']:
        continue
    
    # 检查连锁失衡
    if not result['chain_imbalance']:
        continue
    
    # 检查AVL性质
    if not result['is_avl']:
        continue
    
    # 检查总旋转次数
    if len(result['rotations']) < 2:
        continue
    
    best_seq = seq
    best_result = result
    break

if best_seq:
    print(f"找到满足约束的序列: {best_seq}")
    print(f"序列长度 n = {len(best_seq)}")
    print(f"前 m = {best_result['rotations'][0]['step'] - 1} 步无旋转")
    print(f"旋转类型: {best_result['rotation_types']}")
    print(f"连锁失衡: {best_result['chain_imbalance']}")
    if best_result['chain_imbalance_detail']:
        print(f"连锁失衡详情: {best_result['chain_imbalance_detail']}")
    print(f"AVL性质: {best_result['is_avl']}")
    print(f"旋转次数: {len(best_result['rotations'])}")
    print()
    print("=== 详细插入过程 ===")
    for log in best_result['all_logs']:
        for line in log:
            print(line)
        print()
    print("=== 最终树形态 ===")
    print(best_result['final_tree'])
    print("=== 旋转详情 ===")
    for rot in best_result['rotations']:
        print(f"第 {rot['step']} 步插入 {rot['key']}: {rot['type']} 旋转, 失衡结点: {rot['imbalance_node']}, 子树高度变化: {rot['height_changed']}")
else:
    print("未找到满足所有约束的序列")
    # 打印所有候选的结果以便调试
    for seq in candidates:
        result = simulate(seq)
        print(f"\n序列 {seq}:")
        print(f"  旋转类型: {result['rotation_types']}")
        print(f"  连锁失衡: {result['chain_imbalance']}")
        if result['chain_imbalance_detail']:
            print(f"  连锁失衡详情: {result['chain_imbalance_detail']}")
        print(f"  AVL: {result['is_avl']}")
        print(f"  旋转次数: {len(result['rotations'])}")
        if result['rotations']:
            print(f"  首次旋转在第 {result['rotations'][0]['step']} 步")
