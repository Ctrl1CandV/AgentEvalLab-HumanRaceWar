# 问题与风险

更新：2026-11-07；阶段 A 进行中，开发环境已迁入 WSL。

| 编号 | 状态 | 内容 / 下一步 |
|---|---|---|
| ENV-001 | 已解决 | 用户授权后，通过已有 uv 用户级安装 Python 3.13.15；保留系统 Python 3.10.12，创建无第三方包的 `.venv`。86 项测试在 3.13.15 的两个哈希种子进程中通过。见 `data/python313-tests.json`。 |
| ENV-002 | 已解决 | 整个项目及本地 Git 历史迁入 WSL `~/projects/AgentEvalLab-HumanRaceWar`，不再依赖 D 盘挂载。42 个原有受跟踪文件和本地测试历史已核对，原 Windows 目录留作备份。见 `data/wsl-setup.json`。 |
| SANDBOX-001 | 首批审查修正通过，验收未完成 | M2/M3/M5 已补单进程seccomp、线程任务上限、禁止改绑核、END累计CPU、proc缺失报错、只读/tmp及编译2GiB；真实Python/C++线程探针通过。全局核锁/批量折算及controller中断清理已有开发回归，仍缺完整压力/清理矩阵与编译树总资源验收。见 `data/review-runtime-tests.json`、`docs/RUNTIME.md`。 |
| RUNTIME-002 | 已修复，失败复现保留 | M1退出125不再算infra_error；M6格式错误不再算configuration_error，改判提交方编译失败并保留原因。旧的错误重试和误分类结果均保留；两轮132项通过。 |
| RUNTIME-001 | 已修复，失败复现保留 | 初版传输层将非法 UTF-8 字节换成 U+FFFD，重编码后膨胀字节预算，导致后续合法行被丢弃。1 项定点测试先失败，改为逐字节禁用 NUL 占位后通过；不改引擎规则。见 `logs/runtime-utf8-before-fix.log`、`runtime-utf8-after-fix.log`，最终两次 107 项测试全部通过。 |
| AGENT-001 | CLI 就绪，认证未验证 | 初次安装记录为 pi 1.4.0；最终复核实际为 1.5.0，CLI 与软件包版本一致，hrw-dev 版本/帮助检查通过。此次没有改动安装或读取认证文件，模型认证和推理未测试。用户自行通过 `/login`、`/model` 配置或确认账号。 |
| AUDIT-001 | 已解决，原始记录保留 | 最终复核脚本假设 pi 仍为 1.4.0，版本断言停止；实际 CLI/软件包均为 1.5.0。保留当前安装，改为核对实际版本后审计通过。两次引擎测试均为 86 项通过，不是引擎回归。记录在本地 `runs/development/final-handoff-attempt-1.json` 与 `final-handoff-check.json`。 |
| INSTALL-001 | 已恢复 | 下载时一次 curl TLS EOF、一次 npm ECONNRESET；保留既有代理和 TLS 校验，复用已有 uv，npm 按同一固定版本重试成功。未改 DNS、代理或安全设置。 |
| SPEC-001 | 已裁定，附加实现进行中 | 2026-11-07审查已同意I01–I11；D1–D10已纳入DESIGN/BRIEF，原游戏参数/结算不变。S1/S2原始统计及D5已实现，D6正式矩阵已完成但平衡未通过，过程分公式仍不冻结，评分局数不改。 |
| MAP-001 | D5已修，未作平衡验收 | v2加入家门矿步行≤12、近矿塔基同时满足曼哈顿3–5及步行≤6；44图重生成通过，17文件变化、墙体/基地不变。独立BFS旧图40条违规记录及旧资产保留；全图种子拒绝0/44，未放宽阈值。见review-bench-map证据。 |
| SANDBOX-ROOT | 补查已修，失败保留 | 只读/tmp仍允许在合成根tmpfs写文件；已复现并只读/，同时拒绝SysV IPC/POSIX消息队列分配。运行策略v3；真实Python/C++回归通过，仍非完整安全验收。 |
| SANDBOX-CLEANUP | 四个缺口已复现并修复 | preexec父死亡窗口、清除PDEATHSIG、worker启动无归档、SIGKILL半截attempt；策略v4及5项清理回归、两轮157项全套通过。见cleanup-tests；编译树资源等仍待补。 |
| BUDGET-A | 风险已告知，获准继续 | 最新快照77.322M含74.981M缓存，已超过含缓存45M提醒线；用户已授权继续至可提交审查，网络恢复后再次确认。继续分列用量，完整总量未知。 |
| EVAL-001 | 正式D6完成，平衡未通过 | v5正式3680局全部回放验证；M对骚扰37.5%、maze对速攻50%，骚扰无单一克制者；1/2/7未通过。自对弈27.5%拆基地达标。所有旧版分开保留，见balance.json及phase-A-review-request。 |
| PERF-001 | 已实测，未全部达标 | 2ms轮询的49次CPU扫描先失败，50ms事件驱动/剩余预算约束后为5次；引擎p95最高0.785ms。六局CPU开销均值1.787ms但最大7.583ms，整局36.052–36.088秒。三版数据保留；D4折算与35秒口径、正式参考待审查，不改门槛。 |
| USAGE-001 | 计量不完整 | 最新部分pi用量77,321,999 token，其中缓存74,980,992；完整阶段token/CPU总量仍未知。用户继续A的预算授权有效。见usage-pi-local及phase-a-validation；不把直接回收子进程rusage当完整总量。 |
| SANDBOX-COMPILE | 总资源契约/集成待审查 | 有限两子进程编译探针清理通过，但NPROC继承63593、2GiB AS逐进程，无整树内存/CPU/磁盘硬限额。cgroup不可写，未改系统安全设置；不能把轮询监督称为硬总量保障。见phase-a-security。 |
| ZOO-STARVATION | 三个最小反例已修 | 远敌挤占塔钱、占用目标邻格使远兵停下、反复争格不让路，分别失败后窄修；未重写寻路。v3/v4/v5各368局均保留，包括恶化的战绩。 |

尚未达到A阶段完成条件。`reports/phase-A-review-request.md`为新增资源/效率口径审查请求，不是完成报告；等待审查，不冻结、不进入B、不自动推送。
