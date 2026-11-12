# 审查汇总

这里不再存放实际对局的逐局数据。完整结果、回放、失败尝试和逐局索引均保留在本机，见 [`docs/REPOSITORY.md`](../docs/REPOSITORY.md)。

## 当前入口

- [`phase-b/e-strength01-preflight.json`](phase-b/e-strength01-preflight.json)：已批准public2320执行前置，121文件冻结、零重试控制器及纯检查；实际执行仍0，登记见[`e-strength01-preflight-registration.json`](phase-b/e-strength01-preflight-registration.json)。

- [`phase-b/author-r04-engineering-repair-review.json`](phase-b/author-r04-engineering-repair-review.json)：旧工程包协调审查聚合，52文件原样归档、6组工程阻塞，E只核89项摘要。新工程包未接收，用户要求共享收束后继续已批2320局；收束见[`e-strength01-integration-registration.json`](phase-b/e-strength01-integration-registration.json)。

- [`phase-b/e-strength01-preparation.json`](phase-b/e-strength01-preparation.json)：下一轮public强度提案及存量复用核对，480旧局摘要/头/旧审计凭据和92冻结文件/四入口匹配；10纯检查双seed，本批零新增执行。该准备时点2320新局尚待批准，随后用户已明确批准，但未因此视作已计分；收束见[`e-strength01-preparation-registration.json`](phase-b/e-strength01-preparation-registration.json)。
- [`phase-b/e-qualification02-p0.json`](phase-b/e-qualification02-p0.json)：资格02完整P0通过后停止，实际1快照/6编译/126启动/4066回复＋8参考步=4074项/1check/0计分，压力和停后只读审计聚合；不证明强度改善，不自动P1/P2。收束登记见[`e-qualification02-closure-registration.json`](phase-b/e-qualification02-closure-registration.json)，641668项全摘要通过、零例外。
- [`phase-b/e-qualification02-preflight.json`](phase-b/e-qualification02-preflight.json)：用户新批准的单次P0资格02前置，92文件/6入口冻结，14纯检查双seed及4文件LSP通过；8参考步已记账，不是运行成功或强度证据。执行前登记见[`e-qualification02-preflight-registration.json`](phase-b/e-qualification02-preflight-registration.json)，639726项全量摘要通过，旧trial01账本不变。
- [`phase-b/e-compute-trial01-postmortem.json`](phase-b/e-compute-trial01-postmortem.json)：停后只读证据复盘、纯检查及当时的新资格提案预算；该批零新执行、未写候选/冻结，原trial01判定和用量不变；资格02的新授权与实施另列。
- [`phase-b/author-r04-ready-package-review.json`](phase-b/author-r04-ready-package-review.json)：原协调会话的工程准备包聚合；旧记录对照不是引擎重放，复用资格未过，下一修订由用户转交；E只集成队列。

- [`phase-b/e-compute-trial01-p0.json`](phase-b/e-compute-trial01-p0.json)：两份真实P0均失败，最终计数与只读核验；本轮停止、0新计分，压力工作量不是强度证据。

- [`phase-b/author-r04-plan-v2-review.json`](phase-b/author-r04-plan-v2-review.json)：原协调会话的v2接收/审查聚合；E仅集成receipt，未重做作者审计，不授权执行。

- [`phase-b/e-compute-trial01-preflight.json`](phase-b/e-compute-trial01-preflight.json)：E执行前置、精确日程和纯检查；freeze01已在新共享静止窗口全量登记，此登记检查点实际执行0，不是P0通过；保全/登记见`phase-b/e-p0-preflight-registration.json`。

- [`phase-b/e-handoff-integration.json`](phase-b/e-handoff-integration.json)：新E会话接手及统一收束；旧637075文件不变、新637169文件登记/全摘要通过。仅字节保全，E仍零编译/启动/新局，不是P0通过。

- [`phase-b/author-r04-plan-review.json`](phase-b/author-r04-plan-review.json)：6文件计划接收/预算核对/审查与下一项有界任务聚合；未授权r04执行，零bot/新局，接收后的全量登记已由新E会话统一收束。
- [`phase-b/author-r03-reconciliation.json`](phase-b/author-r03-reconciliation.json)：9文件补正账本核对；原失败、35启动/2199回复和快照超限不变，未知CPU不补造；补正收束。

- [`phase-b/author-r03-review.json`](phase-b/author-r03-review.json)：r03功能失败、未计分；35次启动/2199回复、实际源码超限与判据问题，300文件接收和34份轨迹重步聚合。这是原补正前检查点，补正及后续计划审查见上列最新汇总；不采纳或扩大评测。

- [`phase-b/next-preparation.json`](phase-b/next-preparation.json)：7份作者材料归档与静态来源/配对核对、18项双hashseed纯测试及保全用量；记录当时用户已转交有限修复、尚待反馈的时点。该准备批astra尚待试验批准，零bot/新局、未实现候选；其后一次E试验已获批，当前进度见STATUS。

- [`phase-b/astra-stop-review.json`](phase-b/astra-stop-review.json)：旧6720public账本配对复核，终选56改善/42退步，训练五个最高分条件逐格胜负相同；新方案预算算术与纯测试。复盘时未获实施授权、零新局，不是新强度结果；后续明确授权不改写此历史时点。

- [`phase-b/author-r02-review.json`](phase-b/author-r02-review.json)：作者r02的160局及1次check核验、阴性停止与原样保全；主仓库零新局，不批准r03；这是补正前检查点，后续前置定位归档和有限修复转交状态见STATUS及本次准备汇总。

- [`phase-b/mainlines-dev05.json`](phase-b/mainlines-dev05.json)：完整6720public搜索＋80dev首段；候选37.5%低于45%早停线，不采纳。复用1440局、追加5360，保留一次启动前资源错误；连续三轮止损，不追加下一候选。收束检查见[`phase-b/dev05-completion-validation.json`](phase-b/dev05-completion-validation.json)：专项检查、8080份当前评测回放摘要复核、旧证据两项明确生命周期例外及最终632178文件登记。
- [`phase-b/author-addendum-D-c01.json`](phase-b/author-addendum-D-c01.json)：补充198份既有作者/公开参考对局，纠正2份误归，合计2814份记录及6份历史调试故障；补充会话自述不证明原开发身份；这是r02执行前的历史快照，后续见上列r02复核。

- [`phase-b/author-intake-D-c01.json`](phase-b/author-intake-D-c01.json)、[`phase-b/author-evaluation-D-c01.json`](phase-b/author-evaluation-D-c01.json)：首份作者交付/旧2616局普查及随后统一1280局评测，原件不改、所有回放核验通过；流程缺项与强度不足如实记录，仅保留同作者首版比较基线，不替换现有控制线，独立会话尚未核实。

- [`phase-b/dev05-checkpoint.json`](phase-b/dev05-checkpoint.json)：dev05完成1440局public和默认逐回合等价核验，下一批启动前因CPU资源暂停时的历史快照；当时搜索/取舍未完成，资源错误本身不是拒绝。实现前纯检查见[`phase-b/dev05-preflight.json`](phase-b/dev05-preflight.json)。

- [`phase-b/dev-maps.json`](phase-b/dev-maps.json)：新增80张dev图的布局/再生和六集合不重复检查聚合，无新对局，不含逐图记录。
- [`phase-b/author-workspaces.json`](phase-b/author-workspaces.json)：试探/DeepSeek两份公开材料目录的清单与检查；不等于模型会话、记忆隔离或bot运行已验收。
- [`phase-b/mid-review.json`](phase-b/mid-review.json)：2026-11-09中期审查L1–L6既有档案聚合：饱和度计数、实际CPU、SEED证据边界、直接比较敏感性、机器绑定及临时BT（含分离/不可识别）；没有新对局，不是正式等级。`mid-review-validation.json`记录M1修前失败、最终35项双hashseed纯检查、逐线对手池纠正及验证边界。

- [`balance.json`](balance.json)：最终平衡条件、公平性、结束方式。
- [`zoo-matrix.csv`](zoo-matrix.csv)：按bot配对/地图类型聚合的局数和胜平负，不是逐局表。
- [`timing.json`](timing.json)：当前效率汇总；历史评估明确标注。
- [`phase-a/acceptance/`](phase-a/acceptance/)：测试、累计验证、资源、效率及发布检查。
- [`phase-a/matrices/`](phase-a/matrices/)：各版本分别保存的完整聚合矩阵；不混池、不隐藏失败。
- [`phase-a/regressions/`](phase-a/regressions/)、[`phase-a/diagnostics/`](phase-a/diagnostics/)：反例和成因汇总。
- [`phase-a/usage/`](phase-a/usage/)：不完整且相互重叠的用量快照，不可相加。
- [`phase-a/history/`](phase-a/history/)：早期开发汇总、v5基线和历史检查点。
- [`phase-a/catalog.json`](phase-a/catalog.json)：整理前后审查文件的位置对照。
- [`phase-b/final-holdout-maps.json`](phase-b/final-holdout-maps.json)：新24图holdout的布局/独立检查及五集合代表性汇总，不含逐图数据。`ladder-anchor-preflight.json`仅为原v15 L0两bot诊断，非完整阶梯Elo；原构成停点已由用户2026-11-09澄清。`preflight-validation.json`含最终249项测试等验证。
- [`phase-b/l0-resolution.json`](phase-b/l0-resolution.json)：既有128局终局核查，支持保留原版L0基础组，不强求内部等强；`l0-common-opponents.json`补查全部7个共同对手，不能据此声称两者同强。不是新实验或全阶梯校准。
- [`phase-b/mainlines-dev04.json`](phase-b/mainlines-dev04.json)：新1872局完整比较及144局被动诊断汇总、105项最终合成检查；初稿失败与负结果保留，未采纳，仍以dev02为基线。
- [`phase-b/mainlines-dev03.json`](phase-b/mainlines-dev03.json)：算法候选1872局、96项合成检查和完整配对变化；如实保留退步，未提升为开发基线，非正式验收。
- [`phase-b/mainlines-dev02.json`](phase-b/mainlines-dev02.json)：修订版1872局、配对变化、57项合成检查和固定预算核查；公开仅跨主线范围及汇总，不披露具体弱点关系。
- [`phase-b/mainlines-dev01.json`](phase-b/mainlines-dev01.json)：三条私有主线原型首批1728局的运行、验证、预算及准备状态汇总；没有公开具体弱点对应关系。原型仍需增强，非正式阶梯验收。`development-start-validation.json`记录完整257项测试及39项合成探针。
- [`phase-b/margins.json`](phase-b/margins.json)、[`type-counters.json`](phase-b/type-counters.json)、[`maze-hypothesis.json`](phase-b/maze-hypothesis.json)：第二份审查N1/N3/N2聚合证据；全部实际失败仅差1图，新标准生效；目标假设有反例，不改M。`review-validation.json`与`analysis-validation.json`分别记录R1和分析工具验证。
- [`phase-b/damage22/`](phase-b/damage22/)：唯一获准的D22试验5888局聚合；`results.json`为失败判定，两张CSV为完整候选矩阵及全配对差值，`trajectories.json`/`cohorts.json`为重点全队列及探索性转移分组。另有限额普查、来源、CPU及验证汇总，不含逐局数据。
- [`phase-b/holdout-v15.json`](phase-b/holdout-v15.json)、[`phase-b/holdout-matrix.csv`](phase-b/holdout-matrix.csv)：2208局留出的指定验收、地图簇区间及聚合矩阵；第1、2项失败。`maps.json`、`provenance.json`、`usage.json`和`tool-validation.json`分别记录地图构成/摘要、来源、CPU和工具检查，不含隐藏布局或逐局数据。

JSON中的`_publication`记录本机完整原件及SHA-256。矩阵、区间、失败总数与原件保持一致；只移出了逐局明细。旧引用中尚未迁移的路径按历史快照解释，原件可在本机归档查找。

`phase-a/history/checkpoint.sha256`保留历史检查点的原字节和原路径，需在对应历史树核对；本轮文件以根`MANIFEST.sha256`为准。

A已通过审查，`phase-a/`保留的是审查前各次实测及发布记录，不改写为新实验。B前置留出与D22按旧标准失败；第二份审查的N1完成后，新留出标准生效，原v15前置按新标准通过，D22仍拒绝。新holdout布局已通过、尚无对局；L0问题B-L0-001已关闭，继续阶梯开发，见STATUS。隐藏资产、相关原始对局及合并分析只放`private/`，公开原始对局只留本机`runs/`。已开始主线原型开发，尚无正式阶梯，C未启动，不填造Elo、grade或自测结果。
