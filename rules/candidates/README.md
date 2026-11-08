# A阶段参数候选（未冻结）

候选JSON由 `Rules.from_dict` 校验，作为 `run_tournament(..., ruleset=...)` 的覆盖参数；其余参数不变。每局初始化PARAM和回放记录全部实际数值。当前默认及 `rules/rules.md` 仍是起点，候选不等于已采纳。

每个候选用新批次目录跑完整40图、3680局D6；保留之前版本和全部失败，不混池。授权与理由见 `inbox/2026-11-07-phase-a.md`、`rules/CHANGELOG.md`、`reports/phase-A-balance-rework.md`。

- `worker-survival-1.json`（P1）：仅WORKER_HP 40→60、WORKER_DMG 5→10。3680局已完成，平衡不通过；默认未变。
- `worker-survival-slower-mining-2.json`（P2）：接P1，仅MINE_RATE 10→5；3680局不通过，M自对弈拆基地仅5%，撤回采矿减速。
- `worker-survival-cost-3.json`（P3）：接P2，采矿恢复10、战士价升150；3680局不通过，骚扰仍无单一克制者，M自对弈拆基地12.5%。
- `worker-survival-opening-4.json`（P4）：接P3，战士价150→80、初始能量300→500；3680局不通过。
- `worker-survival-siege-5.json`（P5）：接P4，仅基地HP 1000→600；3680局仍无骚扰克制者。
- `worker-survival-economy-6.json`（P6）：接P5，仅工兵价50→40；3680局中M总体全部≥70%，但分地图与骚扰单一克制仍失败。
- `worker-survival-workers-7.json`（P7）：接P6，仅初始工兵2→4；检验基础经济差及军队成型。

以上参数批次均保持动物园v5源码、地图v2、配对与种子不变，全部源码在批次内冻结；当前public的M v7是独立策略修复，不能混作参数的效果。
