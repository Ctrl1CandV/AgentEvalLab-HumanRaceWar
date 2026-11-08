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

JSON中的`_publication`记录本机完整原件及SHA-256。矩阵、区间、失败总数与原件保持一致；只移出了逐局明细。旧引用中尚未迁移的路径按历史快照解释，原件可在本机归档查找。

`phase-a/history/checkpoint.sha256`保留历史检查点的原字节和原路径，需在对应历史树核对；本轮文件以根`MANIFEST.sha256`为准。

隐藏内容仍只放`private/`。B/C未启动，不创建或填造阶梯、grade和评分结果。
