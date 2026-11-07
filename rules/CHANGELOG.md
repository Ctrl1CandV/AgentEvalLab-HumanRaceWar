# 规则和参数的改动记录

每一条写明：
- 日期和 ruleset；
- 改了什么；
- 为什么改；
- 依据的数据：data/ 里的文件，以及对局数。

只能在 DESIGN 附录 A 的范围内调参数。改规则机制，要先等评测负责人同意（BRIEF 3.3）。

## 2026-11-07：A阶段候选P1（尚未采纳为默认）

- 授权：第二次审查第二节、BRIEF 3.3、DESIGN 10.3；不改机制、结算、胜负或门槛。
- 候选 `rules/candidates/worker-survival-1.json`：WORKER_HP 40→60、WORKER_DMG 5→10，均在附录A范围内；其他参数、v5动物园、地图v2不变。
- 依据：旧正式3680局中的全部720局骚扰对局重放，见 `data/harassment-v5/report.json`。M与守家的阵亡工兵全部在执行ATTACK，工兵原值仅承受两次20伤害；M第25回合战士中位1对5。对守家，934次工兵死亡中778次在家门L1≤8；并非仅远处扩张风险。
- 假设：三击存活窗口及更高反击代价能降低持续杀工兵的净收益，尤其让本已有友军的守家战线更稳定。不能据此断言解决了M的军费分配；也可能增强工兵速攻或使自对弈只剩比分结束。
- 引擎例子：单工兵对单战士仍败；原参数战士余90HP，候选余70HP。`test_harassment_analysis.py`通过。
- 验证：新批次 `runs/development/zoo-p1-worker-survival/` 完整3680局，使用评测机参考；结果待写入 `data/zoo-p1-worker-survival/`。默认规则未变，逐局PARAM公开实际候选值，旧证据不覆盖。

## 2026-11-06：起点

- ruleset standard-1 的起点数值见 docs/DESIGN.md 附录 A，尚未调参。
