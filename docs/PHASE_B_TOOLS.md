# B前置留出工具与输出边界

2026-11-08。standard-1、动物园v15及引擎/SDK不变。**本轮2208局留出未通过，已停止等待调参授权；以下命令仅供说明，不是继续运行的授权。** 先读`STATUS.md`和`reports/phase-B-holdout.md`，不重新生成地图或另起基线。

## 地图

```sh
.venv/bin/python -B -m tools.generate_hidden_maps
```

只写`private/maps/`，先保存`generation-plan.json`再生成地图。calibration/grading各24张，四种类型各6张，各类型预定尺寸24、28、32、36、40、32。48个请求种子由系统熵一次产生，只保存在私有计划；生成器v2只按既有布局检查递增重试，不读取对局胜负。种子候选耗尽、地图重复或已有资产不同即停止，不自动重新抽种子。`--resume`只续原计划，不覆盖不同文件。

`catalog.json`包含地图摘要、种子和完整布局检查，不可公开。校验覆盖D5及已批准I11、48图互不重复、不与40张public/4张scrimmage重复。`data/phase-b/maps.json`只保留构成、集合摘要和汇总检查。grading不用于这次留出或筛图。

## 计划、运行、分析

```sh
.venv/bin/python -B -m tools.phase_b_holdout plan
.venv/bin/python -B -m tools.phase_b_holdout run
.venv/bin/python -B -m tools.phase_b_holdout analyze
```

- plan不启动bot，先保存并核对2208项完整任务：45对不同名bot×24图×2座位，加M-balanced不同种子自对弈48局。种子17/29随bot换边。
- run只能续已有计划；核对A最终矩阵的源码摘要、引擎/SDK指纹、standard-1、评测机参考、jobs=6。准备、编译、bench、运行、快照、缓存、失败重试及日志全部在`private/phase-b/holdout-v15/`，bot和编译仍在离线bwrap内执行。
- analyze复用`tools/analyze_zoo.py`并完整审计回放；原始JSON、逐局CSV和审计列表只放`private/phase-b/holdout-v15-analysis/`。不要直接公开现有分析器的完整报告。
- `review-summary.json`按明确字段白名单提取聚合矩阵、地图簇区间、失败数、CPU及指定验收项。它不带地图名、布局、生成种子、taskId或逐局引用；导入公开data前仍须检查。
- 留出判定只用DESIGN 10.2第1、2、4、6、7条，以`winRate=胜局/总局`为主，并另报半胜平局口径。公平性/长度等诊断不能代替或混入这五项。24图不是公开40图D6的新证据。
- 不完整任务集不发布部分矩阵；输入不一致、回放验证失败或bot故障也不会放行。任何指标未达标就报告并停止，不调参、不重抽、不建阶梯。

`private/HIDDEN.sha256`在静止检查点登记私有文件，包括元数据及运行原件。控制日志在程序退出时才最终定稿，退出后需再登记并完整核对；不要在仍写入的日志上声称摘要已最终一致。生成、controller、match、bench、重放校验分别记录CPU；编译及其他未捕获环节写未知，不叠加RUSAGE_CHILDREN冒充总量。

## 回归与限制

`tests/test_phase_b_holdout.py`使用合成输入，检查私有路径边界、先计划后生成、原计划续跑、重复即停、精确配对、指定停点和字段白名单；不接触真实隐藏布局，也不执行bot。已有发布检查不是任意格式脱敏器，MANIFEST和Git钩子不能替代人工检查。
