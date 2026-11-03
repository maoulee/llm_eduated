## assert_scan

检出 **1** 处疑似假 todo（high=1）——请 dual_review 逐条复核，确认是假 todo 的判 needs_fix：

- **[tautology/high]** L77 `assert m == m, "Tag 位数 == m (全相联无行索引)"  # Tag_bits == m` — 自等恒真 (x == x / x is x)
