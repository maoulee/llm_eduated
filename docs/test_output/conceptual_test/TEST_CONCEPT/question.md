# Q45 概念题组——银行家算法与安全状态

## 第 1 题

关于操作系统中"安全状态"与"死锁状态"的关系，下列三个论断：

- I．处于安全状态的系统一定不会发生死锁
- II．处于不安全状态的系统一定会发生死锁
- III．死锁状态一定是不安全状态

以上论断中，正确的组合是（ ）。

A．仅 I

B．I 和 III

C．II 和 III

D．I、II 和 III

---

## 第 2 题

在银行家算法中，当进程 P_i 提出一组资源请求 Request_i 时，系统需要依次执行一系列检查才能决定是否批准该请求。下列关于检查执行顺序的描述，正确的是（ ）。

A．先检查 Request_i ≤ Need_i，若通过再检查 Request_i ≤ Available，若通过则执行试探性分配并运行安全性算法，安全性算法判定安全后正式批准请求

B．先检查 Request_i ≤ Available，若通过再检查 Request_i ≤ Need_i，若通过则执行试探性分配并运行安全性算法，安全性算法判定安全后正式批准请求

C．先检查 Request_i ≤ Need_i，若通过则执行安全性算法，若安全性算法判定安全再检查 Request_i ≤ Available，最后正式批准请求

D．先执行安全性算法判断当前系统是否安全，再检查 Request_i ≤ Need_i 和 Request_i ≤ Available，最后正式批准请求

---

## 第 3 题

在银行家算法的安全性检查算法中，系统需要维护工作向量 Work 和完成标志向量 Finish。关于 Work 和 Finish 的使用方式，下列描述正确的是（ ）。

A．Work 的初始值设为 Available 向量的副本，Finish 的所有分量初始化为 false；每轮从尚未完成的进程中寻找满足 Need_i ≤ Work 的进程 P_i，将其 Allocation_i 加入 Work，并标记 Finish_i = true；当所有 Finish 分量均为 true 时，系统处于安全状态

B．Work 的初始值设为 Available 向量的副本，Finish 的所有分量初始化为 true；每轮从所有进程中寻找满足 Need_i ≤ Work 的进程 P_i，将其 Need_i 加入 Work，并标记 Finish_i = false；当所有 Finish 分量均为 false 时，系统处于安全状态

C．Work 的初始值设为所有进程 Allocation 之和，Finish 的所有分量初始化为 false；每轮从尚未完成的进程中寻找满足 Need_i ≤ Work 的进程 P_i，将其 Need_i 加入 Work，并标记 Finish_i = true；当所有 Finish 分量均为 true 时，系统处于安全状态

D．Work 的初始值设为所有进程 Need 之和，Finish 的所有分量初始化为 false；每轮从尚未完成的进程中寻找满足 Max_i ≤ Work 的进程 P_i，将其 Allocation_i 加入 Work，并标记 Finish_i = true；当所有 Finish 分量均为 true 时，系统处于安全状态

---

## 第 4 题

下列关于银行家算法的叙述中，**错误**的是（ ）。

A．Need 矩阵表示各进程尚需的各类资源最大数量，其中 Need[i][j] = Max[i][j] − Allocation[i][j]

B．某进程的资源请求通过了 Request_i ≤ Need_i 检查但未通过 Request_i ≤ Available 检查时，该进程必须等待，系统暂时不分配资源

C．试探性分配后执行安全性算法，若判定系统处于安全状态，则将试探性分配正式确认；若判定系统处于不安全状态，则回滚试探性分配，拒绝该请求

D．某进程的资源请求同时通过了 Request_i ≤ Need_i 和 Request_i ≤ Available 两步检查后，系统即可直接批准该请求并正式分配资源，无需再执行安全性算法
