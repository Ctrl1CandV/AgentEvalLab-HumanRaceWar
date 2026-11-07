# A 阶段首局闭环

更新：2026-11-07。运行器、SDK 和回放已能打通开发用对局，尚未完成 A 阶段验收。游戏参数、规则、协议和计分公式未改。

## 运行一局

在当前 WSL 工作区使用 Python 3.13；不直接执行 bot 或 g++：

```sh
.venv/bin/python -m arena match \
  --a sdk/python/example --b sdk/cpp/example \
  --map tests/fixtures/smoke.map
```

`smoke.map` 只是 24×24 的对称测试地图，不满足 DESIGN 7.2 的完整资源布局要求，不是 public 地图集。现在也可使用 `maps/public/*.map` 和 `maps/scrimmage/*.map`；44 张默认布局检查通过的地图及 `mapgen/mapcheck` 用法见 `maps/README.md`，平衡尚未验收。两种示例会采矿、返家卸货、偶尔出兵；未校准强度。

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

所有实际 bot 和 C++ 编译都使用 bwrap；没有 plain 回退。沙箱不联网，不挂载 Agent HOME、宿主 `/etc`、整个项目或另一个 bot，只挂载系统运行库、Python 安装目录、本方源码和公开 SDK。源码与运行时构建产物只读；编译时仅本方构建目录可写。启动环境使用固定白名单，不继承代理、认证或个人配置。

每个 bot 在本局内绑定不同 CPU，设置 512 MiB 地址空间、16 MiB 文件、64 个文件描述符、整局 CPU 硬限额及禁用 core dump。C++ 编译为 GCC 11 的 `-O2 -std=gnu++20`，另加 SDK include 目录，墙钟上限 60 秒。隔离、环境清理、只读源码和这些限额已有真实沙箱测试，但这不是完整安全验收。

当前采用跨命名空间 Linux 进程 CPU 时钟，单个进程包括全部线程；采样可见后代，时钟不可用时标记回退 `/proc/<pid>/stat`。短命子进程可能逃过轮询，单进程约束尚未强制执行，也没有进程树总内存限制。不要把此开发运行器当作已经验收的恶意提交执行服务。

速度基准尚未实现，回放 `speedFactor` 为 `null`，使用未折算的开发默认时限。`BANK` 内部按纳秒扣除超额，不回充，消息显示向下取整的毫秒数。墙钟兜底包括本回合预算、剩余储备和 500 ms；初始化为初始化预算加 500 ms。两方均发送观察后并发收取回复，不把两方思考串行相加。

编译失败、退出、超时判为 bot 故障；同一次收取中的双方故障判平。框架异常不产生胜负，保留所有尝试，默认在初次尝试后重试最多 3 次。配置错误单独记录，不盲目重试。故障回合不结算、重试次数的解释见 STATUS 的 I09–I10，仍待审查确认。

## 尚未交付

- plain 的外层沙箱集成、`check`；
- 完整的进程树计量/清理验收、速度基准和全局独占核调度；
- 可续跑的批任务调度器、共享结果库及 `tournament`；
- 动物园、地图/策略平衡矩阵、全部效率测量与 A 阶段报告。

目前一次只启动一条 `match` 命令；不同调用之间尚无核分配锁。不要用这些测试局填报地图、公平性或动物园验收。涉及隐藏 bot 或地图时，输出也必须放在 `private/`；CLI 会拒绝已知私有输入写往公开路径，本次没有创建隐藏内容。
