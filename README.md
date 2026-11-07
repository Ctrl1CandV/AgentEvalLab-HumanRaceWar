# AgentEvalLab-HumanRaceWar

AgentEvalLab 顶层题族 CA（竞技场）的开发仓库。被测模型写一个 bot，在游戏"前哨"里对一条固定的对手阶梯打分。做完后迁移到 AgentEvalLab。

## 现在进行到哪一步

看 [STATUS.md](STATUS.md)。A阶段已打通沙箱内Python/C++示例对局与回放，修复首批运行器问题，提供bench/独立速度折算，并按D5步行检查重新生成44张地图。批量平台、动物园、平衡和效率验收尚未完成，不是已验收的竞技场。当前按BRIEF 3.7登记预算风险并暂停新增实现，等待用户确认；不是A阶段验收停点。

## WSL 开发与交接

主工作区已迁移到 WSL 的 `~/projects/AgentEvalLab-HumanRaceWar`，Windows 原目录仅保留备份。Python 3.13.15、GCC 11.4、bwrap 0.6.1 和 pi 1.5.0 已就绪（pi 版本按最终复核结果记录）。启动方式、登录步骤、验证记录与交接提示词见 [docs/WSL_HANDOFF.md](docs/WSL_HANDOFF.md)。

在 WSL 终端运行 `hrw-dev`，启动器会进入项目并激活 `.venv` 后启动 pi。首次自行完成 `/login`、`/model`；信任当前项目后可使用 `/resume-phase-a` 或 `/process-review`。

在主工作区运行开发检查（运行器测试中的 bot 与编译只在 bwrap 内执行）：

```sh
cd ~/projects/AgentEvalLab-HumanRaceWar
.venv/bin/python tools/check_environment.py
.venv/bin/python tools/run_tests.py
```

原 86 项引擎测试与迁移记录保留在 `data/python313-tests.json`、`data/wsl-setup.json` 和 `logs/python313-*.log`。新增运行器验证见 `data/runtime-tests.json`；用法与验证边界见 [docs/RUNTIME.md](docs/RUNTIME.md)。旧的 Python 3.10 开发记录与 Windows 转发工具 `tools/test_in_wsl.py` 保留为历史，不再作为主工作区入口。

打通开发用首局：

```sh
.venv/bin/python -m arena match --a sdk/python/example --b sdk/cpp/example --map tests/fixtures/smoke.map
.venv/bin/python -m arena replay verify <命令输出的回放路径>
```

此地图只是测试 fixture，不计入正式地图或平衡验收。也可改用 `maps/scrimmage/open-01.map`；公开地图集、生成器与检查命令见 [maps/README.md](maps/README.md)。最新两轮全套测试各140项通过，见 `data/review-bench-map-tests.json`；首批修复及旧地图证据仍在 `data/review-runtime-tests.json`、`data/mapgen-tests.json`。负载曲线、逐核差异和折算边界见 [docs/TIMING.md](docs/TIMING.md)、`data/timing.json`。

规则草稿见 [rules/rules.md](rules/rules.md)，测试覆盖与未验证范围见 [tests/COVERAGE.md](tests/COVERAGE.md)，暂定细节见 [docs/IMPLEMENTATION_NOTES.md](docs/IMPLEMENTATION_NOTES.md)。

## 文件

| 路径 | 内容 | 谁写 |
|---|---|---|
| [docs/DESIGN.md](docs/DESIGN.md) | 设计：游戏规则、框架、阶梯、计分、扩展、公开与保密 | 评测负责人 |
| [docs/BRIEF.md](docs/BRIEF.md) | 任务书，开头有给构建者的开场提示 | 评测负责人 |
| `rules/` | 给被测模型的规则全文；规则和参数的改动记录 | 构建者 |
| `STATUS.md` | 当前状态，构建期间每天更新 | 构建者 |
| `reports/` | 阶段报告 | 构建者 |
| `data/`、`logs/`、`replays/` | 审查用的数据、日志和少量回放 | 构建者 |
| `inbox/` | 审查意见 | 评测负责人写，用户放入 |
| `arena/`、`sdk/`、`bots/`、`maps/`、`ladder/`、`package/`、`tests/` | 代码和公开材料，A 阶段起创建 | 构建者 |
| `private/` | 隐藏内容，不入库 | 构建者 |
| `runs/` | 全部对局和回放，不入库 | — |

## 每次克隆后先运行

```
git config core.hooksPath .githooks
```

这一步启用提交前检查，会拦住隐藏内容、大文件和看起来像凭据的文件。

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
