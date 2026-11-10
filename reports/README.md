# 审查报告

- [`phase-B-author-r02.md`](phase-B-author-r02.md)：作者160局筛选阴性停止，未交付新版本；原样归档及完整回放核验，原诊断解释需修正，下一步仅零新局补正，不自动r03。

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

数据入口在`data/`，只上传审查汇总；原始对局与旧完整日志留本机。目录和历史限制见`docs/REPOSITORY.md`。B的前置留出复核未过就停止；B全部完成后仍须等待审查，不进入C。
