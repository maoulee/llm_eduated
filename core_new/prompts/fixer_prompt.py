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

请严格按以下Markdown格式输出：

## fix_result
- **status**: ok（修复成功）或 failed（无法修复）
- **fix_applied**: 简述修复了什么

## fixed_content
（修复后的完整内容。根据fix_target，包含对应字段的完整修复后内容。不需要修复的字段不要包含。）
"""
