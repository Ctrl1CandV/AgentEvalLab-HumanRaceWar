# data

| 文件 | 内容 | 阶段 |
|---|---|---|
| `environment.json` | 初次开工的环境探测历史（Python 3.10）；不是性能验收 | A（历史开发检查） |
| `engine-tests.json` | Python 3.10 引擎测试历史、输入 sha256、测试进程 CPU 时间 | A（历史开发检查） |
| `environment-wsl-python313.json` | 迁移后 Python 3.13.15 / WSL 环境和机器配置 | A（环境检查） |
| `python313-tests.json` | 主工作区 Python 3.13.15 测试结果及输入 sha256；不是整体验收 | A（引擎检查） |
| `wsl-setup.json` | 用户级工具安装、工作区迁移、可信沙箱探针及未验证范围 | A（开发交接） |
| `runtime-tests.json` | 首局闭环、最终两次 107 项测试、UTF-8 失败复现与修复、全部 122 次对局尝试、88 份回放验证、源码摘要和不完整用量 | A（集成开发检查，不是平衡/效率验收） |
| `zoo-matrix.csv` | 动物园各 bot 之间的局数、胜、平、负，分地图类型 | A |
| `balance.json` | 先后手公平、平局率、对局长度分布、结束方式 | A |
| `timing.json` | 引擎、运行器、整局和整套评分的用时，注明机器配置和速度系数 | A、C |
| `ladder-matrix.csv` | 阶梯各 bot 之间的成对对局数、胜、平、负（只写代号） | B |
| `ladder-ratings.csv` | 各级各 bot 的 Elo、区间、风格、sha256 | B |
| `standard-budget.json` | 标准预算自测：投入的 token 和时间、主分数、每一级的成绩 | B |

隐藏的 bot 只写代号和 sha256。
