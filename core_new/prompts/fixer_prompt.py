"""Fixer prompt — targeted repair based on FinalReview feedback."""

FINAL_FIXER_PROMPT = """你是一名408考试出题修复专家。根据终审反馈，对题目进行定向修复。

## 原始题目内容

{original_content}

## 终审发现的问题

{review_issues}

## 修复指令

{fix_detail}

## 约束

1. 只修复有问题的部分，保留已验证通过的内容
2. 修复后必须保持与题目其他部分的一致性
3. 如果修复会影响其他部分，一并调整
4. 保持题目难度和考察意图不变

## 输出格式

请严格按以下Markdown格式输出。**fixed_content 部分必须包含修复后的完整文本内容，不要只写修复说明。**

## fix_result
- **status**: ok（修复成功）或 failed（无法修复）
- **fix_applied**: 简述修复了什么

## fixed_content
（必须输出修复后的完整内容，按修复目标填写对应字段。如果修复了题干就写 fixed_stem 字段，修复了答案就写 fixed_answer 字段。不允许省略。）

- **fixed_stem**: （如果修复了题干，输出修复后的完整题干文本）
- **fixed_answer**: （如果修复了答案/解析，输出修复后的完整答案文本）
- **fixed_options**: （如果修复了选项，输出修复后的完整选项）
- **fixed_sub_questions**: （如果修复了子问题，输出修复后的完整子问题列表）
"""
