# logs

| 文件 | 内容 | 阶段 |
|---|---|---|
| `determinism.log` | 确定性、重放和对称测试的结果 | A |
| `robustness.log` | 乱码、超长输出、非法指令、崩溃、死循环的 bot 的测试结果 | A |
| `self-calibration.log` | 评分器自检的完整输出，包括噪声测试 | C |
| `issues.md` | 没解决的问题和已知的风险 | 一直更新 |
| `engine-tests.log`、`engine-tests-seed1.log` | 两个独立哈希种子进程的全套引擎测试 | A（开发检查） |

目前 `determinism.log` 只覆盖内存指令复现和对称测试，`robustness.log` 只覆盖字符串解析；真实回放、bot 进程、原始字节流、崩溃和超时尚未验证。各日志开头明确标注范围，不能据此声称 A 阶段完整验收通过。
