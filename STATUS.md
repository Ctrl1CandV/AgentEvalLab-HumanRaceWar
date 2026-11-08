# 状态

更新：2026-11-08。**A阶段完成，等待审查；未进入B。**

- 审查入口：[`reports/phase-A.md`](reports/phase-A.md)。
- 工作目录：WSL Ubuntu 22.04，`~/projects/AgentEvalLab-HumanRaceWar`；Windows备份不再同步。
- 交审配置：`standard-1` / zoo v15；完整参数见 `rules/standard-1.json`。
- 本轮只按用户要求精简上传内容、整理目录，并提交推送；不改变游戏、计分、验收门槛，不重跑验收对局。

## A阶段已验证结果

| 项目 | 结果 | 当前汇总 |
|---|---|---|
| 最终D6 | 40图、3680局，全部数值条件通过；M总体最低90%，分类型最低60% | `data/phase-a/matrices/zoo-standard-1-final.json` |
| M自对弈 | 80局：20拆基地、60回合上限；中位300回合 | `data/balance.json` |
| 配置复核 | 最终框架复跑与v15/P7的全部结果/原始指标一致；不增加独立样本 | `data/phase-a/matrices/trials.json` |
| 全套回归 | 整理前两个哈希种子各198项通过，13文件LSP零诊断 | `data/phase-a/acceptance/tests.json` |
| 累计回放 | 截至交审快照61,979次尝试：61,789 complete、186 infra_error、4 configuration_error；完整回放全验证 | `data/phase-a/acceptance/validation.json` |
| 效率 | 引擎p95≤0.7437ms；单局/六局runner p95=1.0278/1.6236ms，整局在20.9/23秒门槛内 | `data/timing.json` |

编译与运行资源按二审批准契约落实，不冒称cgroup总量配额或穷尽所有攻击面。各失败候选分版保留，详见阶段报告及 `reports/phase-A-balance-rework.md`。

## 本轮发布范围与目录整理

用户明确：开发机保留全部对局数据；远端只放审查所需的代码、测试、配置、文档和汇总。

- **不上传**实际对局回放、逐局CSV/JSON、结果库、逐局尝试/回放审计索引。公开bot的示例回放也不例外。
- 当前验收汇总、候选矩阵、回归、诊断、用量和历史汇总分别位于 `data/phase-a/` 的分类目录；`data/` 根目录仅保留主要汇总入口。
- 整理前555份证据文件逐字节保全于 `runs/local-evidence/509f1f8-before-summary-only/`，附本地SHA-256清单。`runs/development/` 中的全部原始运行也保留。撤下文件是归档，不是删除实验或失败记录。
- `logs/` 只保留当前确定性/健壮性和必要的验收、反例日志；旧完整日志留在本机归档。
- 测试不再依赖已撤下的真实回放：旧协议兼容与开局分析使用显式合成夹具，冻结参数与完整矩阵汇总核对。合成夹具不算实验数据，不执行bot。
- `.gitignore`及pre-commit增加发布范围检查；仍保留原凭据、隐藏内容、大小检查，不绕过钩子。
- 本轮检查结果见 `data/phase-a/acceptance/publication.json`，目录说明见 `docs/REPOSITORY.md`。

**历史限制：** `509f1f8`及以前已经上传过明细。本轮用普通提交从最新树撤下，不改写历史、不强推；完整clone仍可能取得旧对象，不能把本轮整理称为远端历史清除。

## 用量与后续停点

历史三会话文件快照77,321,999 token；11-08两文件快照70,902,675（缓存69,545,728，input+output 1,356,947）。两者重叠且来源不全，不能相加；后续整理调用未计入，完整总量未知。见 `data/phase-a/usage/`。

可核对的累计对局bot/宿主CPU为2.561/3.579小时，交审前累计回放复核另1.311小时；计数器及其他环节不全，阶段CPU总量未知。继续授权有效。

**本轮提交推送后停止，等待评测负责人审查A；不进入B。** 历史过程、旧路径与当时结论移至 [`docs/history/phase-a-progress.md`](docs/history/phase-a-progress.md)。
