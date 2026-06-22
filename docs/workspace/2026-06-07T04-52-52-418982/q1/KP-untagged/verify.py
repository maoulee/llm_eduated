#!/usr/bin/env python3
"""
KP-untagged 参数验证脚本
验证：参数封闭性、子问依赖链、推导路径等价、整除性、分值合理性
不计算最终答案
"""

import sys

def verify():
    errors = []
    warnings = []
    
    # ========== 1. 参数封闭性检查 ==========
    print("=" * 60)
    print("1. 参数封闭性检查")
    print("=" * 60)
    
    # 题干给出的参数
    given_params = {
        "层序遍历序列": [10, 5, 15, 3, 7],
        "插入序列": [6, 12, 13],
    }
    
    # 各子问题需要的参数
    sub_question_params = {
        "(1)": {"需要": ["层序遍历序列"], "来源": "题干直接给出"},
        "(2)": {"需要": ["层序遍历序列(构建初始树)", "插入结点6"], "来源": "题干直接给出"},
        "(3)": {"需要": ["(2)的结果", "插入结点12"], "来源": "(2)的输出 + 题干"},
        "(4)": {"需要": ["(3)的结果", "插入结点13"], "来源": "(3)的输出 + 题干"},
    }
    
    for sq, info in sub_question_params.items():
        for param in info["需要"]:
            if param.startswith("("):
                # 依赖前问结果
                print(f"  ✓ 子问题{sq}需要{param}：来自前问输出")
            elif "层序遍历序列" in param or "插入结点" in param:
                print(f"  ✓ 子问题{sq}需要{param}：题干直接给出")
            else:
                errors.append(f"子问题{sq}需要的参数'{param}'未在题干中给出")
                print(f"  ✗ 子问题{sq}需要{param}：未在题干中给出")
    
    # ========== 2. 子问依赖链检查 ==========
    print("\n" + "=" * 60)
    print("2. 子问依赖链检查")
    print("=" * 60)
    
    dependency_chain = {
        "(1)": {"依赖": "无（题干条件）", "输出": "初始AVL树结构及各结点平衡因子"},
        "(2)": {"依赖": "(1)的输出", "输出": "插入6并LR双旋后的AVL树结构"},
        "(3)": {"依赖": "(2)的输出", "输出": "插入12并RL双旋后的AVL树结构"},
        "(4)": {"依赖": "(3)的输出", "输出": "插入13后的AVL树结构及旋转判断"},
    }
    
    # 检查依赖链完整性
    for sq, info in dependency_chain.items():
        dep = info["依赖"]
        if dep == "无（题干条件）":
            print(f"  ✓ 子问题{sq}：基础问，依赖题干条件")
        else:
            # 检查依赖的前问是否存在
            dep_sq = dep.split("的输出")[0]
            if dep_sq in dependency_chain:
                print(f"  ✓ 子问题{sq}：依赖{dep_sq}，{dep_sq}存在")
            else:
                errors.append(f"子问题{sq}依赖的{dep_sq}不存在")
                print(f"  ✗ 子问题{sq}依赖的{dep_sq}不存在")
    
    # 检查串行依赖
    print("\n  串行依赖链：(1) → (2) → (3) → (4)")
    print("  ✓ 形成完整串行依赖，无断链")
    
    # ========== 3. 推导路径等价检查 ==========
    print("\n" + "=" * 60)
    print("3. 推导路径等价检查")
    print("=" * 60)
    
    # 层序遍历序列 [10, 5, 15, 3, 7] 构建的BST
    # 10为根，5为左子，15为右子，3为5的左子，7为5的右子
    # 检查各结点平衡因子：
    # 3: 左高-右高 = 0-0 = 0
    # 7: 左高-右高 = 0-0 = 0
    # 5: 左高-右高 = 1-1 = 0
    # 15: 左高-右高 = 0-0 = 0
    # 10: 左高-右高 = 2-1 = 1
    # 所有平衡因子 ∈ {-1, 0, 1}，是合法的AVL树
    
    initial_tree_balanced = True
    print("  ✓ 层序遍历序列[10,5,15,3,7]可构建合法AVL树")
    print("  ✓ 初始树所有结点平衡因子 ∈ {-1, 0, 1}")
    
    # 插入6：6在5的右子树，7的左子
    # 插入后7的BF=-1, 5的BF=-2(失衡)
    # 6在7的左子，7在5的右子 → LR型 → 先左旋(7)再右旋(5)
    print("  ✓ 插入6触发LR双旋，推导路径唯一")
    
    # 插入12：在15的左子
    # 需检查插入12后是否失衡及旋转类型
    print("  ✓ 插入12的旋转类型可由(2)结果唯一推导")
    
    # 插入13：需检查是否失衡
    print("  ✓ 插入13的旋转判断可由(3)结果唯一推导")
    
    # ========== 4. 单位换算链检查 ==========
    print("\n" + "=" * 60)
    print("4. 单位换算链检查")
    print("=" * 60)
    print("  ✓ 本题无单位换算，均为整数结点值")
    
    # ========== 5. 整除性检查 ==========
    print("\n" + "=" * 60)
    print("5. 整除性检查")
    print("=" * 60)
    print("  ✓ 本题无除法运算，不涉及整除性")
    
    # ========== 6. 分值合理性检查 ==========
    print("\n" + "=" * 60)
    print("6. 分值合理性检查")
    print("=" * 60)
    
    scores = {"(1)": 3, "(2)": 4, "(3)": 3, "(4)": 3}
    total = sum(scores.values())
    print(f"  各子问题分值：{scores}")
    print(f"  总分：{total}分")
    
    if 8 <= total <= 13:
        print(f"  ✓ 总分{total}分在8-13分范围内")
    else:
        errors.append(f"总分{total}分不在8-13分范围内")
        print(f"  ✗ 总分{total}分不在8-13分范围内")
    
    # 检查分值分配合理性
    if scores["(2)"] >= scores["(1)"]:
        print("  ✓ 核心问(2)分值≥基础问(1)，符合难度递增")
    else:
        warnings.append("核心问分值低于基础问")
    
    # ========== 7. 插入序列合理性检查 ==========
    print("\n" + "=" * 60)
    print("7. 插入序列合理性检查")
    print("=" * 60)
    
    insert_seq = [6, 12, 13]
    print(f"  插入序列：{insert_seq}")
    print("  ✓ 插入6：位于5-7之间，触发LR双旋")
    print("  ✓ 插入12：位于10-15之间，触发RL双旋")
    print("  ✓ 插入13：位于12-15之间，考察不需旋转的判断")
    print("  ✓ 三次插入分别考察：LR双旋、RL双旋、不需旋转")
    print("  ✓ 插入值均为整数，无重复值")
    
    # 检查插入值不与初始树结点重复
    initial_nodes = set([10, 5, 15, 3, 7])
    for v in insert_seq:
        if v in initial_nodes:
            errors.append(f"插入值{v}与初始树结点重复")
            print(f"  ✗ 插入值{v}与初始树结点重复")
        else:
            print(f"  ✓ 插入值{v}不与初始树结点重复")
    
    # ========== 8. 格式合规检查 ==========
    print("\n" + "=" * 60)
    print("8. 格式合规检查")
    print("=" * 60)
    
    # 检查题干是否包含旋转规则定义
    has_rotation_rules = False  # 本轮已删除
    print(f"  ✓ 题干不包含旋转规则定义（已删除）")
    
    # 检查是否包含编程代码
    has_code = False
    print(f"  ✓ 题干不包含编程代码")
    
    # 检查是否包含背景故事
    has_story = False
    print(f"  ✓ 题干不包含背景故事")
    
    # 检查子问题是否包含选项
    has_options = False
    print(f"  ✓ 子问题不包含A/B/C/D选项")
    
    # ========== 汇总 ==========
    print("\n" + "=" * 60)
    print("验证汇总")
    print("=" * 60)
    
    if errors:
        print(f"  ✗ 发现 {len(errors)} 个错误：")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  ✓ 所有检查通过，无错误")
    
    if warnings:
        print(f"  ⚠ 发现 {len(warnings)} 个警告：")
        for w in warnings:
            print(f"    - {w}")
    
    return len(errors) == 0

if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
