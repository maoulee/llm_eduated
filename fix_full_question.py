"""Fix data quality issues in full_question.json.

1. 2021 Q19 (index 163): answer D -> C (GT typo, C is the wrong statement about buses)
2. 2021 duplicate Q21 (index 166): -> Q22
3. 2019 (indices 131-143): add missing question numbers
"""
import json
import os

SRC = "data/full_question.json"

with open(SRC, encoding="utf-8") as f:
    data = json.load(f)

# Fix 1: 2021 Q19 answer D -> C
data[163]["answer"] = data[163]["answer"].replace("【参考答案】D", "【参考答案】C", 1)
print("Fix 1: 2021 Q19 D->C")

# Fix 2: 2021 duplicate Q21 -> Q22
data[166]["prompt"] = data[166]["prompt"].replace(
    "[2021年考研真题第21题]", "[2021年考研真题第22题]", 1
)
print("Fix 2: 2021 Q21->Q22")

# Fix 3: 2019 missing question numbers
# Indices 131-141 are Q12-Q22 (MCQs), 142-143 are Q43-Q44 (subjective)
for idx, qnum in enumerate(range(12, 23), start=131):
    old = data[idx]["prompt"]
    data[idx]["prompt"] = old.replace(
        "[2019年考研真题第题]", f"[2019年考研真题第{qnum}题]", 1
    )
    print(f"Fix 3: 2019 [{idx}] -> Q{qnum}")

for idx, qnum in [(142, 43), (143, 44)]:
    old = data[idx]["prompt"]
    data[idx]["prompt"] = old.replace(
        "[2019年考研真题第题]", f"[2019年考研真题第{qnum}题]", 1
    )
    print(f"Fix 3: 2019 [{idx}] -> Q{qnum}")

# Verify fixes
assert "【参考答案】C" in data[163]["answer"]
assert "[2021年考研真题第22题]" in data[166]["prompt"]
assert "[2019年考研真题第12题]" in data[131]["prompt"]
assert "[2019年考研真题第22题]" in data[141]["prompt"]
assert "[2019年考研真题第43题]" in data[142]["prompt"]
assert "[2019年考研真题第44题]" in data[143]["prompt"]
print("\nAll verifications passed!")

DST = os.environ.get("FIX_DST", os.path.expanduser("~/full_question.json"))
with open(DST, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)
print(f"Saved to {DST}")
