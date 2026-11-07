# 规则例子与验证边界

当前入口：WSL 主工作区执行 `.venv/bin/python tools/run_tests.py`，或 `.venv/bin/python -m unittest discover -s tests -t . -v`。全部只用标准库；新增 `test_runtime.py` 会通过 bwrap 执行示例、故障 bot 和 C++ 编译，不会在宿主裸跑。2026-11-07 迁移时的引擎检查已用 Python 3.13.15 在 `PYTHONHASHSEED=0`、`1` 两个独立进程中各通过 86 项测试，另外归档确定性与协议测试；证据见 `data/python313-tests.json` 和 `logs/python313-*.log`。这不等于完成 A 阶段整体验收。

初始及第 80 回合的状态哈希有固定回归值。旧的 `data/engine-tests.json`、`logs/engine-tests*.log` 与 Windows 转发工具 `tools/test_in_wsl.py` 保留为 Python 3.10 时期的历史记录；后续在 WSL 原生目录直接测试，不再经 Windows 临时副本。

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

## 明确尚未验证

- 完整沙箱攻击面、编译阶段进程树总资源、清理与压力矩阵、速度折算；单进程、线程上限、绑核和只读临时空间已有本机回归，不等于完整安全验收。
- 多局全局独占核、并行调度、断点续跑、共享结果库及正式工作区 plain 集成。
- D5地图步行检查与地图再生成；地图/策略动物园矩阵、平衡、公平性及统计验收。I11已经确认，不再等待批准。
- 引擎 p95、运行器开销、满负荷整局速度及评分效率。

因此测试通过只表示引擎、运行器和地图的开发检查通过，不能填报 A 阶段的 10 项总体验收通过。
