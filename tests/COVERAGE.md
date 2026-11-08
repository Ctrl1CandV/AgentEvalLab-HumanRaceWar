# 测试覆盖与边界

测试入口：`.venv/bin/python tools/run_tests.py`。运行bot和C++编译的测试仍使用bwrap；本宿主不可裸用plain。

## 当前记录

- A阶段交审前：`PYTHONHASHSEED=0/1`各198项通过，零失败/错误/跳过；13文件Pyright零诊断。汇总：`data/phase-a/acceptance/tests.json`。
- 本轮仅整理目录与上传范围：发布检查、规则/确定性、合成回放兼容和开局分析的专项测试，见`data/phase-a/acceptance/publication.json`。这不是重跑全部198项或新的D6样本。
- 以前的失败、修复和测试次数均保留；详细历史说明见`docs/history/test-coverage-before-publication.md`，完整旧日志在本机归档。

## B前置留出工具（2026-11-08）

- 本轮开工基线203项通过；新增`test_phase_b_holdout.py`9项合成测试在`PYTHONHASHSEED=0/1`各通过，3个新Python文件Pyright零诊断。未宣称新增工具后重跑完整212项；汇总见`data/phase-b/tool-validation.json`。
- 覆盖隐藏路径/符号链接边界、先保存计划后生成、原计划续跑及拒绝重抽/覆盖、重复即停、登记、2208项精确配对、指定5项停点、聚合输出字段白名单和不完整统计拒绝。
- 这些测试不读真实隐藏地图、不执行bot，不等于留出或B阶段验收通过。

## 主要覆盖

| 范围 | 测试与已验证内容 |
|---|---|
| 规则、协议 | `test_rules.py`、`test_protocol.py`：结算次序、战斗/经济、出兵/建造、终局、非法输入与21项默认参数 |
| 确定性、对称 | `test_determinism.py`：历史固定哈希、默认配置逐步复现/旋转换边、全事件及625种移动组合 |
| 运行器、隔离 | `test_runtime.py`、`test_review_runtime.py`、`test_security_acceptance.py`：启动、END计费、进程/线程、超时/洪泛、环境与路径/网络隔离、进程树清理 |
| 资源、平台 | `test_review_balance.py`、`test_platform.py`：编译序列化/限额、TMPDIR、CPU租约、缓存、结果恢复与批调度 |
| 地图 | `test_mapgen.py`：资源、对称、D5步行距离、基地/出兵空间，拒绝把fixture当正式图 |
| 动物园策略 | `test_zoo.py`、`test_zoo_strategy.py`：生成与沙箱编译、资金/交通、兵力/回防、终结目标、建造任务分配等反例 |
| 分析 | `test_harassment_analysis.py`、`test_opening_analysis.py`：计数口径、缺失里程碑分母、生成战士的首个回合 |
| 发布 | `test_publication.py`：逐局文件/改名记录拒绝、聚合和失败计数保留、计时数组汇总、按暂存字节检查而非工作区副本 |

## 不依赖真实对局文件的单测

`tests/synthetic_replay.py`在本机`runs/`生成明确标记的合成输入：固定指令、旧格式终局字段和状态哈希。旧回放格式兼容与开局分析测试使用它，不执行bot，也不把它算作实验数据。

冻结参数检查读取已发布完整矩阵的运行配置；真实对局初始状态/参数核对已在整理前验收完成，原件留本机。测试不会因真实回放未上传而静默跳过。

## 不能据此宣称

- 沙箱测试不是穷尽攻击证明；资源契约不等于cgroup总量硬配额。
- 反例修复不是平衡结论；平衡仍由分版本完整矩阵决定，不合并最终重复复跑的分母。
- 公开集调参结果不代表隐藏地图、正式阶梯或评测机已验收；A已通过，B前置留出未通过并已停止，C未启动。
- 发布检查只覆盖已知格式，仍需人工核对新格式和提交范围。不上载明细不等于删除失败或清除旧Git历史。
