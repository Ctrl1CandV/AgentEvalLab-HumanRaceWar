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
- 同一宿主UID的arena命令使用 `/tmp/hrw-cpu-locks-<uid>/` 内核文件锁，match/bench/batch互斥占用CPU，worker继承锁但bot不继承。它不能排除其他用户程序或宿主/虚拟机负载。
- 批量开始在相同CPU池、相同jobs下测bench，然后各槽使用相同系数；每局保存校准摘要与具体CPU。续跑保持CPU池/jobs和参考来源不变，重新测量并保留历史校准；运行中的槽数在开头/队尾和任务交接时会少于上限，不宣称所有时刻恰有2N个满负荷bot。
- `--max-tasks` 是有意留检查点的开发选项，未完成的清单仍标incomplete。已完成任务校验回放摘要后跳过；worker已写完整结果而controller来不及收取时，先重放验证再接纳，避免重复对局。
- 保留 `attempts.jsonl`（所有尝试）、`results.jsonl`（每个完成任务一次）、`executions.jsonl`（worker退出/中断）。文件追加加锁并fsync；被杀死的写入留下半行时，先另存原字节，再恢复有效前缀；中间坏行直接报错，不能跳过。框架重试预算在续跑之间累计，配置错误不重试。
- 没有完成的任务仍是incomplete，不从分母中悄悄删除。此处不是grade，不生成过程分或有效评分结果。

## 编译和原始指标

C++成功编译按源码、SDK、编译参数、编译器二进制及系统头文件/工具链元数据摘要缓存。每批先串行准备各bot，之后对局复制不可变产物，不逐局重编译。命中记录在 `cache.json`，复核产物SHA-256；损坏时拒绝使用，失败编译及日志保留，不缓存成成功。

新回放增加 `metricsVersion=2`：`warnings` 只数第一阶段的无效输入；`failedOrders` 数合法但执行失败的指令；`failedMoves` 数移动阶段失败（包括行动者死亡）。`buildContested` 是每方失败指令数，`buildContestedSites` 是争夺的塔基-回合次数。保留原始 `damageDealt`，增加每目标截断到攻击前生命的 `damageEffective`。全部从事件/前一状态复算，不改变游戏状态、哈希、结算或任何计分公式。没有该版本字段的历史回放按原指标解释，仍可验证。

## plain 的边界

`--sandbox plain` **不是宿主开发的快捷开关**，也不会从bwrap失败自动回退。它要求非root、只读挂载 `/hrw-outer-sandbox.json` 的操作者声明，以及仅有loopback的网络命名空间。声明内容：

```json
{"version":1,"network":"disabled","files":"isolated","purpose":"local-tools-only"}
```

这是外层沙箱集成契约，不是创建沙箱或认证外层安全性的机制。操作者必须先提供隔离的外层工作区，不能挂载用户HOME或凭据。资源限额和运行时seccomp仍设置，但不再隔离工作区内各bot的文件；临时文件和文件权限取决于外层。RLIMIT_NPROC在外层UID命名空间共享，可用线程余量也共享，并非每个本地bot都能同时获得16个线程。正式评分/阶梯校准只用bwrap。本地外层沙箱可用 `bench --sandbox plain --jobs N` 获取该环境的开发预算，校准数据不能跨backend使用；这不是正式评测机参考。

工作区总共8个CPU时，保留runner后最多3局，超过就明确拒绝，不能悄悄降并行度或挪用不同负载的校准值。`tools/test_outer_plain.py` 用只挂载必需文件的外层bwrap，实际验证Python/C++ check、plain本地基准、折算后的完整对局和回放；不会在本开发宿主裸用plain。
