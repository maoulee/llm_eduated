# -*- coding: utf-8 -*-
# N=74 n1=1: n0c=37, n2c=36
# A=37, D(混淆)=36, C(漏减n1)=38
# Need B != 36,37,38
#
# Natural error that produces a different value:
# "把 n0 = n2 + 1 误记为 n0 = n2 * 2" -> 3*n2 = 73, non-integer
# "把度数和方程写成 n0 + n2 = N (漏n1), 用 n0=n2+1 -> n2=(N-1)/2=36, n0=37" -> =A
#
# Actually the cleanest fix: make C the "double error" and B the "漏减n1"
# 
# B = 漏减n1 = 38
# C = ??? different
# D = 混淆 = 36
# A = 37
# Need C != 36,37,38
#
# What natural error gives C outside {36,37,38}?
# "把 N 误记为 N-2=72": n0=(72-1+1)/2=36 -> =D
# "把 N 误记为 N+2=76": n0=(76-1+1)/2=38 -> =B(漏减n1)
#
# The real issue: n0=n2+1 means n0c-n2c=1 always. So all ±1 linear errors
# fall in {n2c, n0c, n0c+1}. Only non-linear errors escape.
#
# Cleanest solution: CHANGE PARAMETER N to break this.
# If we use n1=0 and odd N, the "漏减n1" error becomes meaningful differently.
# But n1=0 means question says "度为1的结点数为0" which is valid.
# 
# n1=0: n0c=(N+1)/2, n2c=(N-1)/2
# 记反/混淆 = n2c = (N-1)/2
# 漏减n1 doesn't apply (n1=0)
# So we need a DIFFERENT second error for n1=0 case
#
# n1=0 errors: 
#   - 混淆n0/n2 = n2c = (N-1)/2
#   - 记反 = same
#   - "误认为 n0 = n2 (忽略+1)": n0=(N-1)/2=n2c -> same
#   - "误认为 n0 = (N+1)//2 + 1" = n0c+1 
#   - "误认为 n0 = N/2 向下取整" = N//2
#
# With n1=0, N=73 (odd): n0c=37, n2c=36
# Same values! Because (N+1)/2 and (N-1)/2 for N=73 are 37 and 36.
#
# The fundamental issue persists regardless of n1.
# 
# SOLUTION: Use 4 options where B and C are the two genuinely different
# errors (漏减n1=38, 混淆=36), and make D a value that differs from all.
# The ONLY natural way: D uses a completely different mistake.
#
# Most natural for D: "误用 n0 = N - n2 但同时用了错误的 n2"
#   = "把 n2 当成 n0 + n1 = 37+1 = 38, 然后 n0 = N - 38 = 36" -> =混淆
#
# OK let me just try: D = n0 + n2 = 73 (sum instead of individual)
# Error type: "把 n0+n2 的和当作 n0" 
# Not great but it IS a real student mistake (confusing partial result with final)

N, n1 = 74, 1
n0c = (N - n1 + 1) // 2  # 37
n2c = (N - n1 - 1) // 2  # 36

# Option A = 37 (correct)
# Option B = 36 (混淆n0/n2: 把n2当n0)
# Option C = 38 (漏减n1)
# Option D = 73 (把n0+n2的和当n0) -- but this is too far from 37, bad distractor

# Better: D = n2 - 1 = 35 (误选n2且又减了1: "以为叶子=n2-1=正确记反")
#   = 35, distinct from 36,37,38
# Error: "记反 n0=n2-1 联立得 n2=37, 但把n2当n0选 -> 37=A"... no
# 
# D=35: "正确求n2=36, 然后误记n0=n2-1=35" (二次错误, 不自然)

# === FINAL DECISION ===
# The cleanest approach: B(记反公式) genuinely gives n0=36 which equals D(混淆)=36.
# These are the SAME mathematical result. I should NOT have both.
# 
# Replace B with the 漏减n1 error (38), and replace C with a different error.
# Or: keep C=漏减n1=38, D=混淆=36, and make B something genuinely different.
#
# The most natural 4th error that gives a unique value:
# "将 n0 = n2 + 1 误用为 n0 = n2 + n1 + 1" 
#   = n2 + 2 = 38 -> collides with C
#
# "将 n0 = n2 + 1 误用为 n0 = 2*(n2+1)" 
#   = 2*37 = 74 -> too big, weird
#
# "将 n0 = n2 + 1 误用为 n0 = (n2+1)*n1"
#   = 37*1 = 37 -> collides
#
# OK. The ONLY way to get 4 distinct values with this knowledge point
# is to use a parameter where non-linear errors produce integers.
# OR accept 3 distinct + 1 far-off.
#
# SIMPLEST ACCEPTABLE: B = 漏减n1 = 38, C = 记反/混淆 = 36, D = n2 = 36... collide
#
# ACTUALLY: let me re-examine the question design.
# D says "误将n2的值当作n0" = n2c = 36
# B says "记反n0=n2-1" -> solving gives n0 = 36 too
# C says "漏减n1" -> gives 38
# A = 37
#
# B and D both = 36. This is the collision.
# Fix: REMOVE one of them, add a genuinely different error.
#
# I'll change B's error to: "忽略性质公式n0=n2+1, 只用n0+n2=N-n1, 
#   误认为n0=n2" -> n0=(N-n1)//2 = 36 -> same as D
#
# Change B to: "误把n1当作n0" -> n0=1 -> absurd
#
# Change B to: "把N当成n0" -> 74 -> absurd
#
# The real fix: change D's error type instead.
# D = "联立时把n1加到等式右边: n0+n2=N+1=75" -> n0=(75+1)/2=38 -> =C
#
# D = "把N-n1=73当成n0" -> 73, distinct but far
# 
# I'll use: B=漏减n1=38, C=混淆n0/n2=36, D=n0+n2=73(部分和误当n0)
# No, 73 is too far. Bad distractor.
#
# ===== ULTIMATE FIX: Change N to 57, n1=1 =====
# N=57: odd. N-n1=56=even. NOT valid (needs odd).
# N=58, n1=1: N-n1=57=odd. OK.
# n0c=(58-1+1)/2=29, n2c=(58-1-1)/2=28
# 混淆/记反 = 28
# 漏减n1: 58-(58-1)//2=58-28=30  (wait (57)//2=28, so C=58-28=30)
# A=29, B=28, C=30, D=28 -> B=D collide again
#
# SAME PROBLEM. 记反 ALWAYS = n2c = 混淆.
# This is a mathematical theorem: n0=n2+1 reversed gives n0=n2-1,
# solving which yields n0=n2_original.
#
# ====== THE REAL FIX ======
# Merge B(记反) and D(混淆) since they're the same value.
# Use: A=37(正确), B=36(混淆n0/n2), C=38(漏减n1), 
#      D = a genuinely different error that gives a unique value.
#
# The most natural D that gives unique value:
# "把 n0 = n2 + 1 记成 n0 = n2 + 1 的推导中, 误将 n2 = n0 + 1 代入"
#   -> n0 + (n0+1) + 1 = N -> 2*n0 = 72 -> n0 = 36 -> = B
#
# "把 n0 = n2 + 1 记成 n0 = n2 = N - n0 - 1 代入自己"
#   circular, nonsensical
#
# D = 35: "误认为 n0 = n2 + 1 但 n2 少算了1 (n2=35), n0=36" -> =B
# D = 35: "误认为 n0 = n2 - 1 且用正确n2=36" -> n0=35 ✓ DISTINCT!
#   Error type: "记反公式n0=n2-1, 但用正确方法求出的n2=36, 直接代入n0=n2-1=35"
#   This is actually natural! Student remembers n0=n2-1 (reversed),
#   correctly finds n2=36, then plugs in to get n0=35.
#
# Wait, but the question asks for n0. If student uses n0=n2-1:
#   Method 1: solve system n0=n2-1 & n0+n1+n2=N -> n0=36 (= n2c)
#   Method 2: solve correctly for n2=36, then n0=n2-1=35
#   These are TWO DIFFERENT applications of the same wrong formula!
#   Method 1 (system) gives 36, Method 2 (plug) gives 35.
#   Both are natural student mistakes!

# Let me verify:
print("=== Method 1: solve system with wrong formula ===")
print(f"  n0=n2-1 & n0+n1+n2=N=74")
print(f"  (n2-1)+n2=73 -> 2*n2=74 -> n2=37, n0=36")
print(f"  Result: n0=36")
print()
print("=== Method 2: solve n2 correctly, then apply wrong formula ===")
print(f"  Correctly: n2=(74-1-1)/2=36")
print(f"  Wrong: n0=n2-1=36-1=35")
print(f"  Result: n0=35")
print()
print(f"A=37, B=36(系统记反), C=38(漏减n1), D=35(正确求n2后记反代入)")
print(f"互异? {len(set([37,36,38,35]))==4}")
