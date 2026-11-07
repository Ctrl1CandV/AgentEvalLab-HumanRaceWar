# 状态

- 最近更新：2026-11-07（运行器、SDK、首局与回放开发检查）
- 当前阶段：A，进行中；已打通沙箱内首局闭环，尚未完成 A 阶段验收
- 主工作区：WSL Ubuntu-22.04 的 `~/projects/AgentEvalLab-HumanRaceWar`；Windows 原目录仅留备份
- ruleset：standard-1 的起点数值（DESIGN 附录 A），尚未调参
- 引擎版本：0.1.0-dev（未发布、未冻结）

## 本次 A 阶段进展

- 已完整阅读 inbox、DESIGN、BRIEF、STATUS 和首次接手文档。inbox 无新审查文件；开工时 `main` 干净、领先远端记录 4 个提交，钩子为 `.githooks`，Python 3.13.15，原 86 项测试全部通过。
- 实现 Python/C++ SDK 与弱示例、bwrap 启动及沙箱编译、非阻塞双 bot 运行器、CPU/墙钟时限与储备、故障归档/重试、`match` 和 gzip JSONL `replay verify/show/summary`。所有 bot 和编译均在 bwrap 内；无 plain 回退，未安装工具、未联网下载或读取凭据。
- CLI 首局：Python 示例对 C++ 示例，300 回合，C++ 方以卸货量 820 对 660 获胜，无故障、超时或警告。公开回放 `replays/runtime-smoke.hrw.jsonl.gz`（17,148 字节）可完整验证。使用 `tests/fixtures/smoke.map`，不是正式地图或平衡证据。
- 最终在 `PYTHONHASHSEED=0`、`1` 两个独立进程中各通过 **107 项测试**，0 失败、0 跳过；Pyright 检查 13 个 Python 文件，0 诊断。开发中发现非法 UTF-8 替换字符会膨胀字节预算、挤掉后续合法行，先复现 1 项失败，再修复并通过回归；前后日志均保留，未改引擎规则。
- 全部保留 **88 局有结果对局**（含故障判负）及 **34 次故意注入的框架失败尝试**；88 份完整回放均重新验证。数据、全部测试批次和失败复现见 `data/runtime-tests.json`、`logs/runtime-*.log`；本地完整材料在 `runs/development/runtime/` 与 `runs/development/cli-smoke/`。首轮测试报告沿用旧的“无 bot”scope 文案，原件保留，汇总中已明确纠正其实际包含 bwrap 集成测试。
- **验证边界：** 地图集、速度基准、完整进程树计量/资源/清理验收、全局独占核调度、动物园、平衡和效率均未完成。速度系数为未知；目前一次只运行一条 match，不用于正式评分。见 `docs/RUNTIME.md`、`tests/COVERAGE.md`。
- SDK 提交 `fbd9063`，运行器提交 `5278ceb`；另提交本次证据和状态。只在 WSL 本地提交，未推送。未改规则参数、计分方式或验收指标，也未创建隐藏内容；本次不生成阶段完成报告或 MANIFEST，不进入 B 阶段。

## 迁移与交接历史

- 用户已明确授权在 WSL 安装 Python、迁移整个项目、安装 pi 并配置基础开发环境。后续不在 Windows 备份目录继续开发。
- Python 3.13.15 已通过已有 uv 0.13.4 安装到用户目录，项目 `.venv` 使用该版本，仅标准库；Ubuntu 的 `/usr/bin/python3` 仍是 3.10.12，未替换。没有使用 sudo，也没有改代理、DNS 或安全设置。
- 项目经本地 Git bundle 迁入原生 ext4 工作区：基线 `d2f60c2`、4 个原有提交、42 个受跟踪文件和 1 个本地测试历史文件均已核对。保留本地提交身份、无凭据的 HTTPS 远端及跟踪关系，恢复 `.githooks`；没有迁移认证存储，没有推送。
- 初次迁移时用户级安装 pi 1.4.0，使用 `--ignore-scripts`。最终复核时已是 **1.5.0**，CLI 与已安装软件包一致；此次只复核，未重装、升级或降级，不推断版本变化来源。Node 22.23.3 / npm 10.9.9 沿用已有安装。`hrw-dev` 的版本和帮助命令通过；模型认证和实际推理未验证，由用户自行配置或确认，不读取凭据。
- Python 3.13.15 下，两个不同哈希种子的全套 **86 项测试均通过**，另归档 9 项确定性和 17 项协议测试。见 `data/python313-tests.json`、`logs/python313-*.log`；3.10 历史数据未删除。
- bwrap 内可信 Python 标准库、自身进程 CPU 时钟，以及可信 C++20 小程序的编译运行通过；未挂载 Agent HOME 或项目。这不是完整沙箱、跨命名空间计时、资源限额或故障 bot 验收。见 `data/wsl-setup.json`、`logs/wsl-setup.log`。
- 交接文档：`docs/WSL_HANDOFF.md`；自动开工说明：`AGENTS.md`；pi 提示词：`/resume-phase-a`、`/process-review`（信任当前项目后可用）。默认项目信任设置为 ask，未自动批准；未复制 Windows 扩展、技能、会话或认证文件。
- 最终复核：原 4 个提交、42 个文件、测试历史原始内容完整，`git fsck --full` 通过；两份迁移中转文件也补存至本地 `runs/migration/`。再次通过两次 86 项引擎测试及 Python/C++ 沙箱探针。第一次辅助审计因旧 pi 版本假设而停止，原始记录保留；核对实际版本后通过，未改引擎或测试源码。
- 后续 commit/push/pull 均在 WSL 主工作区，Windows 备份不再参与同步。远端读取已通过 `git ls-remote` 验证，远端 main 与本地 origin/main 一致；推送写权限未验证，本次没有 push/pull。复核记录在被忽略的 `runs/development/final-handoff-check.json`。

## 已有引擎工作（此前记录）

- 新增 `arena/core/game.py` 游戏接口与 `arena/games/outpost/` 引擎：状态、21 个默认规则参数、地图结构校验、指令解析、九步结算、终局、开局/观察消息、规范 SHA-256 状态哈希及 ASCII 棋盘。
- 新增 86 项单元测试；WSL Python 3.10.12 下，`PYTHONHASHSEED=0`、`1` 两次全套检查均通过，0 失败、0 跳过。包括 625 种四单位移动组合、200 组解析模糊输入、80 回合固定指令逐回合复现及全部事件类型的对称性检查。另分别归档 9 项确定性和 17 项协议测试。
- 迁移前 Pyright 检查 18 个 Python 文件，0 诊断；本次未改引擎或测试源码。WSL 只配置基础 pi，不能假定已有 Windows 的 LSP 扩展。
- 新增 `rules/rules.md` 草稿、`tests/COVERAGE.md` 和 `docs/IMPLEMENTATION_NOTES.md`；规则文档的全部参数与引擎有一致性测试。
- 新增 `tools/test_in_wsl.py`：仅传输公开引擎、规则和指定测试到临时目录，不要求挂载 D 盘，不运行 bot。数据见 `data/engine-tests.json`（含输入 sha256），日志见 `logs/engine-tests*.log`、`logs/determinism.log`、`logs/robustness.log`。
- **迁移时的验证边界：** 当时只有 Python 3.13.15 引擎检查，没有 bot 对局、完整回放、运行器、SDK、地图集、动物园矩阵或性能数据。旧 robustness 日志不代表真实管道验收；本次新增证据单独保存在 runtime 数据与日志中。
- 未改规则参数或评分方式，`rules/CHANGELOG.md` 仍为 2026-11-06 起点条目。没有创建隐藏文件、公开回放，也没有推送。
- 计分已定（用户 2026-11-06）：
  - 主分数取各级得分的平均；
  - 每局得分 = 0.75 × 胜负分 + 0.25 × 过程分；
  - 过程分目前是雏形（DESIGN 第 12 节），C 阶段由构建者用数据补齐。

## 卡住的地方

- 原 Python 版本和 D 盘访问阻塞已解决：现使用 WSL 原生目录、Python 3.13.15 和 `.venv`，不依赖 Windows 盘挂载。
- 无新的环境阻塞；本次没有检查认证或个人配置，也不需要用户向 Agent 提供凭据。
- 运行器已能打通开发局，但完整沙箱/计时与其余 A 阶段验收仍未完成。当前环境见 `data/environment-wsl-python313.json`；`data/environment.json` 保留初次检查历史。

## 需要评测负责人或用户决定的事

- 环境安装和迁移已获用户授权并完成，不再等待这两项批准。后续新增工具安装仍须另行询问。
- 以下按 BRIEF 3.3 先作对称、公开的实现，待评测负责人确认，详细依据和对应测试见 `docs/IMPLEMENTATION_NOTES.md`。

| 编号 | 当前做法 |
|---|---|
| I01 | 初始工兵在出兵范围内选最近空地，同距用双方互为旋转的局部坐标顺序；ID 为独立递增序号 × 玩家数 + 玩家号，不复用。 |
| I02 | SPAWN 必须在回合开始时无人占格；不能利用本回合移动、阵亡或卸货来绕过开始条件。 |
| I03 | 第一条语法完整且指向己方单位的指令占用槽，即使语义非法；语法错误不占槽。基地生产、射击各有一个槽。 |
| I04 | 双方 BUILD 冲突先于能量支付；死亡工兵先取消，再在存活工兵中按 ID 选执行者与扣款顺序。 |
| I05 | 生命最低记 0；伤害日志同时保留原始伤害和结算后生命，累计伤害暂含过量部分。尚未实现或冻结过程分口径。 |
| I06 | 合法但失败的移动/建造也发本方 INVALID，并计入诊断警告，不据此判负或扣分。 |
| I07 | 同步事件按固定键序列化；对称检查变换全部字段后重排比较，保留重复次数，不要求序列化顺序随玩家互换保持不变。 |
| I08 | 地图文件复用 MAP/ORE/END 记录；当前只校验结构与对称，生成后的连通性与资源验收尚未实现。 |
| I09 | 提交途中发生 bot 故障时，不结算该回合；双方统一判定，结果回合数记已结算回合数。编译/初始化故障记 0 回合，保留最后完整局面。 |
| I10 | 框架“重跑最多 3 次”暂按初次加最多 3 次重试，共最多 4 次；每次均归档，配置错误不重试。 |

## 下一步

1. 下次开工仍按必读顺序检查 inbox、Git 和测试；不要把 I01–I10 当成已批准解释。
2. 按 BRIEF 4.1 继续地图生成与完整检查、public/scrimmage 地图集；补齐速度基准、进程树计量/清理和沙箱验收、`check` 及外层沙箱的 plain 集成。
3. 实现调度器、共享结果库、tournament，再推进动物园、平衡和效率验收。全部 bot 与编译继续只在沙箱内执行。
4. A 阶段全部工作完成后才写正式 `reports/phase-A.md`、生成完整 MANIFEST 并进入阶段审查停点；现在不进入 B 阶段。

## 对 inbox/ 审查意见的回复

| 意见文件 | 条目 | 处理 |
|---|---|---|
| `inbox/README.md` | 工作流程说明 | 已读；当前无审查意见文件。 |

## 用量

| 阶段 | 模型 token | CPU 小时 | 机器配置 |
|---|---|---|---|
| A（进行中） | 当前工具未提供可靠累计计量，未知，待宿主补记 | 总 CPU 小时未知；累计已计量测试宿主 156.8581698 s，约 0.04357 h；本次全部对局回复 CPU 采样合计 16.5698367 s，非完整 bot/编译总量 | i5-14600KF，WSL 可见 20 逻辑 CPU、约 15.53 GiB 内存；速度系数未标定，见 `data/environment-wsl-python313.json` |

此前计量测试 CPU 共 3.3862897 s，本次基线和已归档测试批次新增 153.4718801 s。两次 UTF-8 定点检查、CLI 宿主、回放复核、编译和短命子进程未完整计量；`RUSAGE_CHILDREN` 只记录到直接回收进程，不能代替沙箱进程树总量。详见 `data/runtime-tests.json`；原始批次及失败复现均保留，历史索引在 `runs/development/test-history.jsonl`。这些数值不是效率验收结果，不包括模型用量。

## 最初环境开工记录（历史）

- 已按要求阅读 inbox、DESIGN 全文、BRIEF、STATUS。
- 已运行 `git config core.hooksPath .githooks`；沿用当前 `main` 分支，小步本地提交，不推送。
- 新增离线环境探测 `tools/check_environment.py`，不读取凭据、不下载、不执行 bot。
- 用户此次授权的开发工具安装已完成；项目源码/对局数据没有从网络下载。后续交接变更在 WSL 主工作区本地提交，Windows 保留 `d2f60c2` 备份。
