# HumanRaceWar 构建者说明

本仓库的后续搭建和开发在 WSL Ubuntu 22.04 内进行，工作目录为 `~/projects/AgentEvalLab-HumanRaceWar`。Windows 原目录仅保留迁移前备份，不在两边同时开发。后续提交、推送和拉取都在这个 WSL 仓库执行，Windows 备份不再参与同步。

## 每次开工

1. 先看 `inbox/` 是否有新审查文件，再完整阅读 `docs/DESIGN.md`、`docs/BRIEF.md`、`STATUS.md`。
2. 首次接手补读 `docs/WSL_HANDOFF.md`、`docs/IMPLEMENTATION_NOTES.md`、`tests/COVERAGE.md`。
3. 检查 `git status --short --branch`，保留用户改动；确认 `git config --get core.hooksPath` 为 `.githooks`。
4. 使用 `.venv/bin/python` 或 `python3.13`；不要把 `/usr/bin/python3` 的 3.10 当作项目解释器。测试入口：`.venv/bin/python tools/run_tests.py`。

## 实施边界

- 当前仍是 A 阶段，以 STATUS 的最新记录为准。先完成运行器、SDK、示例、match 和完整回放的小闭环，再按任务书推进。
- 框架只用 Python 标准库。所有 bot（包括示例、动物园、测试用故障 bot）及 C++ 编译必须在沙箱中执行。WSL 和 pi 本身不等于 bot 沙箱；在本开发宿主上不能裸用 plain。plain 只用于已经有外层沙箱的情况。
- 不读取、打印或迁移凭据，不读取 pi 的 `auth.json`，不把认证或个人配置写入仓库；不修改或绕过现有代理、安全设置。启动 bot 沙箱时清理继承环境，只传必要的白名单变量；只挂载所需运行环境，不挂载整个用户 HOME。
- 本次用户只授权了环境安装与迁移；后续新增开发工具仍先询问。对局、bot 和项目构建不得联网下载代码或数据。
- 隐藏 bot、隐藏地图及涉及它们的对局只能在 `private/`；隐藏文件登记 `private/HIDDEN.sha256`。`runs/`、`.venv/` 不入库。不得绕过 pre-commit。
- 不改计分方式、规则机制、结算顺序、胜负条件、协议格式或验收指标。歧义按 BRIEF 3.3 公开记录；已有 I01–I08 还需要审查确认，不能当成批准记录。
- 如实保存全部对局及失败结果，不挑数据；记录用量，无法计量就标未知。

## 交付与停点

小步本地提交、每日更新 STATUS；推送不是自动授权。A 阶段结束时按 BRIEF 第 7 节写 `reports/phase-A.md`，更新 data/logs 和 MANIFEST，写“等待审查”并停止；未经审查不能进入 B 阶段。测试通过或环境迁移完成都不等于 A 阶段验收完成。
