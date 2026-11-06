# data

| 文件 | 内容 | 阶段 |
|---|---|---|
| `environment.json` | 离线环境探测、机器配置；不是性能验收 | A（开发检查） |
| `engine-tests.json` | 引擎测试结果、输入 sha256、测得的测试进程 CPU 时间；不是整体验收 | A（开发检查） |
| `zoo-matrix.csv` | 动物园各 bot 之间的局数、胜、平、负，分地图类型 | A |
| `balance.json` | 先后手公平、平局率、对局长度分布、结束方式 | A |
| `timing.json` | 引擎、运行器、整局和整套评分的用时，注明机器配置和速度系数 | A、C |
| `ladder-matrix.csv` | 阶梯各 bot 之间的成对对局数、胜、平、负（只写代号） | B |
| `ladder-ratings.csv` | 各级各 bot 的 Elo、区间、风格、sha256 | B |
| `standard-budget.json` | 标准预算自测：投入的 token 和时间、主分数、每一级的成绩 | B |

隐藏的 bot 只写代号和 sha256。
