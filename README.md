# AgentEvalLab-HumanRaceWar

AgentEvalLab 顶层题族 CA（竞技场）的开发仓库。被测模型写一个 bot，在游戏"前哨"里对一条固定的对手阶梯打分。做完后迁移到 AgentEvalLab。

## 现在进行到哪一步

**A阶段已通过审查，用户已授权进入B。** 依据见 [inbox/2026-11-08-phase-a-accepted.md](inbox/2026-11-08-phase-a-accepted.md)。standard-1和动物园v15按交审配置冻结；A最终40图3680局条件通过，两个哈希种子全套各198项通过，完整报告见 [reports/phase-A.md](reports/phase-A.md)。

**dev05完成6800局并未采纳：首段dev得分37.5%低于45%门槛，保留原三轮止损结论。用户随后只批准一次E有限试验，不推送。** 原1440局未重跑，启动前资源失败保留；public搜索最优79.17%，但未通过对保留版的dev取舍，A/E/C-r02不变，不追加dev06或放宽门槛。见[完整dev05报告](reports/phase-B-mainlines-dev05.md)和[原计划](docs/PHASE_B_DEV05_PLAN.md)。D-c01首版另完成1280局，运行合规但强主线目标未达，只作同作者比较基线；随后作者r02完成160局public但未过筛选，未交新版本；后续有限修复r03功能失败、未计分，接收核验发现策略快照超限及汇总/判据问题，补正已核账收束；随后r04-plan-v2已收审，仍不可运行，下一项仅用户转交的120分钟工程准备包，零编译/bot/check/新局，保留r01，见[最新接收汇总](reports/phase-B-author-r04-plan-v2.md)、[补正接收](reports/phase-B-author-r03-reconciliation.md)、[r03报告](reports/phase-B-author-r03.md)、[首版报告](reports/phase-B-author-D-c01.md)和[r02报告](reports/phase-B-author-r02.md)。此前[第0步](reports/phase-B-mid-review-step0.md)已完成M1、历史分析、dev80和两公开材料目录：`~/projects/HRW-pilot/`、`~/projects/HRW-deepseek/`，由用户另开新会话，不用`hrw-dev`；分工与交付见[AUTHORS](docs/AUTHORS.md)。public调参、dev取舍/临时BT、calibration仅正式校准；grading/holdout仍未用。

**astra一次E单组件试验已获明确批准，总新计分上限4400；两稿P0均未通过，本轮已停止：首稿预算门失败，唯一修订通过压力但未过原功能门；总12编译/140启动/6282项，0新计分，不追加第三稿或P1/P2，见[P0记录](reports/phase-B-astra-compute-trial01-p0.md)。** 先P0，再四档public及条件式dev门，见[已批准计划](docs/PHASE_B_NEXT_TRIAL_PLAN.md)；不重新申请同一授权，不自动追加候选。用户让原GPT会话专管DeepSeek，新GPT接续E；[共享写入分工](docs/SESSION_COORDINATION.md)指定新E会话单独集成状态、清单与本地提交，交接改动已保全并统一收束，637169私有文件登记/全摘要通过；见[集成记录](data/phase-b/e-handoff-integration.json)。[B剩余路线](docs/PHASE_B_ROADMAP.md)列明依赖，原[止损复盘](reports/phase-B-astra-stop-review.md)和[静态准备](reports/phase-B-next-preparation.md)保留为历史。

**此前B历史：** 原2208局留出和获准的D22试验按旧标准失败，D22仍拒绝，不再调游戏参数。R1已固定配对/校准预算；N1确认全部失败项仅差1图，用户批准的新留出标准生效，v15前置复核通过。N2有反例，不改M、不运行v16；N3显示经济/骚扰按类型互相克制。新holdout24图已冻结并通过布局/独立检查，B末前不打对局。用户2026-11-09澄清L0是异质基础组，不强求内部等强；128局终局核查支持其解释，保留原版两bot，继续阶梯开发。三条私有主线已完成1728局首批开发及三轮各1872局比较，累计7344局、全部回放通过；dev02有改善，dev03/dev04候选未采纳，保留dev02继续增强，未做正式阶梯验收；holdout仍未使用。此解释只限L0，其他要求不变。详见 [主线开发记录](reports/phase-B-mainlines-dev04.md)、[L0决定](docs/PHASE_B_L0_DECISION.md) 和 [STATUS.md](STATUS.md)。当前没有完整阶梯，B未完成、C未启动。原启动快照见 [docs/PHASE_B_HANDOFF.md](docs/PHASE_B_HANDOFF.md)。

## 目录和上传范围

代码布局保持不变；阶段汇总集中在 `data/phase-a/`，历史说明移入 `docs/history/` 和 `reports/archive/`。目录入口见 [docs/REPOSITORY.md](docs/REPOSITORY.md)。

**对局只在开发机运行、存储。** 远端只上传代码、必要测试/配置、审查文档和汇总；不上传回放、逐局表、结果库或逐局索引。之前已上传的明细已从最新树撤下，但旧Git历史仍在，本轮不改写历史或强推。

## WSL 开发与交接

主工作区已迁移到 WSL 的 `~/projects/AgentEvalLab-HumanRaceWar`，Windows 原目录仅保留备份。Python 3.13.15、GCC 11.4、bwrap 0.6.1 和 pi 1.5.0 已就绪（pi 版本按最终复核结果记录）。启动方式、登录步骤、验证记录与交接提示词见 [docs/WSL_HANDOFF.md](docs/WSL_HANDOFF.md)。

在 WSL 终端运行 `hrw-dev`，启动器会进入项目并激活 `.venv` 后启动 pi。首次自行完成 `/login`、`/model`；信任当前项目后可使用 `/resume-phase-a` 或 `/process-review`。

在主工作区运行开发检查（运行器测试中的 bot 与编译只在 bwrap 内执行）：

```sh
cd ~/projects/AgentEvalLab-HumanRaceWar
.venv/bin/python tools/check_environment.py
.venv/bin/python tools/run_tests.py
```

原86项引擎测试、迁移及早期运行器验证汇总位于 `data/phase-a/history/`，完整旧日志在本机归档；用法与验证边界见 [docs/RUNTIME.md](docs/RUNTIME.md)。旧的 Python 3.10 开发记录与 Windows 转发工具 `tools/test_in_wsl.py` 保留为历史，不再作为主工作区入口。

打通开发用首局：

```sh
.venv/bin/python -m arena match --a sdk/python/example --b sdk/cpp/example --map tests/fixtures/smoke.map
.venv/bin/python -m arena replay verify <命令输出的回放路径>
```

此地图只是测试 fixture，不计入正式地图或平衡验收。也可改用 `maps/scrimmage/open-01.map`；公开地图集、生成器与检查命令见 [maps/README.md](maps/README.md)。交审前两轮全套测试各198项通过，见 `data/phase-a/acceptance/tests.json`；本轮目录/发布检查见 `data/phase-a/acceptance/publication.json`。首轮失败、旧平台及地图证据均保留。负载曲线、逐核差异和折算边界见 [docs/TIMING.md](docs/TIMING.md)、`data/timing.json`。

规则见 [rules/rules.md](rules/rules.md)，测试覆盖与未验证范围见 [tests/COVERAGE.md](tests/COVERAGE.md)，暂定细节见 [docs/IMPLEMENTATION_NOTES.md](docs/IMPLEMENTATION_NOTES.md)。

## 文件

| 路径 | 内容 | 谁写 |
|---|---|---|
| [docs/DESIGN.md](docs/DESIGN.md) | 设计：游戏规则、框架、阶梯、计分、扩展、公开与保密 | 评测负责人 |
| [docs/BRIEF.md](docs/BRIEF.md) | 任务书，开头有给构建者的开场提示 | 评测负责人 |
| `rules/` | 给被测模型的规则全文；规则和参数的改动记录 | 构建者 |
| `STATUS.md` | 当前状态，构建期间每天更新 | 构建者 |
| `reports/` | 阶段报告 | 构建者 |
| `data/`、`logs/` | 审查汇总与必要诊断，不含逐局数据 | 构建者 |
| `inbox/` | 审查意见 | 评测负责人写，用户放入 |
| `arena/`、`sdk/`、`bots/`、`maps/`、`ladder/`、`package/`、`tests/` | 代码和公开材料，A 阶段起创建 | 构建者 |
| `private/` | 隐藏内容，不入库 | 构建者 |
| `runs/` | 全部对局和回放，不入库 | — |

## 每次克隆后先运行

```
git config core.hooksPath .githooks
```

这一步启用提交前检查，会拦住隐藏内容、大文件、疑似凭据及已知逐局数据格式；需要项目Python3.13解释器。

## 审查流程

1. 构建者按阶段推进，每天更新 STATUS.md；阶段结束时写报告，然后停下。
2. 用户提醒评测负责人拉取。评测负责人对照 DESIGN 和 BRIEF 审查，意见分"必须改""建议改""问题"三类。
3. 用户把意见文件放进 `inbox/`。构建者下次开工先读，处理后在 STATUS.md 里逐条回复。
4. 涉及计分规则和评分原则的改动，评测负责人只提建议，由用户决定。

## 公开与保密

这个仓库是公开的。以下内容只放在 `private/`，不入库：
- 隐藏的阶梯 bot；
- 评分和校准用的地图；
- 和隐藏 bot 有关的对局。

详见 DESIGN 第 16 节。
