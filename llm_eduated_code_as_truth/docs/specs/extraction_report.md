# Real Exam Data vs slot_extractor.py Coverage Analysis

## Executive Summary

- **Total real_exam questions**: 671
- **Years covered**: 18 (2009-2026)
- **Existing slot observations**: 165
- **Existing question experiences**: 165
- **Evaluated questions (K-ratings)**: 165

## Key Findings

### Data Source Mismatch

The `slot_extractor.py` processes `data/slot_observations.json` (165 questions),
while the real_exam dataset contains 671 questions from `questions.jsonl`.

### New Data Coverage

- **New years in real_exam**: 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026 (18 years)
- **New slots**: CO-6, CO-7, DS-1, DS-2, DS-3, DS-4, DS-5 (7 slots)

### Coverage by Year

| Year | Total | Covered | Missing | Coverage % |
|------|-------|---------|---------|------------|
| 2009 | 40 | 12 | 28 | 30.0% |
| 2010 | 37 | 11 | 26 | 29.7% |
| 2011 | 41 | 12 | 29 | 29.3% |
| 2012 | 36 | 12 | 24 | 33.3% |
| 2013 | 35 | 10 | 25 | 28.6% |
| 2014 | 41 | 11 | 30 | 26.8% |
| 2015 | 36 | 10 | 26 | 27.8% |
| 2016 | 33 | 10 | 23 | 30.3% |
| 2017 | 41 | 12 | 29 | 29.3% |
| 2018 | 38 | 12 | 26 | 31.6% |
| 2019 | 39 | 0 | 39 | 0.0% |
| 2020 | 36 | 11 | 25 | 30.6% |
| 2021 | 36 | 10 | 26 | 27.8% |
| 2022 | 32 | 9 | 23 | 28.1% |
| 2023 | 37 | 12 | 25 | 32.4% |
| 2024 | 37 | 0 | 37 | 0.0% |
| 2025 | 36 | 0 | 36 | 0.0% |
| 2026 | 40 | 0 | 40 | 0.0% |


## Missing Questions by Year

### 2009

- Missing: 28 questions
- Examples: 2009_Q1, 2009_Q2, 2009_Q5, 2009_Q7, 2009_Q8...

### 2010

- Missing: 26 questions
- Examples: 2010_Q1, 2010_Q2, 2010_Q5, 2010_Q6, 2010_Q7...

### 2011

- Missing: 29 questions
- Examples: 2011_Q1, 2011_Q2, 2011_Q3, 2011_Q4, 2011_Q5...

### 2012

- Missing: 24 questions
- Examples: 2012_Q1, 2012_Q2, 2012_Q3, 2012_Q5, 2012_Q8...

### 2013

- Missing: 25 questions
- Examples: 2013_Q1, 2013_Q2, 2013_Q5, 2013_Q6, 2013_Q10...

### 2014

- Missing: 30 questions
- Examples: 2014_Q1, 2014_Q2, 2014_Q3, 2014_Q5, 2014_Q6...

### 2015

- Missing: 26 questions
- Examples: 2015_Q1, 2015_Q2, 2015_Q3, 2015_Q4, 2015_Q8...

### 2016

- Missing: 23 questions
- Examples: 2016_Q2, 2016_Q5, 2016_Q7, 2016_Q9, 2016_Q10...

### 2017

- Missing: 29 questions
- Examples: 2017_Q1, 2017_Q2, 2017_Q3, 2017_Q4, 2017_Q6...

### 2018

- Missing: 26 questions
- Examples: 2018_Q1, 2018_Q2, 2018_Q3, 2018_Q4, 2018_Q8...

### 2019

- Missing: 39 questions
- Examples: 2019_Q1, 2019_Q2, 2019_Q3, 2019_Q7, 2019_Q8...

### 2020

- Missing: 25 questions
- Examples: 2020_Q1, 2020_Q2, 2020_Q3, 2020_Q6, 2020_Q8...

### 2021

- Missing: 26 questions
- Examples: 2021_Q2, 2021_Q3, 2021_Q4, 2021_Q5, 2021_Q9...

### 2022

- Missing: 23 questions
- Examples: 2022_Q1, 2022_Q2, 2022_Q4, 2022_Q9, 2022_Q10...

### 2023

- Missing: 25 questions
- Examples: 2023_Q1, 2023_Q3, 2023_Q6, 2023_Q7, 2023_Q8...

### 2024

- Missing: 37 questions
- Examples: 2024_Q1, 2024_Q2, 2024_Q3, 2024_Q5, 2024_Q6...

### 2025

- Missing: 36 questions
- Examples: 2025_Q2, 2025_Q4, 2025_Q5, 2025_Q6, 2025_Q8...

### 2026

- Missing: 40 questions
- Examples: 2026_Q1, 2026_Q2, 2026_Q3, 2026_Q4, 2026_Q5...

## Recommendations

### 1. Data Integration

- The 671 real_exam questions need to be converted to slot_observations.json format
- Key mapping needed: question_type, question_stem, knowledge_tags → target_family, primary_target_name
- Subject field needs normalization (encoding issues detected)

### 2. Slot Mapping Expansion

- Current slot_extractor.py only handles Q12-Q22, Q43-Q45 slots
- Need to add mappings for Q1-Q11 (data structure, OS, network, CO)
- Use existing slot_id field in real_exam data for mapping

### 3. Processing New Data

- Run slot_extractor.py in eval-only mode first: `python slot_extractor.py --eval-only`
- Then full pipeline: `python slot_extractor.py --resume`
- Expected output: 671 question experiences + ~35 slot templates

### 4. Encoding Fixes

- Fix corrupted subject names in source data (ж"Қд*ѕзі»з»џ → 操作系统)
- Normalize knowledge tags across datasets

## Required Actions

1. Convert real_exam questions to slot_observations format
2. Merge with existing slot_observations.json
3. Run slot_extractor.py with --resume flag
4. Validate outputs against new data coverage
