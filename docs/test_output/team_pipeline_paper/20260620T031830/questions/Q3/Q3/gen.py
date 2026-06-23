# 二维数组列优先存储地址计算 - gen.py

# 参数
M = 5       # 行数
N = 4       # 列数
Base = 1000 # 基地址
L = 4       # 元素大小（字节）
i, j = 2, 1 # 目标元素 A[2][1]

# 正确值：列优先公式 Loc(i,j) = Base + (j*M + i)*L
A = Base + (j * M + i) * L

# 干扰项 B：行优先公式 Loc_row(i,j) = Base + (i*N + j)*L
B = Base + (i * N + j) * L

# 干扰项 C：行列下标颠倒，将 A[i][j]=A[2][1] 误作 A[j][i]=A[1][2]
# 即 i_swap=1, j_swap=2，代入列优先公式 Loc(i_swap, j_swap) = Base + (j_swap*M + i_swap)*L
i_swap, j_swap = j, i  # 交换后 i_swap=1, j_swap=2
C = Base + (j_swap * M + i_swap) * L

# 干扰项 D：忘记乘以元素大小 L
D = Base + (j * M + i)

# 打印结果
print(f"PARAMS: M={M}, N={N}, Base={Base}, L={L}, i={i}, j={j}")
print(f"REASONING:")
print(f"  列优先公式: Loc(i,j) = Base + (j*M + i)*L")
print(f"  A[2][1]: Loc(2,1) = {Base} + ({j}*{M} + {i})*{L} = {Base} + {(j*M+i)}*{L} = {A}")
print(f"  行优先公式: Loc_row(i,j) = Base + (i*N + j)*L")
print(f"  A[2][1]行优先: {Base} + ({i}*{N} + {j})*{L} = {Base} + {(i*N+j)}*{L} = {B}")
print(f"  下标颠倒 A[1][2]: Loc(1,2) = {Base} + ({j_swap}*{M} + {i_swap})*{L} = {Base} + {(j_swap*M+i_swap)}*{L} = {C}")
print(f"  忘记乘L: {Base} + ({j}*{M} + {i}) = {Base} + {(j*M+i)} = {D}")
print(f"ANSWER: A={A}, B={B}, C={C}, D={D}")

# 验证段：通过条件 → assert
# 1. 4选项互异
assert len({A, B, C, D}) == 4, f"选项碰撞: A={A}, B={B}, C={C}, D={D}"

# 2. 正确值唯一确定：A = Base + (j*M + i)*L
assert A == Base + (j * M + i) * L, "正确值计算错误"

# 3. 干扰项对应声明错误类型
assert B == Base + (i * N + j) * L, "B选项（行优先）计算错误"
assert C == Base + (j_swap * M + i_swap) * L, "C选项（下标颠倒）计算错误"
assert D == Base + (j * M + i), "D选项（忘记乘L）计算错误"
