# 练习题 Q1 — 银行家算法与安全状态判定

## 基本信息
- **来源**: 练习题  **题型**: 选择题
- **科目**: 操作系统
- **知识点**: 操作系统/死锁
- **难度**: 中等偏难（需完整执行安全算法）

## 题干原文
一个操作系统在管理三个进程 P0、P1 和 P2 对三种资源类型 X、Y 和 Z 的分配时，使用银行家算法进行死锁避免。下表展示了当前系统状态。其中，Allocation 矩阵显示了每个进程当前分配的每种资源数量，Max 矩阵显示了每个进程在其执行过程中所需的每种资源最大数量。
Allocation Max
 X Y Z X Y Z
P0 0 0 1 8 4 3
P1 3 2 0 6 2 0
P2 2 1 1 3 3 3
目前仍有 3 个单位的 X 资源、2 个单位的 Y 资源和 2 个单位的 Z 资源可用。系统当前处于安全状态。考虑以下两个独立的额外资源请求：
REQ1: P0 请求 0 个 X 单位，
0 个 Y 单位和 2 个 Z 单位
REQ2: P1 请求 2 个 X 单位，
0 个 Y 单位和 0 个 Z 单位
以下哪一项是正确的？（ ）
- 选项:
  A: 仅 REQ1 可以被允许。
  B: 仅 REQ2 可以被允许。
  C: REQ1 和 REQ2 都可以被允许。
  D: REQ1 和 REQ2 都不能被允许
- 正确答案: B
- 解析（参考）: 解析
这是当前的安全状态：
AVAILABLE（可用资源）：X=3，Y=2，Z=2

 MAX ALLOCATION
 X Y Z X Y Z
P0 8 4 3 0 0 1
P1 6 2 0 3 2 0
P2 3 3 3 2 1 1
现在，如果允许请求 REQ1，状态将变为：
AVAILABLE：X=3，Y=2，Z=0

 MAX ALLOCATION NEED
 X Y Z X Y Z X Y Z
P0 8 4 3 0 0 3 8 4 0
P1 6 2 0 3 2 0 3 0 0
P2 3 3 3 2 1 1 1 2 2
在当前资源可用的情况下，我们可以满足 P1 的需求。状态将变为：
AV
- 知识标签: ['操作系统/死锁']
- 知识域: OS-1

## K1-K5 评分与解析
- **K1 = 3**: 评分理由。需要掌握银行家算法的核心概念（Max, Allocation, Need, Available）以及安全状态的定义。属于标准的核心定义记忆，不涉及易混概念的深度辨析，但必须准确理解各矩阵含义。
- **K2 = 3**: 评分理由。涉及矩阵加减运算（Need = Max - Allocation, Available - Request, Allocation + Request）。虽然数字较小，但涉及三个维度（X, Y, Z）和三个进程，单步计算量适中，非2的幂次友好型，容易因粗心出错。
- **K3 = 4**: 评分理由。这是本题的核心难点。对于每个请求，都需要执行完整的“安全性算法”推演：1. 检查请求合法性；2. 试探性分配；3. 寻找安全序列（可能需要多轮尝试，如先满足P1再满足P2等）。这是一个多步串行推演过程，且需记忆中间状态，步骤超过5步。
- **K4 = 3**: 评分理由。存在常规注意点陷阱。例如，REQ1中P0请求Z资源，需检查Request <= Need 和 Request <= Available。更深层的陷阱在于，即使试探性分配后资源看似不足，仍需通过寻找安全序列来最终判定，而非直接拒绝。考生容易忽略“独立请求”的前提，或者在寻找安全序列时遗漏某个进程。
- **K5 = 1**: 评分理由。本题完全局限于操作系统死锁避免子系统内部，不涉及文件系统、内存管理或其他子系统的状态传递或耦合。

- **雷达形状**: K3推演主导型（K3显著高于其他维度，K1/K2基础支撑，K4中等陷阱）

## 考察模式
- **模式**: 推理型
- **理由**: 本题不仅仅是简单的公式代入，而是要求考生模拟操作系统内核中的银行家算法逻辑，通过多步假设、验证、回溯（寻找安全序列）来推导系统状态的安全性。核心在于逻辑推演而非单纯计算。

## 选项级分析
- **选项A**: [干扰] — 针对错误认知：认为REQ1可行。这类学生可能只检查了REQ1的初步合法性（Request <= Available），或者在试探性分配后，错误地认为剩余资源足以满足所有进程，或者在寻找安全序列时漏掉了P0对Z资源的巨大需求（Need Z=0，但已分配3，Max 3，Wait, P0 Need Z = 3-3=0? No, Max Z=3, Alloc Z=1+2=3, Need Z=0. Wait, let's re-calc carefully. P0 Max Z=3, Alloc Z=1. Req Z=2. New Alloc Z=3. Need Z = 3-3=0. P1 Need Z=0. P2 Need Z=2. Avail Z=0. P2 needs 2 Z. Cannot satisfy P2. P0 needs 0 Z. P1 needs 0 Z. So P0 and P1 can finish. P2 waits. But P2 holds resources. If P0 and P1 finish, they release resources. P0 releases 0,0,3. P1 releases 3,2,0. Total released: 3,2,3. Avail becomes 3,2,3. Then P2 can run. So REQ1 IS SAFE? Let me re-read the reference answer. Reference says B is correct. Let me re-evaluate REQ1 carefully.
    *   **Re-evaluation of REQ1**:
        *   Initial: Avail=[3,2,2].
        *   P0 Req=[0,0,2]. Check: Req <= Need? P0 Need=[8,4,2]. Req[0,0,2] <= [8,4,2]. OK. Req <= Avail? [0,0,2] <= [3,2,2]. OK.
        *   Tentative State:
            *   Avail = [3,2,0]
            *   P0 Alloc = [0,0,3], P0 Need = [8,4,0]
            *   P1 Alloc = [3,2,0], P1 Need = [3,0,0]
            *   P2 Alloc = [2,1,1], P2 Need = [1,2,2]
        *   Safety Algorithm:
            *   Work = [3,2,0], Finish = [F,F,F]
            *   Find P where Finish=F and Need <= Work.
            *   P0 Need [8,4,0] <= [3,2,0]? No (8>3, 4>2).
            *   P1 Need [3,0,0] <= [3,2,0]? Yes.
                *   Execute P1. Work = Work + P1 Alloc = [3,2,0] + [3,2,0] = [6,4,0]. Finish[P1]=T.
            *   Find P where Finish=F and Need <= Work.
            *   P0 Need [8,4,0] <= [6,4,0]? No (8>6).
            *   P2 Need [1,2,2] <= [6,4,0]? No (2>0).
            *   No process can proceed. Deadlock/Unsafe.
        *   **Conclusion**: REQ1 leads to an unsafe state. So REQ1 is NOT allowed.
    *   **Analysis of Option A**: Students who choose A likely failed to complete the safety check, stopping after the first step or incorrectly assuming P0 could run immediately. They might have missed that P0's Need for X and Y is still high, and P2's Need for Z cannot be met by the remaining 0 Z resources, and P1's release doesn't provide Z.

- **选项B**: [正确] — 针对正确认知：REQ1导致不安全，REQ2导致安全。
    *   **Re-evaluation of REQ2**:
        *   Initial: Avail=[3,2,2].
        *   P1 Req=[2,0,0]. Check: Req <= Need? P1 Need=[3,0,0]. Req[2,0,0] <= [3,0,0]. OK. Req <= Avail? [2,0,0] <= [3,2,2]. OK.
        *   Tentative State:
            *   Avail = [1,2,2]
            *   P1 Alloc = [5,2,0], P1 Need = [1,0,0]
            *   P0 Alloc = [0,0,1], P0 Need = [8,4,2]
            *   P2 Alloc = [2,1,1], P2 Need = [1,2,2]
        *   Safety Algorithm:
            *   Work = [1,2,2], Finish = [F,F,F]
            *   P0 Need [8,4,2] <= [1,2,2]? No.
            *   P1 Need [1,0,0] <= [1,2,2]? Yes.
                *   Execute P1. Work = [1,2,2] + [5,2,0] = [6,4,2]. Finish[P1]=T.
            *   P0 Need [8,4,2] <= [6,4,2]? No (8>6).
            *   P2 Need [1,2,2] <= [6,4,2]? Yes.
                *   Execute P2. Work = [6,4,2] + [2,1,1] = [8,5,3]. Finish[P2]=T.
            *   P0 Need [8,4,2] <= [8,5,3]? Yes.
                *   Execute P0. Work = [8,5,3] + [0,0,1] = [8,5,4]. Finish[P0]=T.
            *   All finished. Safe.
        *   **Conclusion**: REQ2 is allowed.

- **选项C**: [干扰] — 针对错误认知：认为两个请求都合法。这类学生可能只检查了请求是否小于等于可用资源（Request <= Available），而忽略了后续的“安全性算法”验证。这是最常见的错误，混淆了“请求合法”与“系统安全”。

- **选项D**: [干扰] — 针对错误认知：认为两个请求都不合法。这类学生可能在REQ2的安全性检查中出错，例如错误计算了Need矩阵，或者在寻找安全序列时未能找到正确的顺序（如先P1再P2再P0），导致误判为不安全。

- **干扰策略**: 概念混淆（混淆“请求合法性检查”与“安全性检查”）+ 计算陷阱（在REQ1的安全性推演中，容易忽略P2对Z资源的依赖以及P1释放资源后仍无法满足P2的情况）。

## 核心陷阱
- **核心陷阱**: **混淆“请求合法性”与“系统安全性”**。
    1.  **REQ1的陷阱**：REQ1在初步检查（Request <= Need 且 Request <= Available）中是合法的。许多考生在此止步，认为合法即可允许。实际上，必须执行安全性算法。在REQ1的试探性分配后，虽然P1可以运行，但P1运行结束后释放的资源不足以让P0或P2继续运行（P0缺X/Y，P2缺Z），导致系统进入不安全状态。
    2.  **REQ2的陷阱**：REQ2同样初步合法。关键在于能否找到安全序列。考生需要正确计算出新的Need矩阵，并发现序列 P1 -> P2 -> P0 是可行的。如果计算错误（如Need算错）或搜索顺序不当，可能误判为不安全。

## 考察能力
本题核心考察考生对**银行家算法安全性检查流程**的完整执行能力，包括矩阵运算、状态试探性更新以及多步安全序列搜索的逻辑推演能力。
