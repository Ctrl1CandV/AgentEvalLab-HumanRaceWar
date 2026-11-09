# HumanRaceWar 构建者说明

本仓库的后续搭建和开发在 WSL Ubuntu 22.04 内进行，工作目录为 `~/projects/AgentEvalLab-HumanRaceWar`。Windows 原目录仅保留迁移前备份，不在两边同时开发。后续提交、推送和拉取都在这个 WSL 仓库执行，Windows 备份不再参与同步。

## 每次开工

1. 先看 `inbox/` 是否有新审查文件，再完整阅读 `docs/DESIGN.md`、`docs/BRIEF.md`、`STATUS.md`。
2. 首次接手补读 `docs/WSL_HANDOFF.md`、`docs/IMPLEMENTATION_NOTES.md`、`tests/COVERAGE.md`。
3. 检查 `git status --short --branch`，保留用户改动；确认 `git config --get core.hooksPath` 为 `.githooks`。
4. 使用 `.venv/bin/python` 或 `python3.13`；不要把 `/usr/bin/python3` 的 3.10 当作项目解释器。测试入口：`.venv/bin/python tools/run_tests.py`。

## 实施边界

- A已通过，用户2026-11-08授权进入B。以STATUS和 `inbox/2026-11-08-phase-a-accepted.md` 为准：standard-1与动物园v15冻结；先生成隐藏地图并做24张calibration上的留出复核，未通过就停下报告，不建阶梯、不自行改参数或重抽地图。首次2208局留出已失败，见 `reports/phase-B-holdout.md`。用户随后授权仅一轮`SOLDIER_DMG 20→22`候选，完整public+calibration共5888局及分析，见`docs/PHASE_B_DAMAGE22_PLAN.md`；不改冻结原件/v15、不生成地图、不重跑基线，不自动追加候选或建阶梯。该轮已完成且失败，不采纳D22，见`reports/phase-B-damage22.md`。用户随后批准按`inbox/2026-11-08-phase-b-holdout-review.md`第六节执行：先R1/R2和条件式标准，再以现有证据做N1/N2/N3；N1任何失败项差超过1图即停。N2成立才可另存v16、仅修M指定通用规则并完整重跑两套矩阵，否则不改M；不再调游戏参数。前置满足后生成/检查全新holdout，B末前不打对局，再按BRIEF第5节继续B，无需中间审查。所有实际验收失败即停，B全部完成后仍等审查，不进C。N1/N2/N3已完成：全部实际失败仅差1图，新标准生效、v15前置通过；N2有反例，不改M、不跑v16，见`reports/phase-B-review-analysis.md`。当前下一步是全新holdout布局检查。新会话再读 `docs/PHASE_B_HANDOFF.md`（原启动快照），不重做已验收引擎。
- 框架只用 Python 标准库。所有 bot（包括示例、动物园、测试用故障 bot）及 C++ 编译必须在沙箱中执行。WSL 和 pi 本身不等于 bot 沙箱；在本开发宿主上不能裸用 plain。plain 只用于已经有外层沙箱的情况。
- 不读取、打印或迁移凭据，不读取 pi 的 `auth.json`，不把认证或个人配置写入仓库；不修改或绕过现有代理、安全设置。启动 bot 沙箱时清理继承环境，只传必要的白名单变量；只挂载所需运行环境，不挂载整个用户 HOME。
- 用户 2026-11-07 已同意构建时联网查文档和资料；对局和 bot 运行不联网，被测模型写 bot、测试和评价全程离线。框架只用标准库，后续新增开发工具仍先询问。
- 隐藏 bot、隐藏地图及涉及它们的对局只能在 `private/`；隐藏文件登记 `private/HIDDEN.sha256`。`runs/`、`.venv/` 不入库。不得绕过 pre-commit。
- 不擅改计分方式、规则机制、结算顺序、胜负条件、协议格式或验收指标。`inbox/2026-11-07.md` 的 D1–D10 已批准，I01–I11 已裁定（I11 加步行距离检查），按更新后的 DESIGN/BRIEF 实施；新歧义仍按 BRIEF 3.3 记录。
- 过程分仍是雏形，公式现在不定；结果库保留原始指标，评分局数不改。给被测模型的材料不得包含计分细节、grade 或计分代码。
- 如实保存全部对局及失败结果，不挑数据；记录CPU小时及计量边界，无法计量就标未知。用户2026-11-08取消构建token统计；正式标准预算自测仍按BRIEF 5.3执行。
- 用户2026-11-08明确：本机运行与存储，远端只上传审查所需的代码、配置、测试、文档和汇总。实际对局回放（包括公开示例）、逐局CSV/JSON、结果库、尝试/回放索引均只留本机；不得改名或拆小后上传。原始分析输出写runs，隐藏输入仍只写private。目录与归档约定见docs/REPOSITORY.md；提交前执行发布范围检查。

## 交付与停点

小步本地提交、每日更新 STATUS；今后署名 gpt-6-astra，邮箱用 GitHub noreply，不改写历史；若影响提交或推送就保留原配置并说明。推送不是自动授权。B的前置留出复核不达标就停下报告；B全部完成后按BRIEF第7节写 `reports/phase-B.md`，更新data/logs、MANIFEST及STATUS，写“等待审查”并停止；未经审查不能进入C。构建检查通过不等于阶段验收。
