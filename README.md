# AgentEvalLab-HumanRaceWar

AgentEvalLab 顶层题族 CA（竞技场）的开发仓库。被测模型写一个 bot，在游戏"前哨"里对一条固定的对手阶梯打分。做完后迁移到 AgentEvalLab。

## 现在进行到哪一步

A阶段交付和审查入口见 [reports/phase-A.md](reports/phase-A.md)、[STATUS.md](STATUS.md)。standard-1采用已验证P7参数，动物园v15；最终40图3680局全部条件通过，两个哈希种子全套各198项通过。引擎、SDK、沙箱、bench、check、缓存、调度、结果库和tournament均已交付，见 [docs/BATCH.md](docs/BATCH.md)。按用户授权完成核对后推送，随后等待审查，不进入B；构建检查通过不等于评测负责人已验收。

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
