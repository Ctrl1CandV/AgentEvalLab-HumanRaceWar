# 审查日志

只保留当前必要的诊断，不上传对局流或逐局结果。

- `determinism.log`、`robustness.log`：当前确定性和运行器回归。
- `issues.md`：风险与已处理问题。
- `phase-a/tests/`：最后全套测试的两次通过及首次失败。首次失败是审查副本，已移出其中一条逐次尝试字典；完整原件仍在本机，失败计数和诊断保留。
- `phase-a/regressions/`：启动竞态、建造任务分配、编译限额的关键修前/修后记录。
- `phase-a/publication.log`：A阶段精简与干净检出测试。
- `phase-b-holdout.log`：2208局前置留出与工具检查的聚合诊断；第1、2项失败后停止。没有逐局记录，完整日志只留private。

其余完整日志保留在本机 `runs/local-evidence/509f1f8-before-summary-only/logs/`；各阶段汇总在 `data/phase-a/`。减少上传文件不代表删除旧失败或重跑实验。
