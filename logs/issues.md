# 问题与风险

更新：2026-11-07；阶段 A 进行中，开发环境已迁入 WSL。

| 编号 | 状态 | 内容 / 下一步 |
|---|---|---|
| ENV-001 | 已解决 | 用户授权后，通过已有 uv 用户级安装 Python 3.13.15；保留系统 Python 3.10.12，创建无第三方包的 `.venv`。86 项测试在 3.13.15 的两个哈希种子进程中通过。见 `data/python313-tests.json`。 |
| ENV-002 | 已解决 | 整个项目及本地 Git 历史迁入 WSL `~/projects/AgentEvalLab-HumanRaceWar`，不再依赖 D 盘挂载。42 个原有受跟踪文件和本地测试历史已核对，原 Windows 目录留作备份。见 `data/wsl-setup.json`。 |
| SANDBOX-001 | 首局与隔离测试通过，验收未完成 | bwrap 内 Python/C++ 示例、故障 bot、资源限额、绑核、环境清理和跨命名空间 CPU 时钟已有测试。仍缺短命子进程计量、进程树总资源/清理矩阵、单进程约束强制执行、速度标定及全局核锁。见 `docs/RUNTIME.md`。 |
| RUNTIME-001 | 已修复，失败复现保留 | 初版传输层将非法 UTF-8 字节换成 U+FFFD，重编码后膨胀字节预算，导致后续合法行被丢弃。1 项定点测试先失败，改为逐字节禁用 NUL 占位后通过；不改引擎规则。见 `logs/runtime-utf8-before-fix.log`、`runtime-utf8-after-fix.log`，最终两次 107 项测试全部通过。 |
| AGENT-001 | CLI 就绪，认证未验证 | 初次安装记录为 pi 1.4.0；最终复核实际为 1.5.0，CLI 与软件包版本一致，hrw-dev 版本/帮助检查通过。此次没有改动安装或读取认证文件，模型认证和推理未测试。用户自行通过 `/login`、`/model` 配置或确认账号。 |
| AUDIT-001 | 已解决，原始记录保留 | 最终复核脚本假设 pi 仍为 1.4.0，版本断言停止；实际 CLI/软件包均为 1.5.0。保留当前安装，改为核对实际版本后审计通过。两次引擎测试均为 86 项通过，不是引擎回归。记录在本地 `runs/development/final-handoff-attempt-1.json` 与 `final-handoff-check.json`。 |
| INSTALL-001 | 已恢复 | 下载时一次 curl TLS EOF、一次 npm ECONNRESET；保留既有代理和 TLS 校验，复用已有 uv，npm 按同一固定版本重试成功。未改 DNS、代理或安全设置。 |
| SPEC-001 | 待审查 | 初始站位/ID、SPAWN 占格、重复非法指令、伤害记录、失败动作警告和事件对称排序等处理见 `docs/IMPLEMENTATION_NOTES.md` I01–I10 与 STATUS。未修改既定规则参数或评分公式。 |
| MAP-001 | 未完成 | 当前只有结构校验器和人工测试 fixture，没有生成器、地图资源/连通性验收及正式地图集。 |
| EVAL-001 | 未开始 | 已有开发测试对局和完整回放，但没有动物园或正式地图数据，不能报告平衡、公平性、对局长度、结束方式比例。 |
| PERF-001 | 未开始 | 速度系数未知；测试运行时长不是 DESIGN 6.4 性能数据。 |
| USAGE-001 | 计量不完整 | token 和总 CPU 小时仍未知；测试宿主时间、回放回复 CPU 采样分别记录，编译与短命进程等不完整。不得将直接回收子进程的 rusage 当作整个沙箱用量。见 `data/runtime-tests.json`。 |

尚未达到 A 阶段终点，不生成“已完成”的阶段报告，不进入 B 阶段。
