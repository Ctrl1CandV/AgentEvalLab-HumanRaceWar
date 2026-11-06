# logs

| 文件 | 内容 | 阶段 |
|---|---|---|
| `determinism.log` | 确定性、重放和对称测试的结果 | A |
| `robustness.log` | 乱码、超长输出、非法指令、崩溃、死循环的 bot 的测试结果 | A |
| `self-calibration.log` | 评分器自检的完整输出，包括噪声测试 | C |
| `issues.md` | 没解决的问题和已知的风险 | 一直更新 |
| `engine-tests.log`、`engine-tests-seed1.log` | Python 3.10 时期两个独立哈希种子进程的全套引擎测试 | A（历史开发检查） |
| `python313-engine-tests*.log` | WSL 主工作区 Python 3.13.15 的两次全套测试 | A（引擎检查） |
| `python313-determinism.log`、`python313-robustness.log` | Python 3.13.15 确定性与字符串解析测试，未覆盖真实 bot 进程 | A（引擎检查） |
| `wsl-setup.log` | 可信 Python/C++ 沙箱探针及 pi CLI/启动器检查，不含模型调用 | A（开发交接） |

目前 `determinism.log` 只覆盖内存指令复现和对称测试，`robustness.log` 只覆盖字符串解析；真实回放、bot 进程、原始字节流、崩溃和超时尚未验证。各日志开头明确标注范围，不能据此声称 A 阶段完整验收通过。
