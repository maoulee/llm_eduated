# kcard/prompt_builder.py

from typing import Dict, Optional

def format_question_for_kcard_extraction(
    q_data: Dict,
    enable_rich_formatting: bool = False,
    question_key: str = "Question"
) -> str:
    """
    根据问题数据的元数据，动态地将其格式化为一个丰富的、
    适合知识卡片抽取的字符串。

    Args:
        q_data (Dict): 从.jsonl文件中读取的单个问题数据字典。
        enable_rich_formatting (bool): 是否启用丰富的、基于类型的格式化。
        question_key (str): 字典中包含问题主干文本的键。

    Returns:
        str: 格式化后的、用于输入到KnowledgeEngineer的字符串。
    """
    # 如果禁用丰富格式化，或者问题数据中没有'Format'键，则返回原始问题文本
    if not enable_rich_formatting or "Format" not in q_data:
        return q_data.get(question_key, "")

    # --- 开始丰富的格式化 ---
    
    question_text = q_data.get(question_key, "")
    q_format = q_data.get("Format", "Open-ended")
    q_tag = q_data.get("Tag", "Knowledge")
    
    # 构建一个包含元数据的头部
    header = f"[题目类型: {q_format} | 考察方向: {q_tag}]\n"
    
    # 主体内容
    body = f"问题: {question_text}\n"

    # 根据不同类型添加特定信息
    if q_format == "Multiple-choice":
        options_parts = []
        for key in sorted(q_data.keys()): # Sort keys to ensure consistent order (A, B, C, D)
            if key.upper() in ["A", "B", "C", "D", "E"]:
                options_parts.append(f"- 选项 {key}: {q_data[key]}")
        
        if options_parts:
            body += "选项:\n" + "\n".join(options_parts) + "\n"
        
        if "Answer" in q_data:
            answer_key = str(q_data["Answer"])
            answer_text = q_data.get(answer_key, f"选项 {answer_key}")
            body += f"正确答案: {answer_key}. {answer_text}\n"

    elif q_format == "Fill-in-the-blank":
        if "Answer" in q_data:
            answer = q_data["Answer"]
            # For fill-in-the-blank, the answer is often a list or a single value
            body += f"参考答案: {answer}\n"

    elif q_format == "Assertion":
        if "Answer" in q_data:
            # Answer is typically True/False or A/B for correct/incorrect
            answer = q_data["Answer"]
            body += f"正确判断: {answer}\n"
    
    # For Open-ended, the question body is usually sufficient.
    # We can add a placeholder for a reference answer if available.
    elif q_format == "Open-ended":
         if "Answer" in q_data:
            answer = q_data["Answer"]
            body += f"参考答案摘要: {answer}\n"

    return header + body