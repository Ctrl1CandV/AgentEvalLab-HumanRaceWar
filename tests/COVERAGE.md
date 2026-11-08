# 规则例子与验证边界

当前入口：WSL 主工作区执行 `.venv/bin/python tools/run_tests.py`，或 `.venv/bin/python -m unittest discover -s tests -t . -v`。全部只用标准库；新增 `test_runtime.py` 会通过 bwrap 执行示例、故障 bot 和 C++ 编译，不会在宿主裸跑。2026-11-07 迁移时的引擎检查已用 Python 3.13.15 在 `PYTHONHASHSEED=0`、`1` 两个独立进程中各通过 86 项测试，另外归档确定性与协议测试；证据见 `data/python313-tests.json` 和 `logs/python313-*.log`。这不等于完成 A 阶段整体验收。

初始及第 80 回合的状态哈希有固定回归值。旧的 `data/engine-tests.json`、`logs/engine-tests*.log` 与 Windows 转发工具 `tools/test_in_wsl.py` 保留为 Python 3.10 时期的历史记录；后续在 WSL 原生目录直接测试，不再经 Windows 临时副本。

## 清理补查（策略v4）

`test_cleanup.py`增加5项：fork/preexec窗口内杀父进程、禁止清除死亡信号、worker启动失败跨续跑累计4次后不再尝试该任务、SIGKILL后恢复半截attempt、冻结地图改变属于配置错误而非bot负。外层plain补双槽批量并在宿主预留整个CPU池。初轮4项为3失败/1错误；修复后连同两项初版动物园回归，两个哈希种子全套各157项通过。新增归档117条记录（88 complete、25 infra_error、4 configuration_error）及原运行器漏写的一次worker启动的job证据，见 `data/cleanup-tests.json`；不是完整安全验收。

## 批量平台与原始统计

`test_platform.py` 的10项回归覆盖：warnings/failedOrders分列、失败移动、争塔去重、1HP目标过量伤害截断而状态哈希不变；CPU租约冲突/affinity恢复；JSONL撕裂尾部原样保留；真实C++缓存命中与损坏拒绝；check格式错误/协议检查；宿主拒绝plain与外层bwrap中的Python/C++/本地bench/折算对局；双槽CPU不重叠、换边换种子、完整任务跳过、清单变动拒绝；controller被SIGTERM后的清理与续跑，以及旧公开回放兼容。

最终两轮各 **150项通过**，0失败/错误/跳过；153次新增尝试全保留，其中130份完整回放全部验证。见 `data/platform-tests.json`、`logs/phase-a-platform-*.log`。测试中的plain也在明确创建的外层bwrap中，未在宿主裸跑。仍不等于动物园、效率或完整恶意提交安全验收。

## 规则覆盖

| DESIGN | 测试文件 / 类 | 关键例子 |
|---|---|---|
| 4.1 地图、坐标 | `test_rules.MapAndSetupTests`、`MovementTests` | 尺寸和字符校验、180° 对称、矿量对称、矿耗尽不变地形、曼哈顿相邻、越界 |
| 4.2、附录 A | `MapAndSetupTests`、`SpawnTests`、`BuildRegenAndResultTests` | 21 个参数的独立默认值断言、规则文档参数一致性和全部边界、开局状态、初始站位、单位造价和生命、人口、塔属性、回复 |
| 4.3 指令 | `test_protocol.ProtocolTests`、`AttackTests`、`MiningAndDepositTests`、`SpawnTests` | 所属方、合法目标、邻接、工兵能力、生产条件、基地两个槽、无指令不动 |
| 4.4.1 校验 | `ProtocolTests` | 第一条优先、语法错误不占槽、非法命令逐行独立、解析不修改状态 |
| 4.4.2 攻击 | `AttackTests` | 同时互杀、集火、移动前受击、死亡取消其他动作、基地毁灭立即终止、拆塔后次回合重建 |
| 4.4.3 生产 | `SpawnTests`、`MovementTests` | 双方争同格、不扣失败款、开始占格或人口已满不能利用阵亡、不能用后来卸货、新生单位占格 |
| 4.4.4 移动 | `MovementTests`、`test_determinism.DeterminismTests` | 非空地失败、多人争格、二人互换、阻塞链、通行链、四人轮转、争格先于互换；穷举四个单位各 5 种动作，共 625 组合 |
| 4.4.5 采矿 | `MiningAndDepositTests` | 需求上限、余矿充足/恰好/不足、零头销毁、携带容量不足不再分配、死亡矿工不参与平分 |
| 4.4.6 卸货 | `MiningAndDepositTests` | 移动后卸货、友方与邻接限制、多个卸货点只卸一次、死亡塔不能卸货、死亡携带量消失 |
| 4.4.7 建造 | `BuildRegenAndResultTests` | 使用当回合卸货、先生产后建造、双方争塔、同方重复、按 ID 而非指令行扣款、死亡最低 ID 不阻止其他存活工兵 |
| 4.4.8 回复 | `BuildRegenAndResultTests` | 移动后的范围、仅己方、上限、先伤害后回复、不能复活 |
| 4.4.9 计分 | `BuildRegenAndResultTests` | 新塔当回合得分、已毁塔不得分 |
| 4.5 终局 | `AttackTests`、`BuildRegenAndResultTests` | 单/双基地毁灭，分数/卸货/基地生命逐项比较，全相同平局，末回合卸货破平，终局不可再走 |
| 5.2–5.3 消息 | `ProtocolTests` | 初始化参数完整、观察信息完整、枯竭矿不发、INVALID 仅本方可见、BANK 不混入规则哈希 |
| 5.4–5.5 解析 | `ProtocolTests`、`DeterminismTests` | 空白和 CRLF、UTF-8 字节长度、每行/每回合限制、乱码字符串、200 组确定性模糊输入 |
| 3.3、10.2.8–9 | `DeterminismTests` | 80 回合固定指令逐回合复现、插入顺序不影响哈希、非对称局面及全部事件类型的旋转交换、终局对称 |

测试中的人工局面可刻意不满足地图生成器的资源布局验收，以便单独触发规则。它们不能作为 public 地图数量、动物园对局数或地图平衡数据。

## 新增运行器与 SDK 开发检查

`test_sdk.py` 的 2 项测试覆盖 Python SDK 字段、未知关键字、EOF、输出、曼哈顿距离与 BFS。`test_runtime.py` 的 19 项测试覆盖：

- 分块/CRLF/Unicode 空白分帧，超长伪 END、有界存储和持续输出后的标记恢复；非法 UTF-8 不膨胀字节预算、不丢弃后续合法指令；
- Python/C++ 示例完整 300 回合、采矿 bot 胜 idle、回放 show/summary/verify，以及地图、指令、警告、哈希、结果篡改和不完整回放；
- 单方/双方崩溃、无 READY、初始化死循环、回合 CPU/墙钟超时、时间储备只扣超额不回充；
- 编译失败、乱码/洪泛输出仍只记警告、无 END 洪泛被限时、stderr 64 KiB 上限；
- 真实 bwrap 环境清理、无 HOME/项目挂载、只读源码、无外网接口、资源限额、绑核和跨命名空间 CPU 时钟；
- 缺少 bwrap 和真实沙箱准备失败不算 bot 输，初次加三次重试全部归档，源码符号链接拒绝。

首局批次共 107 项开发测试；证据见 `data/runtime-tests.json`、`logs/runtime-*.log`。所有测试对局及失败尝试保留在 `runs/development/runtime/`，不挑选结果。CLI 首局另存 `runs/development/cli-smoke/`；代表性公开回放见 `replays/runtime-smoke.hrw.jsonl.gz`。以上仍不是 A 阶段总体验收。

## 地图生成与资产检查

`test_mapgen.py` 新增 12 项测试：SplitMix64 固定向量与有界抽样、非法配置、全部四类及边长 24–40、资源总量与独立 flood fill、固定种子地图摘要、地形差异、拒绝/重试上限、布局反例、44 张资产的去重与逐字节再生成、禁止覆盖不同内容。`maps/catalog.json` 的每张图均保留种子、摘要和布局指标；严格资源检查针对当前默认生成配置，不改变自定义 match 地图资格。

本批全套为 **119 项**，在两个哈希种子进程中各通过一次；四类 scrimmage 地图交换双方位置的 8 局沙箱示例联调均完成 300 回合，0 故障、0 警告，完整回放验证通过。原始结果及全套测试中的故障局均保留，证据见 `data/mapgen-tests.json`、`logs/mapgen-*.log`。这不是平衡或公平性验收。

## 2026-11-07 中途审查回归

新增 `test_review_runtime.py`、`test_review_policy.py`，共13项：真实bwrap下第5回合退出125只判负一次、END后后台线程CPU计入下一回合、fork循环与改绑核被拒、Python/C++线程可用且受硬限额、只读临时空间和共享内存文件旁路、编译2GiB、格式/符号链接/大小错误判提交方负、活动proc接口缺失报框架错误；另检查BPF的架构/clone分支、规则无计分细节、全部31个INVALID原因码齐全。

先复现初始9项回归的12个失败断言，修复后两轮全套各 **132项通过**（默认哈希种子、显式1），无失败/错误/跳过；Pyright检查7个文件无诊断。新76份完整回放和旧公开样例均验证通过；失败尝试与直接沙箱探针不删。详见 `data/review-runtime-tests.json`、`logs/review-2026-11-07-*.log`。

## bench、根目录补查与地图 v2

新增 `test_benchmark.py` 5项：整体预算缩放、拒绝无效校准、真实沙箱bench的READY屏障/输出及恢复affinity、保留失败尝试、校准match的LIMIT/硬上限/回放元数据。`test_map_walk.py` 3项以独立BFS检查全部44图，并构造隔墙家门矿和“同一近矿必须同时满足两种距离”的塔基反例。旧图先出现40条家门矿违规；v2修复后通过，原12项生成器测试也全部通过。

原只读文件系统回归加查合成根目录 `/`，先复现可写tmpfs再修正；追加SysV IPC/POSIX消息队列限制，并确认C++编译目录仍可写。前后日志及失败对局均保留。新两轮全套在哈希种子0/1下各 **140项通过**，无失败/错误/跳过；14文件Pyright最终0诊断。新增64份完整回放、10次框架失败均归档，完整回放及历史公开样例验证通过。其中四类v2练习图换边共8局使用实测jobs=1校准，均300回合且无故障，仅为CLI联调而非平衡/效率证据。证据：`data/review-bench-map-tests.json`、`data/timing.json`。

## 动物园交接基线

`test_zoo.py`检查10个独立提交与模板/catalog一致，并在真实bwrap中核对随机/采矿策略换边的逐回合指令旋转；`test_zoo_analysis.py`的3项纯统计测试核对地图簇重采样、胜率与半平得分率、nearest-rank分位数。v2策略下单轮全套160项通过，见 `data/zoo-repair-checkpoint.json` 和 `logs/zoo-v2-baseline.log`。两版各368局练习图回放均验证，但平衡未通过；驻塔工兵长期等钱的根因假设尚无定点回归。

## 资金和交通定点回归

`test_zoo_strategy.py`通过真实bwrap编译/运行SDK策略，4项覆盖：远处敌军不取消塔钱、近敌允许补兵、敌基地邻格全部占用不阻止远方推进、连续争格后短暂停让并接战。三个缺陷分别先出现失败再窄修，原始输入/回复均保留；单轮全套164项通过。`data/zoo-repair-tests.json`索引各阶段日志、14局定向回放及v3/v4/v5各368局独立练习矩阵。平衡仍未通过，不用这些练习局填正式D6分母。

## 安全与效率检查（历史170项回归）

`test_security_acceptance.py`新增6项：地址空间/描述符硬限制、已退出线程CPU、环境/网络/路径/只读、有限编译树停止清理、100ms忙等回复采样次数、5ms墙钟预算不被轮询上限放宽。旧2ms轮询先复现49次采样；最终50ms上限为5次。最初环境断言漏列bwrap生成的PWD，两个失败测试原件保留，修正测试而非修改环境白名单。

两个哈希种子各170项全通过，7文件Pyright零诊断。6局12bot线程超时压力全部正确判定并清理；5036份本轮完整回放在最终框架下全验证，30次infra_error保留。见 `data/phase-a-validation.json`、`data/phase-a-security.json` 和 `data/security-stress.json`。编译探针明确显示NPROC=63593、2GiB仅逐进程，不能据有界探针通过宣布总资源安全已验收。

## 第二次审查后的回归

`test_review_balance.py`新增4项：编译任务上限16、64MiB单文件上限、跨缓存目录编译串行、CPU/编译锁遵守TMPDIR。先出现2失败/1错误，再4项通过；当时全套174项通过。评测负责人已接受逐进程2GiB/CPU与60秒墙钟、16任务、协作串行的编译契约，不要求cgroup总量配额，不能把接受的契约说成硬性总内存/总磁盘限制。

`test_harassment_analysis.py`的4项覆盖回复前兵力、零分母与工兵参数对单挑的影响；`test_opening_analysis.py`的2项覆盖缺失里程碑分母及公开回放首个战士出生时序。v7代码单轮全套182项通过；后续新增项目分别测试，尚不能拼成最新全套通过。

`test_zoo_strategy.py`当前17项真实bwrap决策测试覆盖军费/塔预留、最低经济、回防距离与目标、敌工兵的威胁范围、固定经济目标、基地终结和短距离清障，以及既有占位/让路。每项人工局面只证明对应决策，不证明平衡改善。v13/v14的maze-01各两局定向回归仍双败并保存；正式版本仍各自完整3680局判断，不用定向局补分母。

## 最终交付回归（2026-11-08）

两个哈希种子全套各 **198项通过，0失败/错误/跳过**，见 `data/phase-a-final-tests.json`。旧规则例子显式使用原始参数fixture，旧固定哈希不改；另验证当前默认的21项数值、8个初始工兵、80回合逐步复现/旋转，以及与实际v15矩阵回放的参数和初始哈希一致。最终13文件Pyright零诊断；此前超时保留，项目配置排除了runs等产物索引。

M策略现有19项回归。新增最近建造任务分配及无可建塔址时释放预留预算，两项反例和原资金测试修前失败、修后通过。最终回归还发现启动竞态：stdin先断管时，stdout里已排队的可信启动标记未读，误报infra_error。两个真实bwrap提前退出反例修前报错；只补有界非阻塞读取后通过，缺标记仍按框架失败处理，时限和CPU计量未放宽。

首轮197项的70个失败断言全部保存：68个地图子例和1个协议断言仍指向旧默认，另1个启动竞态；不是70个独立实现缺陷。最终standard-1完整3680局与首次通过的v15/P7结果逐项相同，两个批次都全回放验证，不混成7360个独立样本。

## 验证边界

- 二审的资源、效率裁定及TMPDIR修复已落实；仍不声称穷尽所有攻击面，编译不是cgroup总量配额。
- 评测机空闲单实例bench已到inbox，新批次均使用它；正式AgentEvalLab工作区集成与C阶段全套评分效率尚未验证，不提前进入B/C。
- P1–P7及各策略候选、包括退步版本全量保留；最终矩阵通过不证明留出地图稳健性。见 `data/phase-a-balance-trials.json` 与 `reports/phase-A.md`；B阶段仍需更强对手复核。
- 最终v5效率复测亦达到：引擎p95≤0.7437ms，jobs1/6的runner p95为1.0278/1.6236ms；整局在20.9/23秒折算门槛内。最新最大3.9046ms与旧最大7.5831ms都保留，不当作门槛。

测试通过不自动等于阶段验收；结合完整矩阵、效率与资源证据后的逐项结论见 `reports/phase-A.md`，最终是否接受A由评测负责人审查。
