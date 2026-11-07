# data

| 文件 | 内容 | 阶段 |
|---|---|---|
| `environment.json` | 初次开工的环境探测历史（Python 3.10）；不是性能验收 | A（历史开发检查） |
| `engine-tests.json` | Python 3.10 引擎测试历史、输入 sha256、测试进程 CPU 时间 | A（历史开发检查） |
| `environment-wsl-python313.json` | 迁移后 Python 3.13.15 / WSL 环境和机器配置 | A（环境检查） |
| `python313-tests.json` | 主工作区 Python 3.13.15 测试结果及输入 sha256；不是整体验收 | A（引擎检查） |
| `wsl-setup.json` | 用户级工具安装、工作区迁移、可信沙箱探针及未验证范围 | A（开发交接） |
| `runtime-tests.json` | 首局闭环、最终两次 107 项测试、UTF-8 失败复现与修复、全部 122 次对局尝试、88 份回放验证、源码摘要和不完整用量 | A（集成开发检查，不是平衡/效率验收） |
| `mapgen-tests.json` | 44 张地图的默认布局检查、两次 119 项测试、8 局换边联调及本批全部对局尝试；未作平衡验收 | A（地图/集成开发检查） |
| `review-runtime-tests.json` | 2026-11-07中途审查首批M1/M2/M3/M5/M6修复、失败复现、两轮132项测试及全部新增尝试；不是阶段验收 | A（审查修复开发检查） |
| `review-bench-map-tests.json` | bench/独立折算、根tmpfs补查、地图v2与D5反例、两轮140项测试、全部新增74次对局尝试（含8局v2地图校准换边联调）及10次bench调用索引 | A（开发检查，非整体验收） |
| `platform-tests.json` | check/缓存/全局CPU租约/进程调度/续跑/结果库/tournament及原始指标v2；两轮150项、全部153次新增尝试、24次bench和外层plain集成 | A（平台开发检查，非整体验收） |
| `cleanup-tests.json` | 父死亡/启动失败/强杀恢复、backend缓存隔离、冻结输入检查、两轮157项与全部新增归档记录；另列原运行器漏写worker启动的job证据 | A（开发回归，非完整安全验收） |
| `zoo-v1-pilot/` | 初版10策略、4张练习图的368局完整结果、地图bootstrap、全回放验证；M对骚扰/铺塔各50%，明确未达平衡条件 | A（练习图诊断，不是D6验收） |
| `zoo-v2-pilot/` | 第二版368局练习矩阵，全回放验证；M对骚扰4胜2平2负、对铺塔4胜4负，自对弈全为回合上限，未达平衡条件 | A（练习图诊断，不是D6验收） |
| `zoo-repair-checkpoint.json` | v2代码下单轮160项回归，以及maze失败回放中的驻塔工兵/资金停滞证据；资金分配根因待定点测试，未修v3 | A（会话交接，非阶段停点） |
| `usage-pi-local.json` | 仅本项目本地pi会话usage数值的去重汇总；含缓存输入，历史及未报告用量仍缺失，不导出对话或个人配置 | A（不完整用量） |
| `zoo-matrix.csv` | 动物园各 bot 之间的局数、胜、平、负，分地图类型 | A |
| `balance.json` | 先后手公平、平局率、对局长度分布、结束方式 | A |
| `timing.json` | 已有本机两批并发负载曲线、逐核样本及本地速度系数；引擎p95、运行器开销、整局和整套评分效率仍待测 | A（bench开发检查）、后续C |
| `ladder-matrix.csv` | 阶梯各 bot 之间的成对对局数、胜、平、负（只写代号） | B |
| `ladder-ratings.csv` | 各级各 bot 的 Elo、区间、风格、sha256 | B |
| `standard-budget.json` | 标准预算自测：投入的 token 和时间、主分数、每一级的成绩 | B |

隐藏的 bot 只写代号和 sha256。
