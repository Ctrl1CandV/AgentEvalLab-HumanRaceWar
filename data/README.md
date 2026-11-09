# 审查汇总

这里不再存放实际对局的逐局数据。完整结果、回放、失败尝试和逐局索引均保留在本机，见 [`docs/REPOSITORY.md`](../docs/REPOSITORY.md)。

## 当前入口

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
- [`phase-b/mainlines-dev03.json`](phase-b/mainlines-dev03.json)：算法候选1872局、96项合成检查和完整配对变化；如实保留退步，未提升为开发基线，非正式验收。
- [`phase-b/mainlines-dev02.json`](phase-b/mainlines-dev02.json)：修订版1872局、配对变化、57项合成检查和固定预算核查；公开仅跨主线范围及汇总，不披露具体弱点关系。
- [`phase-b/mainlines-dev01.json`](phase-b/mainlines-dev01.json)：三条私有主线原型首批1728局的运行、验证、预算及准备状态汇总；没有公开具体弱点对应关系。原型仍需增强，非正式阶梯验收。`development-start-validation.json`记录完整257项测试及39项合成探针。
- [`phase-b/margins.json`](phase-b/margins.json)、[`type-counters.json`](phase-b/type-counters.json)、[`maze-hypothesis.json`](phase-b/maze-hypothesis.json)：第二份审查N1/N3/N2聚合证据；全部实际失败仅差1图，新标准生效；目标假设有反例，不改M。`review-validation.json`与`analysis-validation.json`分别记录R1和分析工具验证。
- [`phase-b/damage22/`](phase-b/damage22/)：唯一获准的D22试验5888局聚合；`results.json`为失败判定，两张CSV为完整候选矩阵及全配对差值，`trajectories.json`/`cohorts.json`为重点全队列及探索性转移分组。另有限额普查、来源、CPU及验证汇总，不含逐局数据。
- [`phase-b/holdout-v15.json`](phase-b/holdout-v15.json)、[`phase-b/holdout-matrix.csv`](phase-b/holdout-matrix.csv)：2208局留出的指定验收、地图簇区间及聚合矩阵；第1、2项失败。`maps.json`、`provenance.json`、`usage.json`和`tool-validation.json`分别记录地图构成/摘要、来源、CPU和工具检查，不含隐藏布局或逐局数据。

JSON中的`_publication`记录本机完整原件及SHA-256。矩阵、区间、失败总数与原件保持一致；只移出了逐局明细。旧引用中尚未迁移的路径按历史快照解释，原件可在本机归档查找。

`phase-a/history/checkpoint.sha256`保留历史检查点的原字节和原路径，需在对应历史树核对；本轮文件以根`MANIFEST.sha256`为准。

A已通过审查，`phase-a/`保留的是审查前各次实测及发布记录，不改写为新实验。B前置留出与D22按旧标准失败；第二份审查的N1完成后，新留出标准生效，原v15前置按新标准通过，D22仍拒绝。新holdout布局已通过、尚无对局；L0问题B-L0-001已关闭，继续阶梯开发，见STATUS。隐藏资产、相关原始对局及合并分析只放`private/`，公开原始对局只留本机`runs/`。已开始主线原型开发，尚无正式阶梯，C未启动，不填造Elo、grade或自测结果。
