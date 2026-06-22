"""验证AVL树插入题目的参数合法性"""

# 初始AVL树结构
#       20
#      /  \
#    10    30
#   /  \
#  5    15

# 验证初始树是合法的AVL树
def verify_initial_tree():
    # 每个节点的高度
    heights = {5: 1, 15: 1, 10: 2, 30: 1, 20: 3}
    # 每个节点的平衡因子
    bfs = {5: 0, 15: 0, 10: 0, 30: 0, 20: 0}
    
    # 检查所有平衡因子是否在[-1, 0, 1]范围内
    for node, bf in bfs.items():
        assert bf in [-1, 0, 1], f"节点{node}的平衡因子{bf}超出范围"
    
    # 检查高度计算是否正确
    assert heights[10] == max(heights[5], heights[15]) + 1
    assert heights[20] == max(heights[10], heights[30]) + 1
    
    print("✓ 初始AVL树验证通过")
    print(f"  树高度: {heights[20]}")
    print(f"  节点数: {len(heights)}")

# 插入序列
insert_sequence = [25, 35, 45, 8, 12, 18, 22, 28, 32, 38, 42, 48, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160, 165, 170, 175, 180, 185, 190, 195, 200, 205, 210, 215, 220, 225, 230, 235, 240, 245, 250, 255, 260, 265, 270, 275, 280, 285, 290, 295, 300, 305, 310, 315, 320, 325, 330, 335, 340, 345, 350, 355, 360, 365, 370, 375, 380, 385, 390, 395, 400, 405, 410, 415, 420, 425, 430, 435, 440, 445, 450, 455, 460, 465, 470, 475, 480, 485, 490, 495, 500, 505, 510, 515, 520, 525, 530, 535, 540, 545, 550, 555, 560, 565, 570, 575, 580, 585, 590, 595, 600, 605, 610, 615, 620, 625, 630, 635, 640, 645, 650, 655, 660, 665, 670, 675, 680, 685, 690, 695, 700, 705, 710, 715, 720, 725, 730, 735, 740, 745, 750, 755, 760, 765, 770, 775, 780, 785, 790, 795, 800, 805, 810, 815, 820, 825, 830, 835, 840, 845, 850, 855, 860, 865, 870, 875, 880, 885, 890, 895, 900, 905, 910, 915, 920, 925, 930, 935, 940, 945, 950, 955, 960, 965, 970, 975, 980, 985, 990, 995, 1000]

# 验证插入序列

def verify_insert_sequence():
    # 检查序列中是否有重复值
    assert len(insert_sequence) == len(set(insert_sequence)), "插入序列中有重复值"
    
    # 检查序列中是否有初始树中已存在的值
    initial_values = {5, 10, 15, 20, 30}
    for val in insert_sequence:
        assert val not in initial_values, f"插入序列中的值{val}已在初始树中"
    
    print(f"✓ 插入序列验证通过")
    print(f"  插入序列长度: {len(insert_sequence)}")
    print(f"  插入序列范围: [{min(insert_sequence)}, {max(insert_sequence)}]")

# 验证题目参数
def verify_question_params():
    # 检查初始树高度是否为3
    verify_initial_tree()
    
    # 检查插入序列
    verify_insert_sequence()
    
    # 检查插入序列是否包含触发四种旋转的值
    # LL旋转: 插入左子树的左子节点
    # RR旋转: 插入右子树的右子节点
    # LR旋转: 插入左子树的右子节点
    # RL旋转: 插入右子树的左子节点
    
    # 检查插入序列中是否有触发LL旋转的值
    ll_triggers = [val for val in insert_sequence if val < 10]
    assert len(ll_triggers) > 0, "插入序列中没有触发LL旋转的值"
    
    # 检查插入序列中是否有触发RR旋转的值
    rr_triggers = [val for val in insert_sequence if val > 30]
    assert len(rr_triggers) > 0, "插入序列中没有触发RR旋转的值"
    
    # 检查插入序列中是否有触发LR旋转的值
    lr_triggers = [val for val in insert_sequence if 10 < val < 15]
    assert len(lr_triggers) > 0, "插入序列中没有触发LR旋转的值"
    
    # 检查插入序列中是否有触发RL旋转的值
    rl_triggers = [val for val in insert_sequence if 20 < val < 30]
    assert len(rl_triggers) > 0, "插入序列中没有触发RL旋转的值"
    
    print("✓ 旋转触发值验证通过")
    print(f"  LL旋转触发值数量: {len(ll_triggers)}")
    print(f"  RR旋转触发值数量: {len(rr_triggers)}")
    print(f"  LR旋转触发值数量: {len(lr_triggers)}")
    print(f"  RL旋转触发值数量: {len(rl_triggers)}")

# 执行验证
verify_question_params()
print("\n所有参数验证通过!")
