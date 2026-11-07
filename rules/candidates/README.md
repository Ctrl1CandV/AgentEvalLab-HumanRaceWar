# A阶段参数候选（未冻结）

候选JSON由 `Rules.from_dict` 校验，作为 `run_tournament(..., ruleset=...)` 的覆盖参数；其余参数不变。每局初始化PARAM和回放记录全部实际数值。当前默认及 `rules/rules.md` 仍是起点，候选不等于已采纳。

每个候选用新批次目录跑完整40图、3680局D6；保留之前版本和全部失败，不混池。授权与理由见 `inbox/2026-11-07-phase-a.md`、`rules/CHANGELOG.md`、`reports/phase-A-balance-rework.md`。

- `worker-survival-1.json`（P1）：仅WORKER_HP 40→60、WORKER_DMG 5→10。动物园v5源码和地图v2保持不变。
