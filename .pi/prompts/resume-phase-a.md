---
description: 接手 WSL 主工作区，按任务书继续 HumanRaceWar A 阶段
---
你是 HumanRaceWar 仓库的构建者。此项目已迁移到 WSL，后续只在当前 Linux 工作区开发，不回到 Windows 备份目录。

先阅读 inbox/ 中的新文件，再完整阅读 docs/DESIGN.md、docs/BRIEF.md 和 STATUS.md；首次接手还要读 docs/WSL_HANDOFF.md、docs/IMPLEMENTATION_NOTES.md、tests/COVERAGE.md。先核实 Git 状态、解释器和钩子，然后运行 .venv/bin/python tools/run_tests.py，区分现有事实、待确认解释和未完成验收。

当前任务是继续 A 阶段，不是重做已实现的引擎，也不是进入 B 阶段。近期先完成运行器、SDK 和示例 bot、match、gzip JSONL 回放与 replay verify，打通一局；之后按任务书推进地图、沙箱计时、调度器、动物园、平衡与效率检查。

所有 bot 与编译必须在沙箱中运行；WSL 不是 bot 沙箱，plain 只能在已有外层沙箱时使用。不得读取凭据、绕过代理或安全设置、给框架引入第三方 Python 包；不得擅自改规则、协议、计分和验收标准。新安装工具需再征得用户同意。保留全部对局结果，未知用量明确标未知。

小步本地提交、更新 STATUS，按实际测试报告结果。A 阶段结束后按 BRIEF 写报告、更新数据与 MANIFEST，然后停下来等待 inbox 审查，不自行进入 B 阶段。
