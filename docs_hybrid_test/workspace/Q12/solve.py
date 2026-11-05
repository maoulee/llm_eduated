# ===== 题目参数定义 =====
storage_device = "磁盘"

access_method_categories = {
    "SAM": {
        "chinese_name": "顺序存取存储器",
        "features": [
            "必须按存储介质上的物理顺序依次查找数据",
            "通常不能直接定位到任意目标块",
        ],
        "typical_devices": ["磁带"],
    },
    "DAM": {
        "chinese_name": "直接存取存储器",
        "features": [
            "可先定位到目标块所在区域或附近位置",
            "再按顺序读写目标块数据",
            "访问时间与目标块所在位置有关",
        ],
        "typical_devices": ["磁盘"],
    },
    "RAM": {
        "chinese_name": "随机存取存储器",
        "features": [
            "可直接访问任意存储单元",
            "任意存储单元访问时间基本相同",
        ],
        "typical_devices": ["主存"],
    },
    "ROM": {
        "chinese_name": "只读存储器",
        "features": [
            "按读写特性分类",
            "通常只能读出预先写入的数据",
        ],
        "typical_devices": ["只读存储器"],
    },
}

options = {
    "A": "磁盘属于顺序存取存储器，访问数据时必须从存储介质起始位置逐个查找到目标块",
    "B": "磁盘属于直接存取存储器，访问数据时可先定位到目标块所在位置，再按顺序读写该块数据",
    "C": "磁盘属于随机存取存储器，任意存储单元的访问时间均相同",
    "D": "磁盘属于只读存储器，只能读取其中已存储的数据，不能写入新数据",
}

# ===== 基础事实推导 =====
device_to_access_method = {}

for access_method_code, category_info in access_method_categories.items():
    for typical_device in category_info["typical_devices"]:
        device_to_access_method[typical_device] = access_method_code

disk_access_method_code = device_to_access_method[storage_device]
disk_access_method_name = access_method_categories[disk_access_method_code]["chinese_name"]

disk_can_directly_locate_target_area = disk_access_method_code == "DAM"
disk_must_search_from_beginning = disk_access_method_code == "SAM"
disk_has_equal_access_time_for_all_units = disk_access_method_code == "RAM"
disk_is_read_only_classification = disk_access_method_code == "ROM"

print("===== 基础事实推导 =====")
print(f"存储设备: {storage_device}")
print(f"由典型设备映射得到: {storage_device} -> {disk_access_method_code}")
print(f"{disk_access_method_code} 的中文名称: {disk_access_method_name}")
print(f"是否必须从起始位置逐个查找到目标块: {disk_must_search_from_beginning}")
print(f"是否可先定位到目标块所在位置再读写: {disk_can_directly_locate_target_area}")
print(f"是否任意存储单元访问时间均相同: {disk_has_equal_access_time_for_all_units}")
print(f"是否属于只读存储器分类: {disk_is_read_only_classification}")

# ===== 选项A验证 =====
option_a_claimed_method_code = "SAM"
option_a_requires_sequential_search_from_beginning = True

option_a_method_correct = disk_access_method_code == option_a_claimed_method_code
option_a_feature_correct = disk_must_search_from_beginning == option_a_requires_sequential_search_from_beginning
option_a_is_correct = option_a_method_correct and option_a_feature_correct

print("===== 选项A验证 =====")
print(f"选项A内容: {options['A']}")
print(f"选项A声称的存取方式: {access_method_categories[option_a_claimed_method_code]['chinese_name']}")
print(f"题干对象实际存取方式: {disk_access_method_name}")
print(f"存取方式判断是否一致: {option_a_method_correct}")
print(f"选项A声称必须从起始位置逐个查找: {option_a_requires_sequential_search_from_beginning}")
print(f"磁盘实际是否必须从起始位置逐个查找: {disk_must_search_from_beginning}")
print(f"特征判断是否一致: {option_a_feature_correct}")
print(f"选项A是否正确: {option_a_is_correct}")

# ===== 选项B验证 =====
option_b_claimed_method_code = "DAM"
option_b_can_locate_then_sequentially_read = True

option_b_method_correct = disk_access_method_code == option_b_claimed_method_code
option_b_feature_correct = disk_can_directly_locate_target_area == option_b_can_locate_then_sequentially_read
option_b_is_correct = option_b_method_correct and option_b_feature_correct

print("===== 选项B验证 =====")
print(f"选项B内容: {options['B']}")
print(f"选项B声称的存取方式: {access_method_categories[option_b_claimed_method_code]['chinese_name']}")
print(f"题干对象实际存取方式: {disk_access_method_name}")
print(f"存取方式判断是否一致: {option_b_method_correct}")
print(f"选项B声称可先定位到目标块所在位置再顺序读写: {option_b_can_locate_then_sequentially_read}")
print(f"磁盘实际是否可先定位到目标块所在位置再顺序读写: {disk_can_directly_locate_target_area}")
print(f"特征判断是否一致: {option_b_feature_correct}")
print(f"选项B是否正确: {option_b_is_correct}")

# ===== 选项C验证 =====
option_c_claimed_method_code = "RAM"
option_c_equal_access_time_for_all_units = True

option_c_method_correct = disk_access_method_code == option_c_claimed_method_code
option_c_feature_correct = disk_has_equal_access_time_for_all_units == option_c_equal_access_time_for_all_units
option_c_is_correct = option_c_method_correct and option_c_feature_correct

print("===== 选项C验证 =====")
print(f"选项C内容: {options['C']}")
print(f"选项C声称的存取方式: {access_method_categories[option_c_claimed_method_code]['chinese_name']}")
print(f"题干对象实际存取方式: {disk_access_method_name}")
print(f"存取方式判断是否一致: {option_c_method_correct}")
print(f"选项C声称任意存储单元访问时间均相同: {option_c_equal_access_time_for_all_units}")
print(f"磁盘实际是否任意存储单元访问时间均相同: {disk_has_equal_access_time_for_all_units}")
print(f"特征判断是否一致: {option_c_feature_correct}")
print(f"选项C是否正确: {option_c_is_correct}")

# ===== 选项D验证 =====
option_d_claimed_method_code = "ROM"
option_d_claimed_read_only = True

option_d_method_correct = disk_access_method_code == option_d_claimed_method_code
option_d_feature_correct = disk_is_read_only_classification == option_d_claimed_read_only
option_d_is_correct = option_d_method_correct and option_d_feature_correct

print("===== 选项D验证 =====")
print(f"选项D内容: {options['D']}")
print(f"选项D声称的类型: {access_method_categories[option_d_claimed_method_code]['chinese_name']}")
print(f"题干对象实际按存取方式分类: {disk_access_method_name}")
print(f"分类判断是否一致: {option_d_method_correct}")
print(f"选项D声称磁盘只能读取不能写入: {option_d_claimed_read_only}")
print(f"按题目分类推导磁盘是否为只读存储器: {disk_is_read_only_classification}")
print(f"特征判断是否一致: {option_d_feature_correct}")
print(f"选项D是否正确: {option_d_is_correct}")

# ===== 汇总答案 =====
option_correctness = {
    "A": option_a_is_correct,
    "B": option_b_is_correct,
    "C": option_c_is_correct,
    "D": option_d_is_correct,
}

correct_options = []

for option_label, is_correct in option_correctness.items():
    print(f"汇总: 选项{option_label} -> {is_correct}")
    if is_correct:
        correct_options.append(option_label)

single_choice_answer = "".join(correct_options)

print("===== 最终答案 =====")
print(f"正确选项列表: {correct_options}")
print(f"单选题答案: {single_choice_answer}")
print(f"ANSWER: {single_choice_answer}")