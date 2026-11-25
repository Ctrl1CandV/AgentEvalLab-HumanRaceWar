# 状态

原冻结 B 版已结案。当前由综合会话负责开发、评测和交审发布，用户负责开启所需 Claude 会话与联系审查者。[交接停点](AGENTS.md)

## 当前冻结版结案

[CA 收束审查](inbox/2026-11-21-phase-b-closure-review.md)确认本版 B 未通过。[阶段报告](reports/phase-B.md)保留第 1–8 条原判。C 未启动，calibration 和最终 holdout 继续封存，r19 未启动则暂缓，已启动则按登记存档。

[天花板实验已预登记](reports/phase-B-ceiling-preparation.md)，来自评测提交 `fcd743e`。Fable 已获启动提示，独立 astra 会话已启动。经验包和四份参照分组已核对，dev 赛程已通过零对局检查。新版 DESIGN 采用 M-balanced 的相对级距口径。

[存量重排与替换规模](reports/phase-B-roster-feasibility.md)留作已核验的收束证据。

[天花板实验阶段结果](reports/phase-B-ceiling-round-one.md)按评测提交 `264791b` 原字节导入。Fable 两份候选首轮 6,080 局全核验，主候选判部分。Fable 第二轮开场白已交用户。astra 两轮均为零候选，作者线已结束。

Fable 额度优先用于关键策略决策、实现和候选定型。综合会话负责资料准备、配对统计、统一评测及报告。Fable 第二轮补充包已放入作者收件目录，原会话可继续使用。后续如需游戏深度备忘，先由综合会话准备证据与初稿，仅把需要 Fable 专长的部分留给它。

[天花板实验最终结果](reports/phase-B-ceiling-result.md)已按评测提交 `e3e5f50` 导入。9,120 局 dev 全量核验，合规主判定为部分。Fable 第二轮墙钟超限，独立实测作为开发证据。[游戏深度备忘](reports/phase-B-ceiling-game-depth.md)给出三个新版本原型方向，随结果交审。

## 冻结版本的证据记录
- [低段重排补校准](reports/phase-B-claude-r13-repair.md)及[聚合](data/phase-b/claude-r13-repair.json)按评测提交 `233be2b` 原字节导入。新增 768 局全量核验，复用 7,440 局；第 1–4 条均通过。L2→L3 点估计为 56.96 Elo，95% 区间 29.80–88.45，与允许范围相交。通过名单已在评测侧封存。
- [第 6 条标准预算自测](reports/phase-B-standard-budget.md)及[聚合](data/standard-budget.json)按评测提交 `182cb21` 原字节导入。两个阶段各 364 局核验，最终主分 0.9187，超过 0.60。其余成员结果固定时，四个替换位置的理论最低分 0.7520，门槛所需降幅至少相当于 8 个替换位置。
- [第 5 条知情对比](reports/phase-B-ladder-awareness.md)及[聚合](data/phase-b/ladder-awareness.json)按评测提交 `65b602f` 原字节导入。两组各 364 局全量核验，主分绝对差 0.0109，通过 0.15 的主分差门槛。知情组源码只读副本已核验归档。
- [第 7 条防“一招鲜”基线](reports/phase-B-one-trick-baseline.md)及[聚合](data/phase-b/one-trick-baseline.json)按评测提交 `574c996` 原字节导入。总计 6,240 局，复用 192 局、6,048 局新回放全量核验。60 项中 3 项超过 0.10，第 7 条未通过。
- [r14 候选强度筛查](reports/phase-B-claude-r14-strength.md)及[聚合](data/phase-b/claude-r14-strength.json)按评测提交 `4c008c2` 原字节导入。两份均过标准短检查，首段 1,280 局全核验，无续测候选。作者墙钟超出既有条件，行为风格未拉开，本轮材料用于强度判断。
- [r15 候选强度筛查](reports/phase-B-claude-r15-strength.md)及[聚合](data/phase-b/claude-r15-strength.json)按评测提交 `acba1ec` 原字节导入。800 局新对局全部核验，480 局参考对照逐槽复核。两份均过短检查，合计得分均低于 r14 同风格候选，未进入续测。
- [独立 GPT 候选强度筛查及控制备选补测](reports/phase-B-gpt-ladder-strength.md)和[聚合](data/phase-b/gpt-ladder-strength.json)按评测提交 `13a2cbf` 原字节导入。综合会话主动跟踪 GPT 子进程到交付停测后接收。原两份和控制备选共 1,200 局新对局全部核验，复用同一批 480 局旧参考对照，三份均未入选续测。
- [候选败局复核与 r16 准备](reports/phase-B-strength-loss-audit.md)和[聚合](data/phase-b/strength-loss-audit.json)按评测提交 `bbd2b4c` 原字节导入。复核 1,680 局，塔分决定了大多数败局。r16 作者任务和 dev 预登记已备。第 6、7 条待验证，最终 holdout 尚未启动。
- [r16 候选强度筛查](reports/phase-B-claude-r16-strength.md)及[聚合](data/phase-b/claude-r16-strength.json)按评测提交 `d3831f7` 原字节导入。400 局新 dev 全核验，单份经济候选未达到续测条件。
- [r17 候选强度筛查](reports/phase-B-claude-r17-strength.md)及[聚合](data/phase-b/claude-r17-strength.json)按评测提交 `d062bf5` 原字节导入。作者按先导结果停止终测，独立 400 局 dev 已核验，候选未达到续测条件。
- [r18 候选筛查与同赛程复盘](reports/phase-B-claude-r18-strength.md)及[聚合](data/phase-b/claude-r18-strength.json)按评测提交 `048655c` 原字节导入。400 局新 dev 全核验，未达到续测条件。十份候选使用同赛程复盘，没有一份达到上半梯强锚筛查目标。
- [r13 校准报告](reports/phase-B-claude-r13-calibration.md)及[聚合](data/phase-b/claude-r13-calibration.json)按评测提交 `e56efc5` 原字节导入。筛查 768 局、补校准 624 局均已核验。第 2–4 条通过，第 1 条仅 L2→L3 级距未过，点估计 261.36 Elo，95% 区间 222.25–310.82，整体高于 200。当轮止于 1,392 局，原结果作为历史记录保留。
- [r13 校准预登记](reports/phase-B-claude-r13-prereg.md)及[预算](data/phase-b/claude-r13-prereg.json)按评测提交 `8b234a7` 原字节导入。预登记与模拟检查完成后已按用户的交付停测确认执行。筛查每份 192 局，合格的一对补 624 局，合计封顶 1,392 局。
- [CA 阶梯冻结审查](inbox/2026-11-20-phase-b-ladder-freeze-review.md)为当前任务依据。DESIGN 已按裁定落实 L0、L1 诊断边界、L2 起的正式强度门槛、M 锚点、K 风格披露和防“一招鲜”门槛。
- B-SCORE-001 已关闭；第 5、6 条按胜负主分数判定，过程分只作参考。本轮不改任何其他规则或门槛。
- [r12 同对手风格核对](reports/phase-B-claude-r12-m-style.md)和[聚合](data/phase-b/claude-r12-m-style.json)按评测固定提交 `464d357` 原字节导入。1,280 局全部完成并核验，无故障、超时、警告或重试。经济和控制的近期工兵数差异在独立 dev 样本中得到复核，不改变冻结名单或原联合图。
- 按用户最新安排，在当前开发 WSL 完成标准离线 jobs6 测速并冻结本机正式预算锁，不处理另一台评测机。[测速报告](reports/phase-B-claude-formal-budget.md)及[聚合](data/phase-b/claude-b-formal-budget.json)按评测固定提交 `893429f` 导入。每回合 61 ms、初始化 1210 ms、储备 1814 ms；原 dev 锁未改。
- [正式校准](reports/phase-B-claude-formal-calibration.md)与[聚合](data/phase-b/claude-b-formal-calibration.json)按固定评测提交 `aa07179` 原字节导入。112 对、5,376 局全部完成并核验；无故障、超时、警告或框架重试。不作为另一台评测机的复核。
- 上轮按点估计未过第 1–3 条。[正式校准审查](inbox/2026-11-20-phase-b-calibration-review.md)接受原数据，并依用户裁定改为 95% 地图簇区间判定；基础组公开 Z bot 作为低级一方的隔级反胜只作诊断，DESIGN 11.5 已更新。原结果保留。
- [L3 修法与区间复查](reports/phase-B-claude-calibration-l3-repair.md)和[聚合](data/phase-b/claude-b-calibration-l3-repair.json)按评测提交 `098b5b9` 原字节导入。仅补 10 对、480 局并逐局核验，无故障、超时、警告或重试。原 5,376 局全部保留参与拟合，仅在验收名单中用 b1-econ 换下 b0-econ-hi。
- **按第四节停下。** 第 2、4 条通过；L3 组内跨度降至 48.68 Elo。第 1 条仍未过：L2→L3 间距 298.20，95% 区间 259.49–351.09。第 3 条仍未过：一条正式隔级配对得分率 60.42%，区间 41.67%–77.08%。原两条告警一条为基础 Z 诊断、一条按新区间通过。
- 后续用户授权分两段试验 L3/L4 候选重排。[首段筛查](reports/phase-B-claude-b-lowband-screen.md)及[聚合](data/phase-b/claude-b-lowband-screen.json)从评测提交 `fa88c66` 原字节导入：4 对、192 局全核验，原 5,856 局全部复用。草案 L3 组内跨度 190.09 Elo，95% 区间 168.25–211.83，整体高于 80；按计划不跑剩余 384 局。
- 已测候选又做了零对局重排；114,480 种低段草案中无一同时满足级距和同级跨度。正式名单和门槛保持不变。需要新的中间档候选；独立测试、防“一招鲜”、holdout 与 C 均未启动。隐藏对阵、轨迹和原始证据仅保留于评测 worktree。

## WP-B 收尾与冻结材料（历史）
- [r12 评测](reports/phase-B-claude-wpb02.md)及[聚合 JSON](data/phase-b/claude-wpb02.json)、[冻结审查材料](reports/phase-B-claude-ladder-freeze-preparation.md)及[分组 JSON](data/phase-b/claude-ladder-freeze-preparation.json)，都按评测分支固定提交 `801dcc8` 的原字节导入。未合并分支；原件、原始回放、隔级逐边诊断和异常收据留评测 worktree。
- 四份 r12 均通过短检查；3,840 个新对局全部完结，用时 5 分 36 秒，无故障、超时、警告或重试。包装层退出码收据异常保留，用户授权后凭标准完成单、冻结任务和全部回放核验继续；没有补打或重跑。四个点估计均高于目标窗口，已反馈作者；全部留在联合图。
- 联合开发图为 35 节点、126 条实测边、40,320 个唯一局，复用 36,480 局。三份 12 级草案均未过全套门槛：推荐草案 L1→L2 相差 234.0 Elo；保留原拟 L1 三成员则跨度 138.5 Elo，且该草案有一条隔级边达到 49.7%。L0 及低端缺口交 CA 和用户裁定。
- r11 同对手风格已从 3,200 份原有回放独立重算；r12 只有作者对 M-balanced 的公开自测摘要，不与 dev 合并，是否需要已有回放独立复算留给 CA。

## WP-B 收尾时的停点（历史）
- 不再开作者轮次。冻结材料未新增对局，不修改规则、协议、计分或验收门槛。T6 未用于 WP-B，正式校准是否采用待审；不启动正式校准、独立测试、holdout 或 C。
- [本轮 CA 裁定](inbox/2026-11-18-phase-b-wpb01-review.md)已接受 WP-A2 和 r11，并更新了 r11 旧窗口的缺口判断。[上一轮公开汇总](reports/phase-B-wpa2-wpb01-integration.md)及其聚合（评测固定提交 `9f3f204`）保持原样；其中“r12 未启动”仅为历史。
