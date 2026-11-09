# 批量平台与本地检查（A 阶段）

## 使用

```sh
.venv/bin/python -m arena check sdk/python/example
.venv/bin/python -m arena tournament --bot sdk/python/example \
  --opponents sdk/cpp/example --maps maps/scrimmage --jobs 2 --out runs/example-batch
# 中断后：参数与源码必须仍与原清单一致
.venv/bin/python -m arena tournament --bot sdk/python/example \
  --opponents sdk/cpp/example --maps maps/scrimmage --jobs 2 --out runs/example-batch --resume
# 动物园循环赛；额外包括不同SEED的M-balanced自对弈
.venv/bin/python -m arena tournament --bots bots/public/* --include-self M-balanced \
  --maps maps/public --jobs 6 --out runs/zoo-v1
```

`check` 复用提交校验/编译逻辑，默认检查READY和5回合，面对引擎内的空指令环境，不把它当有胜负的完整对局。结果含明确的格式/编译错误、协议警告和超时。无入口、两种入口、链接和大小超限都按相同提交规则处理。

## 清单、CPU与续跑

- 每对bot逐图交换位置，同时交换各自的种子。相同名称的目录用索引后缀区分，不额外限制提交格式。自对弈要求两个不同种子。
- `manifest.json` 保存输入摘要、源码/SDK/框架标识、规则参数、并行度及全部确定性taskId；每个任务的源代码、地图和执行框架都冻结，运行期间不读变化中的源码。
- 标准库进程调度，不用线程调用带 `preexec_fn` 的启动器。每槽两个独占bot CPU，运行器使用池外CPU。默认6局需要12个bot CPU及至少1个runner CPU；有余量时为不同runner分配不同CPU。
- 同一宿主UID的arena命令使用 `${TMPDIR:-/tmp}/hrw-cpu-locks-<uid>/` 内核文件锁（S8；部署时所有命令共用同一TMPDIR），match/bench/batch互斥占用CPU，worker继承锁但bot不继承。它不能排除其他用户程序或宿主/虚拟机负载。
- 普通开发批次默认仍测速，续跑在同CPU池/jobs下重测并保留历史。**配对试验与阶梯校准不能使用这个默认策略**：新校准的首批用`--freeze-timing`，只测一次；同批续跑继续带该选项，后续批次/候选用`--fixed-timing <首批/timing-lock.json>`。锁定原测速字节、来源摘要、系数、参考、jobs/CPU池，以及实际初始化/每回合/储备限额、墙钟余量和CPU硬上限，不重测、不二次折算。输入预算、backend、回合上限或记录不匹配时拒绝运行。
- 已有基线用`.venv/bin/python -B -m tools.freeze_batch_timing --batch <原批次> --out <本机目录/timing-lock.json>`提取。工具检查全部已完成任务的回放摘要和实际限额，拒绝不完整或混合测速时期的基线；不会执行bot或测速。隐藏来源仍只写private，公开来源的原始锁也只留runs/private。
- 2026-11-09起固定锁为schemaVersion=2，校验CPU型号、架构、机器总逻辑核数和可见物理内存向上取整GiB档位；不把租用CPU池长度当总核数。内核版本保留作诊断，不作为硬件身份。硬件指纹不匹配在规划/写批次前拒绝，提示在新机器测速并重新冻结；不收集hostname、machine-id或凭据，也不声称该硬件组合是密码学唯一主机身份。
- 旧v1锁缺机器绑定，不能静默继续运行。若有已归档、绑定原锁摘要的机器总核数证据，`arena.core.timing.bind_legacy_calibration`可另存v2封装：原锁和原benchmark字节、预算、系数全部保留，嵌入证据及摘要，并核对当前硬件。没有证据就拒绝，不能从当前机器或租用池猜原核数。本次dev01旧锁由`tools/review_mainlines.py`结合`data/phase-b/mainlines-dev01.json`补绑定，新封装在`private/phase-b/mid-review-step0/timing-lock-machine-bound.json`；旧锁不改，不测速。以后的同机开发用此封装，历史四轮原件仍可读，不重跑。
- 固定记录不修改正式评分D4：正式评分每次开始仍按实际并发测速，不跨评分沿用旧记录。固定限额用于配对/校准的可比性，不意味着免受宿主负载或硬件变化影响；跨机器不能拿旧CPU编号/记录替代评测机校准。
- 运行中的槽数在开头/队尾和任务交接时会少于上限，不宣称所有时刻恰有2N个满负荷bot。
- `--max-tasks` 是有意留检查点的开发选项，未完成的清单仍标incomplete。已完成任务校验回放摘要后跳过；worker已写完整结果而controller来不及收取时，先重放验证再接纳，避免重复对局。
- 保留 `attempts.jsonl`（所有尝试）、`results.jsonl`（每个完成任务一次）、`executions.jsonl`（worker退出/中断）。文件追加加锁并fsync；被杀死的写入留下半行时，先另存原字节，再恢复有效前缀；中间坏行直接报错，不能跳过。框架重试预算在续跑之间累计，配置错误不重试。
- 没有完成的任务仍是incomplete，不从分母中悄悄删除。此处不是grade，不生成过程分或有效评分结果。
- worker启动失败也写尝试和执行记录；强杀留下的半截attempt，在worker确认退出/重新取得CPU锁后补记为infra_error（recovered），不冒充完整对局。冻结执行框架和地图在执行前再次核对。
- 正常worker的完整结果先核对回放摘要，不在controller调度循环中串行重跑引擎；`replayVerifiedOnIngest`说明是否当时做了规则重放。崩溃恢复仍先验证再接纳。批量complete仅表示任务完成，不表示平衡或全回放审计完成；动物园报告另行逐份验证。

## 指定配对（B开发/校准）

Python接口`run_tournament(..., pairings=[(0, 1), (0, 2), (2, 2)])`可只执行预先指定的无序配对，索引对应`sources`顺序。每个配对仍覆盖全部输入地图和两座；自对弈仍要求不同种子。拒绝空列表、重复/反向重复、非整数或越界索引，也不能同时传`focus`/`include_self`。排序后的精确配对写入原manifest的`request.pairs`，续跑不能更换；无此参数时原全循环赛行为不变。

用于只运行新主线与参照/其他新主线的对局，避免把冻结动物园之间的既有基线重新打一遍；后续也可表达同级、相邻及隔级校准。它不是评分日程、分数公式或新CLI命令，不改变每对的换边及种子约定。实际配对计划仍须事前保存，固定预算与private边界不变。

## 编译和原始指标

所有实际C++编译先取得同一锁目录中的 `compile` 锁，跨match/check/bench/tournament进程一次只运行一个编译器；排队时间不计入60秒执行墙钟，异常退出由内核释放锁。该锁不依赖具体缓存目录；编译器和bot不继承锁FD。

C++成功编译按backend、源码、SDK、编译参数、编译器二进制及系统头文件/工具链元数据摘要缓存。每批先串行准备各bot，之后对局复制不可变产物，不逐局重编译。命中记录在 `cache.json`，复核产物SHA-256；损坏时拒绝使用，失败编译及日志保留，不缓存成成功。

新回放增加 `metricsVersion=2`：`warnings` 只数第一阶段的无效输入；`failedOrders` 数合法但执行失败的指令；`failedMoves` 数移动阶段失败（包括行动者死亡）。`buildContested` 是每方失败指令数，`buildContestedSites` 是争夺的塔基-回合次数。保留原始 `damageDealt`，增加每目标截断到攻击前生命的 `damageEffective`。全部从事件/前一状态复算，不改变游戏状态、哈希、结算或任何计分公式。没有该版本字段的历史回放按原指标解释，仍可验证。

## plain 的边界

`--sandbox plain` **不是宿主开发的快捷开关**，也不会从bwrap失败自动回退。它要求非root、只读挂载 `/hrw-outer-sandbox.json` 的操作者声明，以及仅有loopback的网络命名空间。声明内容：

```json
{"version":1,"network":"disabled","files":"isolated","purpose":"local-tools-only"}
```

这是外层沙箱集成契约，不是创建沙箱或认证外层安全性的机制。操作者必须先提供隔离的外层工作区，不能挂载用户HOME或凭据。资源限额和运行时seccomp仍设置，但不再隔离工作区内各bot的文件；临时文件和文件权限取决于外层。RLIMIT_NPROC在外层UID命名空间共享，可用线程余量也共享，并非每个本地bot都能同时获得16个线程。正式评分/阶梯校准只用bwrap。本地外层沙箱可用 `bench --sandbox plain --jobs N` 获取该环境的开发预算，校准数据不能跨backend使用；这不是正式评测机参考。

工作区总共8个CPU时，保留runner后最多3局，超过就明确拒绝，不能悄悄降并行度或挪用不同负载的校准值。`tools/test_outer_plain.py` 用只挂载必需文件的外层bwrap，实际验证Python/C++ check、plain本地基准、折算后的完整对局/回放及双槽批量。测试外层先在宿主租用CPU池，内层只分配该池；不会在本开发宿主裸用plain。
