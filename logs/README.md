# 审查日志

只保留当前必要的诊断，不上传对局流或逐局结果。

- `determinism.log`、`robustness.log`：当前确定性和运行器回归。
- `issues.md`：风险与已处理问题。
- `phase-a/tests/`：最后全套测试的两次通过及首次失败。首次失败是审查副本，已移出其中一条逐次尝试字典；完整原件仍在本机，失败计数和诊断保留。
- `phase-a/regressions/`：启动竞态、建造任务分配、编译限额的关键修前/修后记录。
- `phase-a/publication.log`：A阶段精简与干净检出测试。
- `phase-b-ladder.log`：L0澄清、主线dev01–dev03开发的验证/预算/用量摘要，不含隐藏实现或逐局信息。
- `phase-b-review.log`：第二份B审查R1/R2及N1/N2/N3处理、验证和用量摘要，不含逐局证据。
- `phase-b-damage22.log`：授权一轮5888局的完整性、失败门槛、回放诊断和停点摘要；不是对局流。
- `phase-b-holdout.log`：2208局前置留出与工具检查的聚合诊断；第1、2项失败后停止。没有逐局记录，完整日志只留private。

其余完整日志保留在本机 `runs/local-evidence/509f1f8-before-summary-only/logs/`；各阶段汇总在 `data/phase-a/`。减少上传文件不代表删除旧失败或重跑实验。
