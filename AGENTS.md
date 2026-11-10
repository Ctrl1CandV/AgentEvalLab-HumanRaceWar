# HumanRaceWar 构建者说明

本仓库的后续搭建和开发在 WSL Ubuntu 22.04 内进行，工作目录为 `~/projects/AgentEvalLab-HumanRaceWar`。Windows 原目录仅保留迁移前备份，不在两边同时开发。后续提交、推送和拉取都在这个 WSL 仓库执行，Windows 备份不再参与同步。

## 每次开工

1. 先看 `inbox/` 是否有新审查文件，再完整阅读 `docs/DESIGN.md`、`docs/BRIEF.md`、`STATUS.md`。
2. 首次接手补读 `docs/WSL_HANDOFF.md`、`docs/IMPLEMENTATION_NOTES.md`、`tests/COVERAGE.md`。
3. 检查 `git status --short --branch`，保留用户改动；确认 `git config --get core.hooksPath` 为 `.githooks`。
4. 使用 `.venv/bin/python` 或 `python3.13`；不要把 `/usr/bin/python3` 的 3.10 当作项目解释器。测试入口：`.venv/bin/python tools/run_tests.py`。

## 实施边界

- **当前优先：2026-11-09中期审查** `inbox/2026-11-09-phase-b-mid-review.md`及用户本次指令已批准D1–D3。不打新对局的第0步已完成：M1机器绑定、L1–L6既有档案聚合、80张dev图、干净公开材料/DeepSeek工作区、AUTHORS和dev05事前计划，见`reports/phase-B-mid-review-step0.md`。第0步已按约报告两目录并停止；用户随后要求继续astra任务，dev05已执行1440局并完整验证，第4批启动前因共享CPU锁占用停止，见`reports/phase-B-mainlines-dev05-checkpoint.md`。用户随后通知DeepSeek首轮完成并要求检查/交代后续/继续astra，已完成D-c01评测并另存恢复登记：dev05复用原1440局、追加5360，共6720public＋80dev；首段对E-r02仅37.5%<45%，实际未采纳，连续三轮止损已触发。现在保留dev02、等待用户审查/指示，不追加dev06、不改门槛/参数/地图；见reports/phase-B-mainlines-dev05.md。旧资源错误/驱动/计划/日志/完成字节不变，不把原资源停点本身计为拒绝。不代开试探/DeepSeek。两目录为`~/projects/HRW-pilot/`、`~/projects/HRW-deepseek/`；astra没有代开其会话；首份交付D-c01已原字节归档，源码不改，check及1280局dev完成并全核验：356/0/924，仅保留为其首版比较基线，不替C-r02；自测补充核到2814份旧记录（作者2787、公开参考27，含6份历史调试故障，其中4份0回合），误归已反馈；原开发模型/会话独立性未证实。作者已补交只读r02计划，仍需澄清顺序/预算/抽样，等用户执行通知，不因资源空闲自动开局。今后public调参，dev取舍/临时BT，calibration仅正式校准，holdout/grading用途不变。dev05的E-r02参数化+有限CPU坐标搜索已走完，默认等价/最终功能/全回放核验通过但首段取舍失败；原public6720/dev2080上限未扩大，后段不执行，执行状态以STATUS为准；原40/80图两段式门槛不改，固定池采用逐本线未饱和的`fixed-pools-v2.json`（旧并集草案保留，不能再用）。保守计入dev03/dev04，现dev05亦未采纳，已按三轮停报；DeepSeek独立控制，用户启动/转交，astra不改其代码。用户试探bot不读源码、不作调参对手。仅本地提交，**不推送，由用户推送**；逐条处理和当前进度见STATUS，分工见`docs/AUTHORS.md`。
- M1补绑定后，同机后续开发使用`private/phase-b/mid-review-step0/timing-lock-machine-bound.json`（schema2）。原dev01锁、benchmark原字节、60/1200/1800ms及其他预算均保留，不重测；原锁缺总逻辑核数，以绑定该锁的既有dev01记录补证并另存封装，不声称原来已有机器绑定。换机器必须重新测量/冻结，不能使用旧CPU编号规避；正式评分D4不变。
- 以下为中期审查前沿革，不覆盖上面的新用途、停点和推送边界：A已通过，用户2026-11-08授权进入B。以STATUS和 `inbox/2026-11-08-phase-a-accepted.md` 为准：standard-1与动物园v15冻结；先生成隐藏地图并做24张calibration上的留出复核，未通过就停下报告，不建阶梯、不自行改参数或重抽地图。首次2208局留出已失败，见 `reports/phase-B-holdout.md`。用户随后授权仅一轮`SOLDIER_DMG 20→22`候选，完整public+calibration共5888局及分析，见`docs/PHASE_B_DAMAGE22_PLAN.md`；不改冻结原件/v15、不生成地图、不重跑基线，不自动追加候选或建阶梯。该轮已完成且失败，不采纳D22，见`reports/phase-B-damage22.md`。用户随后批准按`inbox/2026-11-08-phase-b-holdout-review.md`第六节执行：先R1/R2和条件式标准，再以现有证据做N1/N2/N3；N1任何失败项差超过1图即停。N2成立才可另存v16、仅修M指定通用规则并完整重跑两套矩阵，否则不改M；不再调游戏参数。前置满足后生成/检查全新holdout，B末前不打对局，再按BRIEF第5节继续B，无需中间审查。所有实际验收失败即停，B全部完成后仍等审查，不进C。N1/N2/N3已完成：全部实际失败仅差1图，新标准生效、v15前置通过；N2有反例，不改M、不跑v16，见`reports/phase-B-review-analysis.md`。全新holdout24图已在`private/holdout-maps/`冻结并通过布局/独立检查，尚无对局。B-L0-001已于2026-11-09获用户澄清并验证：原128局均到300回合，miner全部胜局靠零塔分后的卸货判胜，random胜局靠塔分；保留原版两bot作为异质L0基础组，不以内部胜率/Elo强求等强。该解释仅限L0，L1+80Elo及其他指标不变，见`docs/PHASE_B_L0_DECISION.md`。已继续B：三条私有主线完成dev01的1728局及dev02–dev04各1872局，累计7344局，全部回放/身份/限额核查通过，零运行故障/警告。dev02有改善；dev03/dev04均未采纳，仍以dev02为开发基线。dev04先完成144局被动诊断及105项最终合成检查，完整比较仍未提升强度；所有版本、初稿失败及负结果保留。尚非正式阶梯验收，见`reports/phase-B-mainlines-dev04.md`。用户随后于2026-11-09要求将当前检查点提交推送供Claude中期审查；本次暂不追加候选，等这轮反馈，入口`reports/phase-B-mid-review-request.md`。这是主动中期检查，不是B完成或正式验收失败停点，既有B开发授权保留。继续BRIEF5.1时下一版先记有限计划，所有后续配对/校准复用`private/phase-b/ladder-dev01/batch/timing-lock.json`（60/1200/1800ms，系数0.5998025747312362），不再测速。旧`reports/phase-B-ladder-preflight.md`为历史停点，不再阻塞，也不重做已完成前置。新会话再读 `docs/PHASE_B_HANDOFF.md`（原启动快照），不重做已验收引擎。
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
