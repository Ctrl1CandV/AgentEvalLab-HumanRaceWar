# 状态

- 最近更新：2026-11-06（构建者开工）
- 当前阶段：A，进行中；先实现引擎与规则例子测试，尚未完成验收
- ruleset：standard-1 的起点数值（DESIGN 附录 A），尚未调参
- 引擎版本：—

## 本次更新了什么

- 建立仓库：
  - 设计（docs/DESIGN.md）；
  - 任务书（docs/BRIEF.md）；
  - 目录结构；
  - 提交前检查（.githooks/pre-commit）。
- 计分已定（用户 2026-11-06）：
  - 主分数取各级得分的平均；
  - 每局得分 = 0.75 × 胜负分 + 0.25 × 过程分；
  - 过程分目前是雏形（DESIGN 第 12 节），C 阶段由构建者用数据补齐。

## 卡住的地方

- WSL2 Ubuntu 22.04.5 中只有 Python 3.10.12，`python3.13` 不在 PATH，检查的 `/usr/local/bin` 和 `/opt` 中也未找到。正式环境要求 Python 3.13，未获许可不安装。
- D 盘未挂载到 WSL，`/mnt/d` 下访问不到本仓库。可以仅复制公开引擎和测试到 WSL 临时目录做开发验证，不修改挂载或安全配置。
- GCC 11.4.0、bubblewrap 0.6.1 已有；bwrap 中执行可信 `/bin/true` 成功。这不代表完整沙箱隔离、跨命名空间 CPU 计时已经验收。见 `data/environment.json`。

## 需要评测负责人或用户决定的事

- 请用户授权安装 WSL Python 3.13，或提供已有 Python 3.13 的路径。当前不会运行 bot、进行校准或报告正式性能结果。
- 如需直接在 WSL 使用本仓库，请用户确认 D 盘的挂载方式；也可继续通过仅含本项目公开代码的临时副本开发。

## 对 inbox/ 审查意见的回复

| 意见文件 | 条目 | 处理 |
|---|---|---|
| `inbox/README.md` | 工作流程说明 | 已读；当前无审查意见文件。 |

## 用量

| 阶段 | 模型 token | CPU 小时 | 机器配置 |
|---|---|---|---|
| A（进行中） | 当前工具未提供可靠累计计量，未知，待宿主补记 | 对局 0；开发检查尚未累计计量，不冒充总用量 | i5-14600KF，WSL 可见 20 逻辑 CPU、约 15.53 GiB 内存；速度系数未标定，详见 `data/environment.json` |

## 本次开工记录

- 已按要求阅读 inbox、DESIGN 全文、BRIEF、STATUS。
- 已运行 `git config core.hooksPath .githooks`；沿用当前 `main` 分支，小步本地提交，不推送。
- 新增离线环境探测 `tools/check_environment.py`，不读取凭据、不下载、不执行 bot。
