# 状态

更新：2026-11-20。CA 已接受 r12 与冻结材料，并冻结 12 级名单。B 尚未验收，C 未启动；本地提交，推送由用户负责。

## 冻结裁定与下一步
- [低段重排补校准](reports/phase-B-claude-r13-repair.md)及[聚合](data/phase-b/claude-r13-repair.json)按评测提交 `233be2b` 原字节导入。新增 768 局全量核验，复用 7,440 局；第 1–4 条均通过。L2→L3 点估计为 56.96 Elo，95% 区间 29.80–88.45，与允许范围相交。通过名单已在评测侧封存。
- [第 6 条标准预算自测](reports/phase-B-standard-budget.md)及[聚合](data/standard-budget.json)按评测提交 `182cb21` 原字节导入。两个阶段各 364 局核验，最终主分 0.9187，超过 0.60。其余成员结果固定时，四个替换位置的理论最低分 0.7520，门槛所需降幅至少相当于 8 个替换位置。
- [第 5 条知情对比](reports/phase-B-ladder-awareness.md)及[聚合](data/phase-b/ladder-awareness.json)按评测提交 `65b602f` 原字节导入。两组各 364 局全量核验，主分绝对差 0.0109，通过 0.15 的主分差门槛。知情组源码只读副本已核验归档。
- [第 7 条防“一招鲜”基线](reports/phase-B-one-trick-baseline.md)及[聚合](data/phase-b/one-trick-baseline.json)按评测提交 `574c996` 原字节导入。总计 6,240 局，复用 192 局、6,048 局新回放全量核验。60 项中 3 项超过 0.10，第 7 条未通过。
- r14 公开作者任务和 dev 筛查已准备，运行窗口已开放。先取候选强度证据，再安排正式加强和第 6、7 条复查。最终 holdout 尚未启动。
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
