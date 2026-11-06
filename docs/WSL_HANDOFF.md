# WSL 开发环境与 Agent 交接

更新：2026-11-07。本次是开发工作区迁移，不是 C 阶段向评测机器交付，也不表示 A 阶段验收完成。

## 1. 主工作区与启动方式

后续只在 WSL 的 `~/projects/AgentEvalLab-HumanRaceWar` 开发。Windows 原目录保留迁移前备份，不删除、不双向自动同步，不在两边同时修改。

在 WSL 终端运行：

```bash
hrw-dev
```

启动器位于 `~/.local/bin/hrw-dev`。它通过现有登录 shell 加载用户环境，进入项目、激活 `.venv`，再启动 pi；没有重写代理、DNS 或安全配置。

也可从 Windows PowerShell 启动：

```powershell
wsl -d Ubuntu-22.04 --exec bash -lc 'exec ~/.local/bin/hrw-dev'
```

手动启动的等价步骤：

```bash
cd ~/projects/AgentEvalLab-HumanRaceWar
source .venv/bin/activate
pi
```

继续此目录上次会话用 `hrw-dev --continue`。Windows 上的会话历史和认证文件没有复制过来。

### 第一次启动需要用户做的事

1. 查看并决定是否信任当前项目。项目 `.pi/settings.json` 只指定 `/bin/bash`，两个 `.pi/prompts/` 文件只是文字模板；没有项目扩展或 MCP 配置。默认仍为询问信任，没有自动批准。
2. 在 pi 中运行 `/login`，按提示登录你使用的订阅或 API 渠道，再通过 `/model` 选择模型。如果登录页面未自动打开，在 Windows 浏览器中打开 pi 提供的链接，按提示完成。
3. 不要把令牌、授权回调、API key 或 `auth.json` 贴进 Agent 对话、交接文件或仓库。
4. 本次只验证了 pi 的版本、帮助命令及启动器，没有测试模型认证和推理请求。不要把“CLI 已就绪”理解为“模型账号已验证”。

Git 的原有 HTTPS 远端、提交身份和分支跟踪关系已在仓库本地恢复；没有复制 Windows 的 Git 凭据或 credential helper。当前可以本地提交，日后推送认证由用户按需完成；本次没有推送。

## 2. 已安装与已验证

| 项目 | 当前状态 |
|---|---|
| Linux | WSL2 Ubuntu 22.04.5，项目位于原生 ext4 文件系统 |
| Python | CPython 3.13.15，通过已有 uv 0.13.4 用户级安装 |
| 项目解释器 | `.venv/bin/python`，3.13.15；使用 `venv --without-pip` 创建，框架无第三方 Python 依赖 |
| 系统 Python | `/usr/bin/python3` 仍为 3.10.12，没有替换 |
| C++ | GCC / g++ 11.4.0 |
| 沙箱 | bubblewrap 0.6.1 |
| Node / npm | 22.23.3 / 10.9.9，沿用已有安装 |
| pi | `@earendil-works/pi-coding-agent@1.4.0`，用户级 npm 前缀 `~/.local`，安装使用 `--ignore-scripts` |
| 其他工具 | Git 2.34.1、ripgrep 13.0.0、Bash、make 已有 |

Python 运行环境在 `~/.local/share/uv/python/cpython-3.13.15-linux-x86_64-gnu`。以后实现 bwrap 启动器时，只读挂载这个 Python 运行目录，不要为了运行 Python 而挂载整个用户 HOME；里面有 pi 配置、会话和认证文件。

验证结果：

- 86 项引擎测试在 Python 3.13.15 下、两个不同 `PYTHONHASHSEED` 进程里分别通过；另归档 9 项确定性和 17 项协议测试。见 `data/python313-tests.json` 与 `logs/python313-*.log`。
- bwrap 内可运行该 Python 的标准库、读取自身 Linux 进程 CPU 时钟；可信 C++20 小程序在 bwrap 内编译和运行成功。Agent HOME 和项目没有挂载到这两个探针中。
- 上述只是环境探针，不是 bot 运行器。资源限额、跨命名空间进程树计时、bot 崩溃/洪泛/超时和完整回放仍未验收。
- 机器配置和工具状态见 `data/environment-wsl-python313.json`；迁移与安装摘要见 `data/wsl-setup.json`、`logs/wsl-setup.log`。速度系数尚未标定。
- 迁移基线为 `d2f60c2`：4 个原有 Git 提交、42 个受版本管理文件以及 1 个本地测试历史文件已核对。使用本地 Git bundle 迁移，没有从远端重新下载仓库。后续交接提交在 WSL 主工作区产生。

复查命令：

```bash
cd ~/projects/AgentEvalLab-HumanRaceWar
.venv/bin/python tools/check_environment.py
PYTHONHASHSEED=0 .venv/bin/python tools/run_tests.py
PYTHONHASHSEED=1 .venv/bin/python tools/run_tests.py
git config --get core.hooksPath  # 应为 .githooks
git status --short --branch
```

`.venv/`、`runs/` 不入库。Python 3.10 时期的数据和日志保留为历史，不冒充 3.13 验证。Windows 专用的 `tools/test_in_wsl.py` 仍保留，但不再是主工作区的测试入口。

## 3. 交给执行 Agent 的提示词

项目已有 `AGENTS.md`，会提醒每次开工的必读顺序、安全约束和停点。信任项目后，可直接使用下面两个 pi 命令；若刚添加模板，可先 `/reload`。

### 首次接手或继续 A 阶段：`/resume-phase-a`

完整模板在 `.pi/prompts/resume-phase-a.md`。也可以复制下面这段：

> 你是 HumanRaceWar 仓库的构建者。后续只在当前 WSL 主工作区开发。先看 inbox/ 新文件，再完整阅读 docs/DESIGN.md、docs/BRIEF.md、STATUS.md；首次接手还要读 docs/WSL_HANDOFF.md、docs/IMPLEMENTATION_NOTES.md 和 tests/COVERAGE.md。核实 Git 状态和钩子，运行 .venv/bin/python tools/run_tests.py。当前仍是 A 阶段：引擎初版已实现，86 项测试已在 Python 3.13.15 通过，但尚无 bot 对局、运行器、SDK、地图集或正式回放。近期先完成运行器、SDK/示例、match 和 replay verify，打通一局，再按任务书推进。所有 bot 和编译必须在沙箱内运行，WSL 本身不是 bot 沙箱。不得读取凭据、绕过安全设置、擅自改规则/协议/计分/验收标准或引入第三方 Python 依赖。保留全部结果、如实记录用量；小步本地提交并更新 STATUS。A 阶段结束后写报告、更新数据和 MANIFEST，然后停下等审查，不自行进入 B 阶段。

### 收到审查意见后：`/process-review`

完整模板在 `.pi/prompts/process-review.md`。也可以复制下面这段：

> 先检查 inbox/ 新审查文件，再完整阅读 DESIGN、BRIEF 和 STATUS，并核实当前 Git 状态。逐条处理“必须改、建议改、问题”，在 STATUS 回复表里记录处理方式、文件、测试证据和未解决项，保留原审查文件。只在 WSL 主工作区开发，使用 .venv/bin/python；保持所有安全与审批边界，不把建议自动当成批准。完成后重跑相关测试，更新数据和报告，做小步本地提交。未明确获准进入下一阶段时保持停点，报告后停止。

## 4. 接手时不要误判的事情

- 环境已就绪，但游戏框架只做到引擎初版。不能因为测试绿了就写“A 阶段完成”。
- STATUS 的 I01–I08 是待确认解释，不是已经批准的设计变更。没有调参，没有冻结过程分。
- WSL 不是 bot 沙箱，pi 的项目信任也不是权限隔离。当前开发宿主不能直接用 plain 裸跑 bot。
- 没有安装 Windows 端的额外扩展或技能，也没有迁移跨会话记忆；基础 pi 提供 read/bash/edit/write，其他能力不能假定存在。
- 本次授权是安装 Python、pi 和迁移环境，不是对后续工具安装、下载、推送或规则修改的无限授权。
- `docs/BRIEF.md` 中的阶段停点仍然有效。B 阶段自测尤其需要全新的干净目录和会话，不能用此构建者工作区替代。
