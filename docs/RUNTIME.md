# A 阶段首局闭环

更新：2026-11-07。按中途审查修正 M1/M2/M3/M5/M6，仍未完成 A 阶段验收。游戏参数、结算和协议未改；计分仍未实现，用户决定和已批准 D1–D10 已纳入 DESIGN/BRIEF。

## 运行一局

在当前 WSL 工作区使用 Python 3.13；不直接执行 bot 或 g++：

```sh
.venv/bin/python -m arena match \
  --a sdk/python/example --b sdk/cpp/example \
  --map tests/fixtures/smoke.map
```

`smoke.map` 只是 24×24 的对称测试地图，不满足 DESIGN 7.2 的完整资源布局要求，不是 public 地图集。现在也可使用 `maps/public/*.map` 和 `maps/scrimmage/*.map`；44 张 v2 地图已通过 D5 步行距离及逐字节再生检查。`mapgen/mapcheck` 用法见 `maps/README.md`，平衡尚未验收。两种示例会采矿、返家卸货、偶尔出兵；未校准强度。

命令输出本局结果和回放路径。`--out` 默认 `runs/matches`，`--seeds` 默认 `17 29`。每次调用产生新的 UUID 目录；其中 `results.jsonl` 追加记录每次尝试，`attempt-N/` 保存双方源码及 SDK 快照、编译输出、最多 64 KiB 的各方 stderr、结果和回放。`--show-stderr` 可显示最后一次尝试的 bot stderr，并转义终端控制字符。不会覆盖以前的对局。

```sh
.venv/bin/python -m arena replay verify <对局号>.hrw.jsonl.gz
.venv/bin/python -m arena replay show <对局号>.hrw.jsonl.gz --turn 25
.venv/bin/python -m arena replay summary <对局号>.hrw.jsonl.gz
```

`verify` 不运行 bot 或编译器，只重新解析保存的回复、结算并核对接受指令、INVALID 事件、逐回合哈希和最终结果。它也验证故障判负局的最后完整局面；缺少结果、文件截断、记录重复、地图或状态不符会报错。它不是计时真实性或来源签名校验。`summary` 每 25 回合报告能量、单位数、塔数和分数；`show` 的回合 0 是初始局面。

## 代码与格式

- `arena/core/sandbox.py`：快照、bwrap 启动、沙箱编译、CPU 时钟采样和资源上限。
- `arena/core/transport.py`：非阻塞管道、同时收发、READY/END 分帧、输出限制和超时。
- `arena/core/runner.py`：只通过 Game 接口发送观察、解析指令和结算；维护时间储备。
- `arena/core/replay.py`：不依赖游戏的 gzip JSONL 写入。
- `arena/games/outpost/replay.py`：前哨的结果、统计与重放适配。
- `arena/match.py`：前哨对局编排、失败归档和重试。

回放版本为 1：文件头保存全部参数、地图全文及摘要、bot/SDK 内容摘要、种子、时限、绑核、开始时间和初始哈希；随后是初始化、每回合或故障记录，最后是结果。每回合保存有界回复、接受的指令、作废原因、CPU/墙钟纳秒数、储备和状态哈希。回复中的非法 UTF-8 字节逐字节记为禁用的 NUL 字符，使引擎拒绝该行但仍按原始字节数计算上限，避免挤掉后续合法指令。bot 摘要由源码快照和 SDK 快照的路径/文件 SHA-256 清单组合得出，不等于单个可执行文件摘要。格式尚未发布，后续只增字段。

## 现在的安全与计时边界

宿主上的实际 bot 和 C++ 编译都使用 bwrap；没有 plain 回退。外层沙箱内的本地工具可显式使用 plain，契约及边界见 `docs/BATCH.md`。沙箱不联网，不挂载 Agent HOME、宿主 `/etc`、整个项目或另一个 bot，只挂载系统运行库、Python 安装目录、本方源码和公开 SDK。源码与运行时构建产物只读；编译时仅本方构建目录可写。启动环境使用固定白名单，不继承代理、认证或个人配置。

每个 bot 在本局内绑定不同 CPU，运行时 512 MiB 地址空间、16 MiB 单文件、64 个文件描述符、整局 CPU 硬限额、禁用 core dump。C++ 编译为 GCC 11 的 `-O2 -std=gnu++20 -I/sdk`，墙钟/CPU均上限60秒、逐进程地址空间2 GiB、任务数16、单文件64 MiB；prepare路径共用编译锁，不论缓存目录一次只运行一个编译器。临时文件位于本方磁盘构建目录，避免编译器写无界 RAM tmpfs。

运行时由标准库生成的 x86-64 seccomp BPF 强制禁止 fork/vfork、非线程 clone 和 sched_setaffinity；clone3 返回 ENOSYS，使 Python/glibc/C++ 线程回退到受检查的 clone。拒绝 i386/x32 或未知宿主架构。可信启动器在新 user namespace 内设置 RLIMIT_NPROC=16，包含管理进程、主线程和工作线程；本机 Python/C++ 均实测最多 14 个工作线程。拒绝以 root 宿主 UID 使用此启动器，避免 RLIMIT_NPROC 豁免。

合成根目录 `/`、`/tmp`、`/dev` 文件系统运行时只读，阻止通过大量临时文件耗尽 RAM；memfd、SysV IPC和POSIX消息队列分配也被禁用，避免这些途径绕过地址空间限额。补查发现只限制 `/tmp` 仍允许在 bwrap 合成根 tmpfs 写文件，因此新增根目录回归并修正，前后失败/通过日志均保留；回放运行策略版本升到3。此只读选择已经公开写入 `rules/rules.md`，不是承诺可写 64 MiB；plain 本地工具也已明示相同评分限制，但其文件隔离由外层负责。

策略v4补齐父死亡窗口：fork前记下父PID，preexec先安装SIGKILL再核对父PID，不能只依赖exec之后的bwrap。运行时seccomp拒绝清除/更改PDEATHSIG；可信worker同样在fork到exec间受保护，再切换到可清理的SIGTERM处理。启动后持久化sandbox-pids sidecar用于诊断；PID属于当时执行命名空间，不应当作任意宿主PID发信号。

跨命名空间进程 CPU 时钟累计全部线程（含已退出线程），只遍历可信启动进程的 leaders/children，不再每 2 ms 遍历全部线程。bot 不得创建子进程；找不到活动进程的 proc 接口或无法定位可计量后代时 fail closed。时钟不可用仍标记回退 `/proc/<pid>/stat`。完整清理/压力矩阵及平台兼容验收仍未完成，不将这些修正夸大为完整恶意提交服务安全认证。

`bench --jobs N` 和独立 `match --timing` 已实现，见 `docs/TIMING.md`、`data/timing.json`。独立match仅接受jobs=1结果；批量调度器在相同CPU池/jobs下测量后接线，backend也须匹配。时限、BANK、墙钟余量和CPU硬上限同时折算，回放记录系数、参考及校准摘要。未提供校准时 `speedFactor` 仍为 `null`，明确使用未折算的开发默认时限，不冒充正式评分。每回合 CPU 为这次 END 与上次 END 的累计读数之差，第一回合基线为 READY；END 后直到下次发消息之间的后台计算也计入下一回合。管道就绪仍立即唤醒；忙等bot的看门狗采样上限改为50ms，并取剩余CPU/墙钟预算的更小值，不放宽短时限。此前2ms轮询的额外proc扫描已用定点反例和整局效率数据验证，见 `docs/TIMING.md`。`BANK` 内部按纳秒扣除超额，不回充，消息显示向下取整的毫秒数。墙钟兜底包括本回合预算、剩余储备和 500 ms；初始化为初始化预算加 500 ms。两方均发送观察后并发收取回复，不把两方思考串行相加。

提交格式不合规和编译失败均判提交方负，并保存 validation/compile 原因；拒绝的源码无法给出完整摘要时，回放 bot 摘要为 null，不虚构内容哈希。可信启动标记后的任何退出（包括 125）都是 bot 故障；同一次收取中的双方故障判平。未收到启动标记或其他框架异常不产生胜负，默认初次加最多 3 次重试。隐藏 bot 编译/格式问题属于配置错误，不让提交方获胜，也不盲目重试；已批准的 I09–I10 保持故障回合不结算。

## 平台状态

`check`、内容摘要编译缓存、全局CPU租约、进程调度/共享JSONL/续跑和`tournament`已接入，见 `docs/BATCH.md`。新回放含可重算的原始诊断指标v2，仍验证旧回放。外层bwrap内已实跑plain的Python/C++工具链；SIGTERM杀死controller后已验证worker清理及续跑不重复任务。

新补512MiB地址空间/64描述符、已退出线程计费、网络/路径/只读检查、有限编译进程树清理，以及6局/12bot并发线程超时压力；全部已知沙箱leader停止，回放全部验证，见 `data/phase-a-security.json`。旧编译探针显示NPROC继承63593，原证据保留。按第二次审查裁定，已改NPROC=16、单文件64MiB和全局串行锁，真实bwrap及跨进程回归通过；2GiB仍是逐进程限额，不声称整树内存/磁盘硬配额。审查明确无需cgroup，未改宿主设置。

旧3680局正式动物园矩阵的平衡仍未通过。第二次审查将runner门槛明确为p95、整局为300×折算TURN+5秒，因此既有v4效率数据达到；最大值仍报告。评测机参考已提供，后续批次使用该参考。详见 `inbox/2026-11-07-phase-a.md` 与STATUS；旧 `reports/phase-A-review-request.md` 是历史请求，不是A阶段完成报告。不要用平台联调局填报平衡、公平性或动物园验收。涉及隐藏 bot 或地图时，输出也必须放在 `private/`；CLI 会拒绝已知私有输入写往公开路径，本次没有创建隐藏内容。
