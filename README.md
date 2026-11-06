# AgentEvalLab-HumanRaceWar

AgentEvalLab 顶层题族 CA（竞技场）的开发仓库。被测模型写一个 bot，在游戏"前哨"里对一条固定的对手阶梯打分。做完后迁移到 AgentEvalLab。

## 现在进行到哪一步

看 [STATUS.md](STATUS.md)。当前为 A 阶段引擎初版：有规则结算、消息解析和单元测试，尚无可运行的 bot 对局工具，不是已验收的竞技场。

## 开发检查

在 Linux/WSL 的仓库根目录运行：

```sh
python3.13 tools/check_environment.py
python3.13 tools/run_tests.py
```

如果 Windows 上的仓库没有挂载进 WSL，可用宿主 Python 运行：

```sh
python tools/test_in_wsl.py --python python3.13
```

此工具只复制本项目公开的引擎、规则和指定测试到 WSL 临时目录，完成后清理临时副本，不安装工具、不联网、不执行 bot。结果写入 `data/engine-tests.json`、`logs/`；测试输入文件附有 SHA-256。默认 `--python python3` 可用于开发检查，但非 3.13 的结果不算正式环境验收。

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
