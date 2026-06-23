# Questions.jsonl Data Cleaning Report

**Generated**: 2026-06-05 14:40:41

## Summary

- **Total Questions**: 2047
- **Output**: `/zhaoshu/llm_eduated/408_export/questions_cleaned.jsonl`
- **Tag Map**: `/zhaoshu/llm_eduated/data/tag_normalization_map.json`

## 1. Question Type Fixes

- 1021 exercise: unknown → choice (had options)
- 32 real_exam: unknown → choice (had options)
- 18 real_exam: unknown → open (no options)

**Result**: choice (94.4%), open (5.6%)

## 2. Subject Fixes

- 950 inferred from knowledge_tags
- 302 inferred from stem content
- 12 encoding issues fixed (mojibake → Chinese)

**Coverage**: 1923/2047 (93.9%)

## 3. Knowledge Tags

- 2564 tags normalized via mapping
- 575 mappings created
- 228 existing hierarchical tags (>) converted to (/)

## 4. Correct Answer

- 4 placeholder values → null
- 1 bold-wrapped → unwrapped

**Coverage**: 1901/2047 (92.9%)

## Files

1. questions_cleaned.jsonl - Cleaned data
2. cleaning_report.md - This report
3. tag_normalization_map.json - Tag mappings
