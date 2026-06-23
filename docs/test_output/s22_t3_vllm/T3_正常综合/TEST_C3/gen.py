"""
Q41 AVL 插入模拟题 — 参数构造与验证（v2）
"""

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1
        self.bf = 0  # balance factor: left_height - right_height

def get_height(node):
    if node is None:
        return 0
    return node.height

def get_bf(node):
    if node is None:
        return 0
    return node.bf

def update_height_bf(node):
    if node:
        node.height = 1 + max(get_height(node.left), get_height(node.right))
        node.bf = get_height(node.left) - get_height(node.right)

def is_valid_avl(node):
    """检查是否为合法 AVL 树"""
    if node is None:
        return True
    if abs(node.bf) > 1:
        return False
    return is_valid_avl(node.left) and is_valid_avl(node.right)

def right_rotate(z):
    """右旋（LL 型）"""
    x = z.left
    T2 = x.right
    x.right = z
    z.left = T2
    update_height_bf(z)
    update_height_bf(x)
    return x

def left_rotate(z):
    """左旋（RR 型）"""
    y = z.right
    T2 = y.left
    y.left = z
    z.right = T2
    update_height_bf(z)
    update_height_bf(y)
    return y

def insert(node, key, log):
    """AVL 插入，记录旋转类型"""
    if node is None:
        return Node(key)
    
    if key < node.key:
        node.left = insert(node.left, key, log)
    elif key > node.key:
        node.right = insert(node.right, key, log)
    else:
        return node  # 不允许重复
    
    update_height_bf(node)
    bf = get_bf(node)
    
    # LL 型
    if bf == 2 and get_bf(node.left) >= 0:
        log.append(f"插入 {key} 后，节点 {node.key} 失衡(bf={bf})，左子节点 bf={get_bf(node.left)}，触发 LL 型旋转（右旋）")
        return right_rotate(node)
    
    # LR 型
    if bf == 2 and get_bf(node.left) < 0:
        log.append(f"插入 {key} 后，节点 {node.key} 失衡(bf={bf})，左子节点 bf={get_bf(node.left)}，触发 LR 型旋转（先左旋后右旋）")
        node.left = left_rotate(node.left)
        return right_rotate(node)
    
    # RR 型
    if bf == -2 and get_bf(node.right) <= 0:
        log.append(f"插入 {key} 后，节点 {node.key} 失衡(bf={bf})，右子节点 bf={get_bf(node.right)}，触发 RR 型旋转（左旋）")
        return left_rotate(node)
    
    # RL 型
    if bf == -2 and get_bf(node.right) > 0:
        log.append(f"插入 {key} 后，节点 {node.key} 失衡(bf={bf})，右子节点 bf={get_bf(node.right)}，触发 RL 型旋转（先右旋后左旋）")
        node.right = right_rotate(node.right)
        return left_rotate(node)
    
    return node

def build_tree_from_list(keys):
    """按顺序插入构建 AVL 树"""
    root = None
    log = []
    for k in keys:
        root = insert(root, k, log)
    return root, log

def level_order(node):
    """层序遍历"""
    if node is None:
        return []
    result = []
    queue = [node]
    while queue:
        curr = queue.pop(0)
        if curr:
            result.append((curr.key, curr.bf))
            queue.append(curr.left)
            queue.append(curr.right)
        else:
            result.append(None)
    while result and result[-1] is None:
        result.pop()
    return result

def print_tree(node, prefix="", is_left=True):
    """可视化打印树结构"""
    if node is None:
        return
    print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
    print(prefix + ("└── " if is_left else "┌── ") + f"[{node.key}] bf={node.bf}")
    print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

def copy_tree(node):
    """深拷贝树"""
    if node is None:
        return None
    new_node = Node(node.key)
    new_node.height = node.height
    new_node.bf = node.bf
    new_node.left = copy_tree(node.left)
    new_node.right = copy_tree(node.right)
    return new_node

# ===== 尝试多组参数 =====

def try_params(initial_keys, insertion_seq, label=""):
    """尝试一组参数"""
    print(f"\n{'='*60}")
    print(f"尝试 {label}: 初始={initial_keys}, 插入={insertion_seq}")
    print(f"{'='*60}")
    
    # 构建初始树
    initial_root, initial_log = build_tree_from_list(initial_keys)
    
    if not is_valid_avl(initial_root):
        print("❌ 初始树不合法")
        return None
    
    print(f"初始树层序: {level_order(initial_root)}")
    print("初始树结构:")
    print_tree(initial_root)
    
    # 执行插入
    root = copy_tree(initial_root)
    rotation_log = []
    rotation_types = set()
    
    for key in insertion_seq:
        root = insert(root, key, rotation_log)
        for l in rotation_log:
            if "LL 型" in l:
                rotation_types.add("LL")
            elif "LR 型" in l:
                rotation_types.add("LR")
            elif "RR 型" in l:
                rotation_types.add("RR")
            elif "RL 型" in l:
                rotation_types.add("RL")
    
    print(f"\n插入后旋转日志:")
    for l in rotation_log:
        print(f"  {l}")
    
    print(f"\n最终树层序: {level_order(root)}")
    print(f"最终树合法: {is_valid_avl(root)}")
    print(f"触发旋转类型: {rotation_types} (数量: {len(rotation_types)})")
    
    if len(rotation_types) >= 2 and is_valid_avl(root):
        print("✅ 满足条件！")
        return {
            'initial_keys': initial_keys,
            'insertion_seq': insertion_seq,
            'initial_root': initial_root,
            'final_root': root,
            'rotation_log': rotation_log,
            'rotation_types': rotation_types
        }
    else:
        print("❌ 不满足条件")
        return None

# 尝试多组参数
results = []

# 方案1：初始树较浅，插入触发旋转
r = try_params([30, 20, 40, 10, 35], [5, 25, 45], "方案1")
if r:
    results.append(r)

# 方案2：初始树 bf 接近边界
r = try_params([50, 30, 70, 20, 40, 60, 80], [25, 35, 65], "方案2")
if r:
    results.append(r)

# 方案3：更小的初始树
r = try_params([30, 20, 40], [10, 25, 35], "方案3")
if r:
    results.append(r)

# 方案4
r = try_params([40, 20, 60, 10, 30, 50, 70], [25, 35, 55], "方案4")
if r:
    results.append(r)

# 方案5：初始树有 bf=1 的节点
r = try_params([30, 20, 40, 10], [5, 25, 35], "方案5")
if r:
    results.append(r)

# 方案6
r = try_params([50, 25, 75, 10, 37, 62, 88], [5, 20, 30], "方案6")
if r:
    results.append(r)

# 方案7
r = try_params([30, 20, 40, 10, 25], [5, 15, 35], "方案7")
if r:
    results.append(r)

# 方案8
r = try_params([40, 20, 60, 10, 30, 50], [5, 25, 35], "方案8")
if r:
    results.append(r)

# 方案9
r = try_params([30, 20, 40, 10, 25], [5, 15, 50], "方案9")
if r:
    results.append(r)

# 方案10
r = try_params([50, 30, 70, 20, 40], [10, 25, 35], "方案10")
if r:
    results.append(r)

# 方案11
r = try_params([40, 20, 60, 10, 30], [5, 25, 35], "方案11")
if r:
    results.append(r)

# 方案12
r = try_params([30, 20, 40, 10, 25], [15, 35, 50], "方案12")
if r:
    results.append(r)

# 方案13
r = try_params([50, 25, 75, 10, 37], [5, 20, 30], "方案13")
if r:
    results.append(r)

# 方案14
r = try_params([40, 20, 60, 10, 30, 50, 70], [15, 25, 35], "方案14")
if r:
    results.append(r)

# 方案15
r = try_params([30, 20, 40, 10, 25, 35, 50], [5, 15, 45], "方案15")
if r:
    results.append(r)

# 方案16：初始树 bf 有 1 或 -1
r = try_params([30, 20, 40, 10], [25, 35, 50], "方案16")
if r:
    results.append(r)

# 方案17
r = try_params([40, 20, 60, 10, 30], [25, 35, 55], "方案17")
if r:
    results.append(r)

# 方案18
r = try_params([50, 30, 70, 20, 40, 60], [10, 25, 35], "方案18")
if r:
    results.append(r)

# 方案19
r = try_params([30, 20, 40, 10, 25], [5, 35, 45], "方案19")
if r:
    results.append(r)

# 方案20
r = try_params([40, 20, 60, 10, 30, 50], [25, 35, 55], "方案20")
if r:
    results.append(r)

print(f"\n\n{'='*60}")
print(f"找到 {len(results)} 组满足条件的参数")
print(f"{'='*60}")

if results:
    best = results[0]
    print(f"\n选中方案: 初始={best['initial_keys']}, 插入={best['insertion_seq']}")
    print(f"旋转类型: {best['rotation_types']}")
    print(f"\n初始树:")
    print_tree(best['initial_root'])
    print(f"\n最终树:")
    print_tree(best['final_root'])
    print(f"\n旋转日志:")
    for l in best['rotation_log']:
        print(f"  {l}")

    # ===== 详细求解路径 =====
    print(f"\n\n===== 求解路径 =====")
    
    # 初始树状态
    print(f"【初始树】")
    print(f"层序遍历（节点值, 平衡因子）: {level_order(best['initial_root'])}")
    print(f"树结构:")
    print_tree(best['initial_root'])
    
    # 逐步插入
    root = copy_tree(best['initial_root'])
    step_log = []
    
    for i, key in enumerate(best['insertion_seq'], 1):
        print(f"\n【第{i}步：插入节点 {key}】")
        
        # 插入前状态
        print(f"插入前树结构:")
        print_tree(root)
        
        # 执行插入
        old_root = copy_tree(root)
        step_rotation_log = []
        root = insert(root, key, step_rotation_log)
        
        # 插入后状态
        print(f"插入 {key} 后树结构:")
        print_tree(root)
        
        # 旋转信息
        if step_rotation_log:
            for l in step_rotation_log:
                print(f"  → {l}")
        else:
            print(f"  → 未触发旋转，树保持平衡")
        
        # 当前各节点平衡因子
        print(f"  当前层序（节点值, 平衡因子）: {level_order(root)}")
    
    # 最终状态
    print(f"\n【最终树】")
    print(f"层序遍历（节点值, 平衡因子）: {level_order(root)}")
    print(f"树结构:")
    print_tree(root)
    print(f"根节点值: {root.key}")
    print(f"根节点平衡因子: {root.bf}")
    print(f"树是否合法 AVL: {is_valid_avl(root)}")
    print(f"触发旋转类型集合: {best['rotation_types']}")
    print(f"触发旋转类型数量: {len(best['rotation_types'])}")
    
    # ===== 答案 =====
    print(f"\n===== 答案 =====")
    print(f"最终 AVL 树的根节点值为: {root.key}")
    print(f"最终 AVL 树的根节点平衡因子为: {root.bf}")
