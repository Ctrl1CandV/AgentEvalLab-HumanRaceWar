# 规则例子与验证边界

当前入口：WSL 主工作区执行 `.venv/bin/python tools/run_tests.py`，或 `.venv/bin/python -m unittest discover -s tests -t . -v`。全部只用标准库，不启动 bot。2026-11-07 迁移后已用 Python 3.13.15 在 `PYTHONHASHSEED=0`、`1` 两个独立进程中各通过 86 项测试，另外归档确定性与协议测试；证据见 `data/python313-tests.json` 和 `logs/python313-*.log`。这不等于完成 A 阶段整体验收。

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

## 明确尚未验证

- 完整回放文件的重放与哈希核对（Python 3.13.15 引擎测试已通过，但回放工具尚未实现）。
- 实际 bot 的 UTF-8 字节流、READY/END 分帧、输出洪泛、崩溃、编译失败、死循环和超时。
- 完整 bwrap 隔离、资源限额、CPU 绑核、跨命名空间 CPU 时钟、速度折算和框架重试。迁移仅补做可信 Python/C++ 环境探针，不是故障 bot 或沙箱安全验收。
- 地图生成器全部检查、公开与练习地图集、SDK、动物园和统计验收。
- 引擎 p95、运行器开销、整局速度及评分效率。

因此测试通过只表示 A1 引擎的开发检查通过，不能填报 A 阶段的 10 项总体验收通过。
