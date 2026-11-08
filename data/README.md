# data

## 2026-11-08交审入口

| 文件 | 内容 |
|---|---|
| `zoo-standard-1-final/`、`zoo-matrix.csv`、`balance.json` | 最终框架/参数/动物园的完整3680局，全部数值条件通过；不与此前候选合并 |
| `zoo-v14-p7-public/`、`zoo-v15-p7-public/` | v14仍失败、v15首次通过；最后交付复跑与v15的全部结果/游戏指标一致，不增加独立样本 |
| `phase-a-final-tests.json`、`phase-a-startup-race.json` | 两个哈希种子各198项、13文件LSP零诊断；首轮失败、启动竞态反例与修复全保留 |
| `phase-a-final-validation/` | 61,979次尝试含186 infra_error/4 configuration_error；61,789份完整回放全验证，分块摘要在report中 |
| `phase-a-security-final.json`、`efficiency-v5.json` | 二审资源契约的最终检查；正式空闲参考下的新配置效率实测，9局回放通过 |
| `phase-a-baseline-v5/` | 更新根目录汇总前的原v5 balance与matrix原件 |
| `csv-canonicalization.json` | 60个生成CSV按Git策略转LF，逐格内容相同；CRLF原字节在runs留存 |
| `usage-pi-current-subset.json`、`usage-pi-final-subset.json` | 11-08两次可见两会话文件的部分用量；最终快照70,902,675，不能与历史三文件快照相加 |

具体逐条结论见 `reports/phase-A.md`。以下历史条目保留各批当时的结论；B阶段文件只是计划，尚未创建。

## 历史与分类索引

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
| `zoo-repair-tests.json`、`zoo-v3-budget-pilot/`、`zoo-v4-traffic-pilot/`、`zoo-v5-yield-pilot/` | 资金/交通各最小失败测试、窄修、14局定向及三版各368局独立练习矩阵；全部回放验证，不混池 | A（策略诊断） |
| `zoo-v5-public/` | 正式40图3680局及地图bootstrap/逐回放审计；无bot故障，平衡1/2/7未通过 | A（正式D6，未通过） |
| `harassment-v5/`、`harassment-analysis-tests.json` | 旧v5全部720局骚扰对局的工兵死亡位置、交战前兵力和结束方式；逐回合hash核对，4项统计/战斗例子通过 | A（全量成因诊断） |
| `review-balance-runtime.json` | 第二次审查编译16任务/64MiB文件/串行锁及TMPDIR修复；失败复现、174项全套 | A（审查修复） |
| `zoo-p1-worker-survival/`、`zoo-p2-slower-mining/`、`zoo-p3-soldier-cost/` | 各3680局独立参数试验及全部回放审计，均未通过平衡；不混池、不覆盖v5 | A（完整D6失败候选） |
| `phase-a-balance-trials.json` | 二审后的完整D6批次索引，参数/源码/地图/折算参考/原始用量与结果分版本保存，不混池 | A（分版试验档案） |
| `zoo-p4-opening/`、`zoo-p5-siege/`、`zoo-p6-worker-cost/`、`zoo-p7-start-workers/` | 后四个完整3680局参数候选，全验证，均未通过 | A（完整D6失败候选） |
| `zoo-v7-p7-public/`、`zoo-v8-p7-public/`、`zoo-v9-p7-public/`、`zoo-v10-p7-public/`、`zoo-v12-p7-public/` | 固定P7的分版策略完整矩阵，各3680局、全验证，失败保留 | A（完整D6，未通过） |
| `harassment-opening-p4/` | 全部80局速攻/骚扰及80局经济/骚扰的开局时序、兵力、工兵死亡；缺失里程碑单列分母 | A（回放诊断） |
| `zoo-v6-regression.json`—`zoo-v15-regression.json` | 各实际存在版本的真实bwrap决策回归、源码摘要；v13另含两局仍失败的迷宫定向回归 | A（策略试验，不替代矩阵） |
| `review-balance-v7-full-seed0.json`、`review-balance-opening-tests.json` | v7代码182项全套通过；开局统计新增2项单独通过，不冒充最新完整测试 | A（开发回归） |
| `phase-a-validation.json`、`phase-a-validation-attempts-*.json`、`phase-a-validation-replays-*.json` | 两轮170项、全部5036 complete与30 infra_error索引、最终框架全回放复核；分块文件摘要在主索引中 | A（未冻结验收检查点） |
| `phase-a-security.json`、`security-stress.json` | 运行时有界资源/清理及6局压力通过；编译树总资源仍无硬约束，明确未完成安全验收 | A（部分通过） |
| `efficiency-v2.json`、`efficiency-v3.json`、`efficiency-v4.json` | 2/20/50ms看门狗版本；各三组引擎样本、3个单局/6并发满预算局及本地校准。全部原始极值保留，六局整局>35秒 | A（未全部通过） |
| `usage-pi-local.json` | 仅本项目本地pi会话usage数值的去重汇总；含缓存输入，历史及未报告用量仍缺失，不导出对话或个人配置 | A（不完整用量） |
| `zoo-matrix.csv` | 动物园各 bot 之间的局数、胜、平、负，分地图类型 | A |
| `balance.json` | 先后手公平、平局率、对局长度分布、结束方式 | A |
| `timing.json` | `currentEfficiencyAcceptance`为最终v5通过结果；旧曲线、v4测量及裁定前评估保留为历史。C阶段完整评分仍未测 | A、后续C |
| `ladder-matrix.csv` | 阶梯各 bot 之间的成对对局数、胜、平、负（只写代号） | B |
| `ladder-ratings.csv` | 各级各 bot 的 Elo、区间、风格、sha256 | B |
| `standard-budget.json` | 标准预算自测：投入的 token 和时间、主分数、每一级的成绩 | B |

`phase-a-checkpoint.sha256` 是提交3076570时的历史未冻结检查点，后续审查修正不会覆盖其原摘要；它不描述当前工作树，不代替A通过后的发布MANIFEST。第二次审查已确认v4效率数据按p95及折算后整局上限达到；评测机bench已到inbox，旧数据中的“参考未知/待裁定”保留为历史表述。编译资源按第二次审查的逐进程/任务/串行契约补齐，不再等待cgroup。

隐藏的 bot 只写代号和 sha256。
