# 状态

- 最近更新：2026-11-07（WSL 开发环境迁移与交接）
- 当前阶段：A，进行中；环境已就绪，由 WSL 中的执行 Agent 接手，尚未完成 A 阶段验收
- 主工作区：WSL Ubuntu-22.04 的 `~/projects/AgentEvalLab-HumanRaceWar`；Windows 原目录仅留备份
- ruleset：standard-1 的起点数值（DESIGN 附录 A），尚未调参
- 引擎版本：0.1.0-dev（未发布、未冻结）

## 本次迁移与交接

- 用户已明确授权在 WSL 安装 Python、迁移整个项目、安装 pi 并配置基础开发环境。后续不在 Windows 备份目录继续开发。
- Python 3.13.15 已通过已有 uv 0.13.4 安装到用户目录，项目 `.venv` 使用该版本，仅标准库；Ubuntu 的 `/usr/bin/python3` 仍是 3.10.12，未替换。没有使用 sudo，也没有改代理、DNS 或安全设置。
- 项目经本地 Git bundle 迁入原生 ext4 工作区：基线 `d2f60c2`、4 个原有提交、42 个受跟踪文件和 1 个本地测试历史文件均已核对。保留本地提交身份、无凭据的 HTTPS 远端及跟踪关系，恢复 `.githooks`；没有迁移认证存储，没有推送。
- 初次迁移时用户级安装 pi 1.4.0，使用 `--ignore-scripts`。最终复核时已是 **1.5.0**，CLI 与已安装软件包一致；此次只复核，未重装、升级或降级，不推断版本变化来源。Node 22.23.3 / npm 10.9.9 沿用已有安装。`hrw-dev` 的版本和帮助命令通过；模型认证和实际推理未验证，由用户自行配置或确认，不读取凭据。
- Python 3.13.15 下，两个不同哈希种子的全套 **86 项测试均通过**，另归档 9 项确定性和 17 项协议测试。见 `data/python313-tests.json`、`logs/python313-*.log`；3.10 历史数据未删除。
- bwrap 内可信 Python 标准库、自身进程 CPU 时钟，以及可信 C++20 小程序的编译运行通过；未挂载 Agent HOME 或项目。这不是完整沙箱、跨命名空间计时、资源限额或故障 bot 验收。见 `data/wsl-setup.json`、`logs/wsl-setup.log`。
- 交接文档：`docs/WSL_HANDOFF.md`；自动开工说明：`AGENTS.md`；pi 提示词：`/resume-phase-a`、`/process-review`（信任当前项目后可用）。默认项目信任设置为 ask，未自动批准；未复制 Windows 扩展、技能、会话或认证文件。
- 最终复核：原 4 个提交、42 个文件、测试历史原始内容完整，`git fsck --full` 通过；两份迁移中转文件也补存至本地 `runs/migration/`。再次通过两次 86 项引擎测试及 Python/C++ 沙箱探针。第一次辅助审计因旧 pi 版本假设而停止，原始记录保留；核对实际版本后通过，未改引擎或测试源码。
- 后续 commit/push/pull 均在 WSL 主工作区，Windows 备份不再参与同步。远端读取已通过 `git ls-remote` 验证，远端 main 与本地 origin/main 一致；推送写权限未验证，本次没有 push/pull。复核记录在被忽略的 `runs/development/final-handoff-check.json`。

## 已有引擎工作

- 新增 `arena/core/game.py` 游戏接口与 `arena/games/outpost/` 引擎：状态、21 个默认规则参数、地图结构校验、指令解析、九步结算、终局、开局/观察消息、规范 SHA-256 状态哈希及 ASCII 棋盘。
- 新增 86 项单元测试；WSL Python 3.10.12 下，`PYTHONHASHSEED=0`、`1` 两次全套检查均通过，0 失败、0 跳过。包括 625 种四单位移动组合、200 组解析模糊输入、80 回合固定指令逐回合复现及全部事件类型的对称性检查。另分别归档 9 项确定性和 17 项协议测试。
- 迁移前 Pyright 检查 18 个 Python 文件，0 诊断；本次未改引擎或测试源码。WSL 只配置基础 pi，不能假定已有 Windows 的 LSP 扩展。
- 新增 `rules/rules.md` 草稿、`tests/COVERAGE.md` 和 `docs/IMPLEMENTATION_NOTES.md`；规则文档的全部参数与引擎有一致性测试。
- 新增 `tools/test_in_wsl.py`：仅传输公开引擎、规则和指定测试到临时目录，不要求挂载 D 盘，不运行 bot。数据见 `data/engine-tests.json`（含输入 sha256），日志见 `logs/engine-tests*.log`、`logs/determinism.log`、`logs/robustness.log`。
- **验证边界：** 已补齐 Python 3.13.15 的引擎检查，但仍没有 bot 对局、完整回放、运行器、SDK、地图集、动物园矩阵或性能数据。新旧 robustness 日志都不代表崩溃/死循环/真实管道测试已经通过。
- 未改规则参数或评分方式，`rules/CHANGELOG.md` 仍为 2026-11-06 起点条目。没有创建隐藏文件、公开回放，也没有推送。
- 计分已定（用户 2026-11-06）：
  - 主分数取各级得分的平均；
  - 每局得分 = 0.75 × 胜负分 + 0.25 × 过程分；
  - 过程分目前是雏形（DESIGN 第 12 节），C 阶段由构建者用数据补齐。

## 卡住的地方

- 原 Python 版本和 D 盘访问阻塞已解决：现使用 WSL 原生目录、Python 3.13.15 和 `.venv`，不依赖 Windows 盘挂载。
- 新 pi 的模型认证和实际推理尚未验证，需要用户手动登录或确认自己的配置；不得把认证文件交给执行 Agent。
- 完整沙箱、计时、运行器等仍是 A 阶段待实现工作，不是环境安装已经替代的验收。当前环境见 `data/environment-wsl-python313.json`；`data/environment.json` 保留初次检查历史。

## 需要评测负责人或用户决定的事

- 环境安装和迁移已获用户授权并完成，不再等待这两项批准。后续新增工具安装仍须另行询问。
- 用户按 `docs/WSL_HANDOFF.md` 在新 pi 中登录并选择执行模型；无需向 Agent 展示任何密钥或令牌。
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

## 下一步

1. 用户登录 pi 后，用 `/resume-phase-a` 交接；执行 Agent 按必读顺序核实状态，并在 WSL 主目录重跑 `.venv/bin/python tools/run_tests.py`。
2. 实现运行器、SDK/示例、match 与回放，再打通第一局；所有 bot 仍只在沙箱中运行。
3. 按任务书继续地图、bwrap 计时与隔离、调度器、动物园、平衡和效率验收。
4. A 阶段全部工作完成后才写正式 `reports/phase-A.md`、生成完整 MANIFEST 并进入阶段审查停点；现在不进入 B 阶段。

## 对 inbox/ 审查意见的回复

| 意见文件 | 条目 | 处理 |
|---|---|---|
| `inbox/README.md` | 工作流程说明 | 已读；当前无审查意见文件。 |

## 用量

| 阶段 | 模型 token | CPU 小时 | 机器配置 |
|---|---|---|---|
| A（进行中） | 当前工具未提供可靠累计计量，未知，待宿主补记 | 对局 0 h；已计量测试 3.3862897 s，约 0.0009406 h；安装、编译探针、开发工具等 CPU 未完整计量，不冒充总量 | i5-14600KF，WSL 可见 20 逻辑 CPU、约 15.53 GiB 内存；速度系数未标定，见 `data/environment-wsl-python313.json` |

测试 CPU 由原有 2.3393043 s、首次 Python 3.13.15 检查 0.6166141 s、最终两次复核 0.2164075 s 与 0.2139638 s 组成。首次 3.13 检查见 `data/python313-tests.json`，本次复核见本地 `runs/development/final-handoff-*`；全部已归档批次历史保留在被忽略的 `runs/development/test-history.jsonl`。这些时间不是性能验收结果，也不包括本对话的模型用量；没有通过新安装的 pi 发起模型调用。

## 本次开工记录

- 已按要求阅读 inbox、DESIGN 全文、BRIEF、STATUS。
- 已运行 `git config core.hooksPath .githooks`；沿用当前 `main` 分支，小步本地提交，不推送。
- 新增离线环境探测 `tools/check_environment.py`，不读取凭据、不下载、不执行 bot。
- 用户此次授权的开发工具安装已完成；项目源码/对局数据没有从网络下载。后续交接变更在 WSL 主工作区本地提交，Windows 保留 `d2f60c2` 备份。
