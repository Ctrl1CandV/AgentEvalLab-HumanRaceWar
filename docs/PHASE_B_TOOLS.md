# B前置留出工具与输出边界

2026-11-08。standard-1、动物园v15及引擎/SDK不变。首次留出及D22按旧标准失败；第二份审查的N1已完成，新留出标准生效、v15前置通过；N2有反例，不改M。R1改变了运行器预算复用，2026-11-09中期审查M1再增加机器绑定。当前权限见`STATUS.md`及`inbox/2026-11-09-phase-b-mid-review.md`，不重做旧地图/基线，不重跑D22。下面旧地图/留出命令是历史说明，不据此重跑；中期准备工具见末节。

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

## 新holdout：先登记、后生成

```sh
.venv/bin/python -B -m tools.prepare_final_holdout plan
.venv/bin/python -B -m tools.prepare_final_holdout build
```

- 这两个命令不执行bot。先检查N1生效、原v15前置按新标准通过，以及N2诊断完整、原10个bot和standard-1不变。
- `plan`一次抽取24个全新64位种子，写`private/holdout-maps/generation-plan.json`并登记HIDDEN.sha256，之后才允许`build`。四类各6张，尺寸24/28/32/36/40/32；种子碰撞即停，不再抽取替代。
- 新目录与`private/maps/`分开，原calibration/grading及catalog原样保留；旧工具的完整48图检查不用放宽。
- `build`核对计划的已登记字节和前置输入，用不变v2生成器生成。重复、耗尽或校验失败即停；不覆盖不同资产。完成后拒绝再次build。中断发生在catalog写成前时只能续同一计划和相同字节。
- 全部五套图重新检查布局；另一个不调用生成器几何辅助函数的实现复核连通、旋转/矿量对称、资源分区、路径、出兵及近矿要求。单格咽喉用空地图的割点数表示，另列真正阻断两基地全部路径的割点数；低链DFS已与3×3全部子图逐点移除的穷举结果对照。
- 新24图逐字节再生核对，布局与逐图指标只在private。公开`data/phase-b/final-holdout-maps.json`只给各集合/类型/尺寸的计数和分布，不给种子或逐图记录。布局相近不证明战略难度相等。
- **B末之前不在新holdout打任何对局。** 2026-11-09起public调参、dev取舍/临时BT，calibration不再做开发对局；完成其他B要求后才做一次最终2208局复核。

## 2026-11-09中期第0步（没有新对局）

- `tools/review_mainlines.py`仅分析已有档案，输出L1–L6、固定池及有历史证据的机器绑定锁封装。全量明细/抽样在`private/phase-b/mid-review-step0/`，公开只有`data/phase-b/mid-review.json`；完成的immutable输出不重复覆盖。`tools/provisional_bt.py`不执行bot，处理强连通、完全分离和共同地图簇区间，不是正式阶梯等级工具。
- `.venv/bin/python -B -m tools.prepare_dev_maps plan`后再`build`：80个新种子先登记，冻结v2生成器/独立检查器，四类各20、每尺寸各4；预定均衡首段40图。原116图不变，全部196图不重复，布局和再生通过才发布`data/phase-b/dev-maps.json`聚合。源码或输入变更、碰撞、耗尽/检查失败均停，不补抽、不打对局。
- `tools/prepare_author_workspace.py`按`package/public-files.json`只向不存在的独立目录导出公开材料，并验证清单/摘要、无Git/链接、CLI导入和已有公开地图。命令见`package/README.md`，角色及启动边界见`docs/AUTHORS.md`。导出不启动模型、bot、编译或测速，不能替代用户的新会话和上下文核查。

## 回归与限制

`tests/test_phase_b_holdout.py`使用合成输入，检查私有路径边界、先计划后生成、原计划续跑、重复即停、精确配对、指定停点和字段白名单；不接触真实隐藏布局，也不执行bot。已有发布检查不是任意格式脱敏器，MANIFEST和Git钩子不能替代人工检查。
