# AVL Insertion Trace (Independent Verification)

Sequence: 16, 3, 7, 11, 9, 26, 18, 14, 15, 20

## Step-by-step

### Insert 16
```
16
```
Balanced.

### Insert 3
```
  16
 /
3
```
bf(16)=1. Balanced.

### Insert 7 → 3's right child
```
  16
 /
3
 \
  7
```
bf(16) = 2-0 = +2. **Unbalanced!** Min-unbalanced root=16. New node 7 in left(3)'s right → **LR**.
Left-rotate on 3, right-rotate on 16 →
```
  7
 / \
3  16
```
Balanced. ✓

### Insert 11 → 16's left child
```
  7
 / \
3  16
   /
  11
```
bf(16)=1, bf(7)=-1. Balanced. ✓

### Insert 9 → 11's left child
```
  7
 / \
3  16
   /
  11
 /
9
```
bf(16)=2-0=+2. **Unbalanced!** Min-unbalanced root=16. New node 9 in left(11)'s left → **LL**.
Right-rotate on 16 →
```
     7
    / \
   3   11
      /  \
     9   16
```
bf(7)=1-2=-1. Balanced. ✓

### Insert 26 → 16's right child
```
     7
    / \
   3   11
      /  \
     9   16
           \
           26
```
bf(16)=0-1=-1, bf(11)=1-2=-1, bf(7)=1-3=-2. **Unbalanced!**
Min-unbalanced root=**7** (NOT 16). New node 26 in right(11)'s right → **RR**.
Left-rotate on 7 →
```
       11
      /  \
     7    16
    / \     \
   3   9    26
```
Balanced. ✓

### Insert 18 → 26's left child (18>16, go right to 26; 18<26, go left)
```
       11
      /  \
     7    16
    / \     \
   3   9    26
           /
          18
```
bf(26)=1-0=1, bf(16)=0-2=-2. **Unbalanced!** Min-unbalanced root=16. New node 18 in right(26)'s left → **RL**.
Right-rotate on 26, left-rotate on 16 →
```
       11
      /  \
     7    18
    / \   / \
   3   9 16  26
```
Balanced. ✓

### Insert 14 → 16's left child
```
       11
      /  \
     7    18
    / \   / \
   3   9 16  26
         /
        14
```
bf(16)=1, bf(18)=2-1=1, bf(11)=2-3=-1. Balanced. ✓

### Insert 15 → 14's right child
```
       11
      /  \
     7    18
    / \   / \
   3   9 16  26
         /
        14
         \
         15
```
bf(14)=0-1=-1, bf(16)=2-0=+2. **Unbalanced!** Min-unbalanced root=16. New node 15 in left(14)'s right → **LR**.
Left-rotate on 14, right-rotate on 16 →
```
       11
      /  \
     7    18
    / \   / \
   3   9 15  26
         / \
        14  16
```
Balanced. ✓

### Insert 20 → 26's left child
```
       11
      /  \
     7    18
    / \   / \
   3   9 15  26
         / \  /
        14 16 20
```
bf(26)=1, bf(18)=2-2=0, bf(11)=2-3=-1. Balanced. ✓

## Summary

5 rebalance events:
1. Insert 7 → LR ✓
2. Insert 9 → LL ✓
3. Insert 26 → RR ✓
4. Insert 18 → RL ✓
5. Insert 15 → LR ✓

Level order: 11, 7, 18, 3, 9, 15, 26, 14, 16, 20 ✓

All final answers match solution.md.
