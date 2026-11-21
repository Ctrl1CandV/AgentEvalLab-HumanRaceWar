# 审查报告

当前停点见 [STATUS](../STATUS.md)。执行权限以用户最新指令和有效裁定为准；[综合会话交接](../docs/CLAUDE_EVALUATION_HANDOFF.md)说明两个 worktree 的写入边界。

## 11-20 CA 冻结裁定后的结果

- [r17 候选强度筛查](phase-B-claude-r17-strength.md)及[聚合](../data/phase-b/claude-r17-strength.json)来自评测提交 `d062bf5`，400 局新 dev 全核验，未安排续测。
- [r16 候选强度筛查](phase-B-claude-r16-strength.md)及[聚合](../data/phase-b/claude-r16-strength.json)来自评测提交 `d3831f7`，400 局新 dev 全核验，未安排续测。
- [候选败局复核与 r16 准备](phase-B-strength-loss-audit.md)及[聚合](../data/phase-b/strength-loss-audit.json)来自评测提交 `bbd2b4c`，复核 1,680 局，r16 dev 已预登记。
- [独立 GPT 候选强度筛查](phase-B-gpt-ladder-strength.md)及[聚合](../data/phase-b/gpt-ladder-strength.json)来自评测提交 `13a2cbf`，原两份和控制备选共 1,200 局全核验，均未获续测资格。
- [r15 候选强度筛查](phase-B-claude-r15-strength.md)及[聚合](../data/phase-b/claude-r15-strength.json)来自评测提交 `acba1ec`，800 局新对局和 480 局参考对照，两份均未获续测资格。
- [r14 候选强度筛查](phase-B-claude-r14-strength.md)及[聚合](../data/phase-b/claude-r14-strength.json)来自评测提交 `4c008c2`，首段 1,280 局核验，两份均无续测资格。
- [第 7 条防“一招鲜”基线](phase-B-one-trick-baseline.md)及[聚合](../data/phase-b/one-trick-baseline.json)来自评测提交 `574c996`，6,240 局中 60 项判定有 3 项超出门槛。
- [第 5 条知情对比](phase-B-ladder-awareness.md)及[聚合](../data/phase-b/ladder-awareness.json)来自评测提交 `65b602f`，两组各 364 局核验，主分差门槛通过。
- [第 6 条标准预算自测](phase-B-standard-budget.md)及[聚合](../data/standard-budget.json)来自评测提交 `182cb21`，两阶段各 364 局核验，最终主分超过 0.60。
- [低段重排补校准](phase-B-claude-r13-repair.md)及[聚合](../data/phase-b/claude-r13-repair.json)来自评测提交 `233be2b`：新增 768 局全核验，第 1–4 条均通过。
- [r13 校准报告](phase-B-claude-r13-calibration.md)及[聚合](../data/phase-b/claude-r13-calibration.json)来自评测提交 `e56efc5`：1,392 局全量核验，第 2–4 条通过，L2→L3 级距仍未过。
- [r13 校准预登记](phase-B-claude-r13-prereg.md)及[预算](../data/phase-b/claude-r13-prereg.json)来自评测提交 `8b234a7`，记录两段校准的事前筛查规则和预算。
- [低段候选首段筛查](phase-B-claude-b-lowband-screen.md)及[聚合](../data/phase-b/claude-b-lowband-screen.json)来自评测提交 `fa88c66`：192 局核验，L3 组内跨度不通过，余下 384 局未运行。
- [L3 修法与区间复查](phase-B-claude-calibration-l3-repair.md)及[聚合](../data/phase-b/claude-b-calibration-l3-repair.json)来自评测提交 `098b5b9`：新增 480 局已核验复用旧图，第 1、3 条仍未通过，停在校准。
- [正式校准](phase-B-claude-formal-calibration.md)和[聚合](../data/phase-b/claude-b-formal-calibration.json)来自评测提交 `aa07179`：前 4 条验收中，级距、同级跨度和隔级反胜未通过，已停止后续测试。
- [B 正式预算锁](phase-B-claude-formal-budget.md)和[聚合](../data/phase-b/claude-b-formal-budget.json)来自评测提交 `893429f`：开发 WSL 标准测速与新固定锁。
- [CA 冻结审查](../inbox/2026-11-20-phase-b-ladder-freeze-review.md)：12 级名单冻结、B 剩余任务和停点。
- [r12 同对手风格核对](phase-B-claude-r12-m-style.md)及[聚合](../data/phase-b/claude-r12-m-style.json)，按评测提交 `464d357` 原字节导入。只补独立风格数据，不改变冻结名单。

## WP-B 收尾与原阶梯冻结材料（历史）

- [r12 评测](phase-B-claude-wpb02.md)及[聚合 JSON](../data/phase-b/claude-wpb02.json)：最后一轮完成，四份候选均保留于图中。与冻结材料一起按评测分支 `801dcc8` 原字节导入。
- [阶梯冻结审查材料](phase-B-claude-ladder-freeze-preparation.md)及[分组 JSON](../data/phase-b/claude-ladder-freeze-preparation.json)：方案未过全部门槛，等 CA 审查，不是正式冻结。

## WP-A2 与 r11 阶段性结果（历史）

[汇总报告](phase-B-wpa2-wpb01-integration.md)和[详细 JSON](../data/phase-b/wpa2-wpb01-integration.json)对应评测分支 `9f3f204`。旧窗口的暂选和缺口只是当时结果，后续重组由本轮 CA 裁定更新。

- WP-A2：[风格分析及早期停点](phase-B-claude-wpa2-checkpoint.md)、[修订联合图](phase-B-claude-wpa2-revised.md)。
- WP-B：[r11 接收记录（历史）](phase-B-claude-r11-intake.md)、[第一轮评测结果](phase-B-claude-wpb01.md)。

## 2026-11-18 审查落实（导入前记录）

[落实报告](phase-B-wpa-review-followup.md)和[对应 JSON](../data/phase-b/wpa-review-followup.json)记录阶梯公开范围和当时的状态更正。T6 小修与 WP-A 获接受；其中“暂无新结果”只描述当时的 `c47c435`，以本页上方的最新结果为准。

## 第二次审查后的实施汇总（历史）

[实施汇总](phase-B-second-review-implementation.md)及[对应 JSON](../data/phase-b/second-review-implementation.json)记录 T6 小修和 WP-A 三项公开成果的精确集成。其中 WP-B 完成的说法已在本次审查落实报告中更正，不作为当前进度。

- [`phase-B-claude-joint-dev01.md`](phase-B-claude-joint-dev01.md)：WP-A联合图、暂定组装和补候选前缺口；[聚合](../data/phase-b/claude-joint-dev01.json)与[口径说明](../docs/CLAUDE_DEV_ASSEMBLY_SCOPE.md)同步导入。
- [`phase-B-t6-small-fixes-20261116.md`](phase-B-t6-small-fixes-20261116.md)：精确计数、三项异机跳过与当时的同步检查点；细节见对应JSON，历史原字节不改。
- [统一报告口径](../docs/PHASE_B_REPORTING.md)：新报告简述结果、一张表；方法、负例和用量放JSON，不重写旧冻结报告。

## 第二次综合审查原提交集（已接受，非B验收）

- [`phase-B-second-review-request.md`](phase-B-second-review-request.md)：本次总入口。GPT完成工作+Claude固定r01–r09，不再等继续开发；请远端安排整体组装/缺口与后续验收，不是B通过。
- [`phase-B-claude-author-batch-handoff.md`](phase-B-claude-author-batch-handoff.md)：claude-evaluation固定提交1da0e91，三强主线/六原型、全部负例及剩余B工作；配套[`收束聚合`](../data/phase-b/claude-author-batch-closure.json)。
- [`phase-B-public-tools-t6-acceptance02.md`](phase-B-public-tools-t6-acceptance02.md)：T6交付02本地代码复核及单次公开非计分实机验收通过；启动量未知和清理/并发边界单列，不自动授计分资格。
- Claude原轮：[`r01`](phase-B-claude-r01.md)、[`r02`](phase-B-claude-r02.md)、[`r03收包问题`](phase-B-claude-r03-intake.md)、[`r03结果`](phase-B-claude-r03.md)、[`r04`](phase-B-claude-r04.md)、[`graph01`](phase-B-claude-graph01.md)、[`r05`](phase-B-claude-r05.md)、[`r06`](phase-B-claude-r06.md)、[`r07`](phase-B-claude-r07.md)、[`r08`](phase-B-claude-r08.md)、[`r09零交付`](phase-B-claude-r09.md)，各有对应data/phase-b聚合；历史图、无穷抽样和未选方案不丢弃。
- Claude历史说明：[`会话连续性`](phase-B-claude-author-continuity.md)、[`进攻里程碑原请求`](phase-B-claude-milestone-review-request.md)、[`中间裁定`](phase-B-claude-milestone-review.md)。原文按固定提交保留，不当当前继续r10的授权。

## 历史工作与检查点

- [`phase-B-public-tools-t6-02-review-request.md`](phase-B-public-tools-t6-02-review-request.md)：第二稿执行前复核请求，历史“未获准实机”状态已由上列单次验收结果更新；原请求不改。
- [`phase-B-public-tools-t6-02.md`](phase-B-public-tools-t6-02.md)：第二稿修复/测试/预算的执行前报告；可信夹具不当bot残留证据，当时真实运行0，后续实际验收另列。

- [`phase-B-public-tools-t6-01-review-request.md`](phase-B-public-tools-t6-01-review-request.md)：T6交付01独立CA审查入口；源码仍45fb7ed，4项真实CLI/标准零任务规划补证通过，未开二稿、真实运行0。先审查，不能直接当作验收通过。

- [`phase-B-public-tools-t6-01.md`](phase-B-public-tools-t6-01.md)：默认关闭的公共实验/profile工具、纯契约检查及用户验收脚本首稿；实机运行0，CA/用户验收待，不得计分。另登记独立对接会话交接，不代开或传源码。

- [`phase-B-workspace-retirement.md`](phase-B-workspace-retirement.md)：用户后续授权在79135份文件完整保全、两次核字节后删除旧DeepSeek/pilot目录；私有档案及D-c01保留，Claude未动、零运行。

- [`phase-B-claude-workspace.md`](phase-B-claude-workspace.md)：T4公开工作区及两份自测预算投影就绪，私有评测协议已登记，零运行；用户启动Claude，GPT停报等待交付通知。

- [`phase-B-gpt-mainlines-final.md`](phase-B-gpt-mainlines-final.md)：T3完成2080局，直接半分174<176而不采纳E100%；零故障/超时/重试，全部回放各验证一次，GPT三线冻结。

- [`phase-B-new-division-preparation.md`](phase-B-new-division-preparation.md)：T1按字节关闭DeepSeek、T2最后一次全量登记及逐轮归档切换；旧状态原样归入docs/history，零运行。

- [`phase-B-author-r04-runtime-wiring02.md`](phase-B-author-r04-runtime-wiring02.md)：108文件只读审查仍有4组工程＋1组记录/写入范围阻塞，不是只差实机测试；E仅核156项摘要、零新增执行。共享收束后继续冻结，无新任务或下一窗口。

- [`phase-B-author-r04-controller-repair01.md`](phase-B-author-r04-controller-repair01.md)：102文件审查聚合，仍4组工程阻塞；E只核130项摘要，新增执行0。wiring02已交付停止但未收审，共享收束/本地提交后才另发只读接收窗口，无运行授权。

- [`phase-B-astra-strength01.md`](phase-B-astra-strength01.md)：10% TURN CPU9.6049ms>6ms技术止损，456新局/912启动/11编译、456回放一次验证通过；余下1864不执行，矩阵不全不作强度结论，不采纳。
- [`phase-B-astra-strength01-readiness-fix.md`](phase-B-astra-strength01-readiness-fix.md)：真实启动前守卫因公开/私有清单混用拒绝；零执行，原冻结/失败保留。修复后25新＋10既有纯检查双seed，新freeze02不改源码/额度。
- [`phase-B-astra-strength01-preflight.md`](phase-B-astra-strength01-preflight.md)：已批2320局的实际日程/121文件冻结、零重试/失败停发控制器及分析器；22新＋10既有纯检查双seed、5文件LSP0，执行前置不等于强度结果。
- [`phase-B-author-r04-engineering-repair.md`](phase-B-author-r04-engineering-repair.md)：既有52文件工程包审查仍阻塞，E仅核聚合/89项摘要；新纯工程包尚未接收。共享收束后优先继续已批准2320局，到E下一合适停点再释放新接收。
- [`phase-B-astra-strength01-preparation.md`](phase-B-astra-strength01-preparation.md)：资格02通过后的下一轮准备；480旧局来源/回放摘要/头及旧审计凭据、92冻结文件/四入口匹配，10纯检查双seed。新提案2320 public-only，通过也停；该准备批零新增执行；随后用户已明确批准具体范围，执行器/冻结仍须完成。
- [`phase-B-astra-qualification02.md`](phase-B-astra-qualification02.md)：用户新批准的单次资格02已完整通过P0后停止；实际1快照/6编译/126启动/4074项含8参考步/1check/0计分，停后只读审计通过。只证明资格，不证明强度，不继承旧4400余量。
- [`phase-B-astra-compute-trial01-postmortem.md`](phase-B-astra-compute-trial01-postmortem.md)：E停后只读复盘与新的一次P0资格提案；12份旧原件核对、5纯检查双seed、零新bot/引擎步，原失败不变；当时待批准的新资格02已于2026-11-12明确获批，进度另列。
- [`phase-B-author-r04-ready-package.md`](phase-B-author-r04-ready-package.md)：原协调会话的工程准备包审查聚合，仍不可运行；下一项仅用户转交的120分钟工程修订、最多78参考步，零编译/bot/check/新局。E不读实现、不下发任务。

- [`phase-B-astra-compute-trial01-p0.md`](phase-B-astra-compute-trial01-p0.md)：两稿P0失败，本轮停止。首稿预算门失败，唯一修订通过四档压力但未过原功能门；总2快照/12编译/140启动/6282项/0check/0新局，禁止第三稿或P1/P2。

- [`phase-B-author-r04-plan-v2.md`](phase-B-author-r04-plan-v2.md)：原协调会话接收10文件，计划仍不可执行；下一项为用户转交的120分钟工程准备，零编译/bot/check/新局。E仅核聚合receipt与前像，不读取作者实现。

- [`phase-B-astra-compute-trial01-preflight.md`](phase-B-astra-compute-trial01-preflight.md)：交接已本地收束；E的具体输入、计数器/运行器及freeze01已备，8项纯检查双seed通过。首次全量登记被active守卫拒绝，后来取得冻结窗口并完成637295文件登记/全摘要核验；本登记检查点零编译/bot/新局，下一步实际P0，不重批授权。

- [`phase-B-author-r04-plan.md`](phase-B-author-r04-plan.md)：r04计划6文件接收及只读审查，契约仍需修订；下一任务只有界计划/旧证据定位，未授权候选或80局。用户拆分会话，新GPT接续已获批E试验；新E会话已统一收束交接资产登记与本地提交，汇总见`../data/phase-b/e-handoff-integration.json`。
- [`phase-B-author-r03-reconciliation.md`](phase-B-author-r03-reconciliation.md)：9文件补正接收，启动/回复/源码账与旧审计一致，原功能失败及快照超限不变，补正已收束。

- [`phase-B-author-r03.md`](phase-B-author-r03.md)：作者功能失败、零计分；300文件原样接收、34份轨迹重步。启动/回复未超限，但策略快照超限、汇总与判据需补正；当时下一任务仅零运行账本/结论补正，现已收束；保留r01，后续见上列最新报告。

- [`phase-B-next-preparation.md`](phase-B-next-preparation.md)：此前7份作者补正/前置材料归档及有限修复转交时点；astra完成剩余路线、静态规格和18项双hashseed纯检查，零bot/新局。该准备时点4400局试验尚待批准；用户后来已明确批准一次，最新进度见STATUS。

- [`phase-B-astra-stop-review.md`](phase-B-astra-stop-review.md)：astra三轮止损后的只读复盘；重计旧6720public结果，提出一条主线的条件式算力试验，最大4400新局只是待批准额度。该复盘批零bot/新局；后续用户只解除一次E有限试验的止损限制，不抹去原失败。

- [`phase-B-author-r02.md`](phase-B-author-r02.md)：作者160局筛选阴性停止，未交付新版本；原样归档及完整回放核验，原诊断解释需修正；这是当时停点；随后补正和前置定位归档、有限修复任务转交见最新准备记录，不自动扩大评测。

- [`phase-B-mainlines-dev05.md`](phase-B-mainlines-dev05.md)：恢复后完成6720public＋80dev，训练收益未通过首段直接对照（37.5%<45%），不采纳；连续三轮止损，保留dev02等用户审查/指示，不追加候选、不推送。

- [`phase-B-author-D-c01.md`](phase-B-author-D-c01.md)：首份作者交付原样接收，旧2616局记录普查有流程缺项；统一1280局356/0/924且全核验，仅保留同作者首版基线，强主线目标未达。随后补齐198份旧记录，合计2814（含6份历史调试故障），纠正作者角色误归；该报告记录当时r02尚在计划阶段；后续执行与阴性停止见上列r02报告，不推送。

- [`phase-B-mainlines-dev05-checkpoint.md`](phase-B-mainlines-dev05-checkpoint.md)：dev05完成1440局public及默认逐回合等价核验，第4批在启动前因共享CPU资源暂停；这是当时搜索/取舍未完成的历史快照，资源暂停本身不算拒绝；后续完整结果与第三轮止损见dev05报告。

- [`phase-B-mid-review-step0.md`](phase-B-mid-review-step0.md)：中期审查第0步完成；M1、L1–L6、dev80、两公开工作区及dev05计划就绪，无新对局，先报告目录并停下，不推送。不是B验收。

- [`phase-B-mid-review-request.md`](phase-B-mid-review-request.md)：用户2026-11-09要求的中期审查入口、重点和远端验证边界；不是B阶段验收。

- [`phase-A.md`](phase-A.md)：A阶段交付及逐项检查结果；已获2026-11-08审查通过。
- [`phase-B-mainlines-dev04.md`](phase-B-mainlines-dev04.md)：144局被动诊断、105项最终合成检查和新1872局；反例修复未转化为强度提升，不采纳，仍保留dev02。
- [`phase-B-mainlines-dev03.md`](phase-B-mainlines-dev03.md)：算法候选1872局及96项合成检查；结束方式改善但强度未提高，不采纳，保留dev02继续开发。
- [`phase-B-mainlines-dev02.md`](phase-B-mainlines-dev02.md)：修订版1872局、固定预算配对及57项合成检查；有改善但尚需算法增强，继续开发，不是交审停点。
- [`phase-B-mainlines-dev01.md`](phase-B-mainlines-dev01.md)：L0决定后的第一批三主线原型开发，1728局完整验证，原型仍需增强，非正式阶梯验收或B完成报告。
- [`phase-B-ladder-preflight.md`](phase-B-ladder-preflight.md)：新holdout24图布局及代表性汇总、原L0构成问题B-L0-001停点（已关闭，见[`L0决定`](../docs/PHASE_B_L0_DECISION.md)）；不把两bot诊断当完整阶梯校准，也不是B完成报告。
- [`phase-B-review-analysis.md`](phase-B-review-analysis.md)：第二份审查N1/N2/N3；N1满足条件，新标准生效、v15前置通过；N2有反例，不改M；N3显示分类型克制。不是B完成报告。
- [`phase-B-damage22.md`](phase-B-damage22.md)：获准的一轮D22共5888局失败报告，包含完整配对比较、回放诊断和处理决定；拒绝决定已获第二份审查认可，原证据保留。
- [`phase-B-holdout.md`](phase-B-holdout.md)：首次B前置留出失败停点，2208局/回放全部完成，但指定第1、2项未达到；原结论保留，没有阶梯或B完成报告。
- [`phase-A-balance-rework.md`](phase-A-balance-rework.md)：二审后的诊断、参数与策略试验过程，包含失败版本。
- [`archive/2026-11-07-phase-A-review-request.md`](archive/2026-11-07-phase-A-review-request.md)：此前资源、效率和平衡的历史审查请求，不作为当前阻塞清单。

数据入口在`data/`，原始对局与完整日志留本机。目录与历史限制见`docs/REPOSITORY.md`；B未完成，C不启动。当前任务与停点只见STATUS及新分工，不从历史报告推定许可。
