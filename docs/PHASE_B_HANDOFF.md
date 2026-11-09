# B阶段启动交接

原始交接日期2026-11-08；入口说明更新于2026-11-09。此文保留`6b8664d`启动快照，不是当前待办或B完成报告。**2026-11-09中期审查第0步已完成，保留dev02且无新对局：机器锁、L1–L6、dev80、两工作区和dev05计划均就绪；已到先报告目录并停止的约定停点，不推送，由用户推送。** 先读`STATUS.md`、`inbox/2026-11-09-phase-b-mid-review.md`、`reports/phase-B-mid-review-step0.md`及`docs/AUTHORS.md`；下一执行批按`docs/PHASE_B_DEV05_PLAN.md`，本准备批未启动它。下文的“尚无private”“先跑留出”“不得继续建阶梯”以及末尾启动提示均属历史快照，不得据此重做已完成工作或覆盖新授权。D22仍拒绝；后续同机预算改用M1另存的机器绑定封装，保留dev01原锁与全部数值，不重新测速；移机必须重新测量/冻结。public调参、dev取舍/临时BT、calibration仅正式校准，不改参数、不提前使用holdout。工具见`docs/PHASE_B_TOOLS.md`。

## 1. 当前事实

- 用户已授权进入B。审查意见：`inbox/2026-11-08-phase-a-accepted.md`，已在`139e5bd`入库；A阶段通过，standard-1与动物园v15按交审配置冻结。
- 本轮已`git pull --ff-only`，按项目`/process-review`模板更新DESIGN、BRIEF、STATUS、AGENTS和入口文档；只做交接，没有运行B实验。
- **尚无private/、隐藏地图、隐藏bot、阶梯校准或后台任务。** 没有待续跑的B对局，也没有可以宣称通过的B指标。
- WSL工作目录：`~/projects/AgentEvalLab-HumanRaceWar`；Python用`.venv/bin/python`，框架只用标准库。主分支main，hooks必须为`.githooks`；提交身份沿用gpt-6-astra/GitHub noreply。
- 用户要求换会话是为了实施效率与质量；新会话从已验收配置开始，不必重新逐局研究A阶段所有失败候选。

## 2. 新会话先读什么

1. `AGENTS.md`，检查inbox是否又有更新；先读最新审查。
2. 完整阅读`docs/DESIGN.md`、`docs/BRIEF.md`、`STATUS.md`。
3. 首次接手补读`docs/WSL_HANDOFF.md`、`docs/IMPLEMENTATION_NOTES.md`、`tests/COVERAGE.md`。
4. 本文、`docs/REPOSITORY.md`；需要A结论时看`reports/phase-A.md`和`data/phase-a/`，不要把历史失败状态当作当前结论。
5. 检查`git status --short --branch`、当前提交、`git config --get core.hooksPath`；保留任何用户修改，再按用户提示`git pull --ff-only`。如不能快进，先报告，不重置、不改写历史。本轮交接只本地提交，没有自动推送；接手时据实际状态确认，不假定本地与远端相等。

## 3. 第一项工作：私有地图与前置留出

先完成这一项，再考虑阶梯实现。

1. 检查现有地图生成、批运行、编译缓存、回放审计、分析器的私有路径传播。隐藏输入不能只把最终报告挪到private，而把快照、缓存、日志留到公开运行目录。
2. 生成calibration与grading各24张地图，只放`private/maps/`；按现有地图合法性/D5要求检查，覆盖四类地图，并在开跑前记录各类构成。登记`private/HIDDEN.sha256`。种子、生成元数据及相关输出均留private。
3. 检查与public/scrimmage以及两隐藏集合之间的重复，冻结地图清单和摘要。不能看了胜负再挑图或重抽种子；grading不用来做本轮调参筛选。
4. 使用冻结的10个动物园bot、standard-1、种子17/29，在calibration全部24图换边；包括不同种子的M自对弈。按现有D6结构应为45×24×2+24×2=**2208局**，先核对实际任务清单。
5. 继续使用bwrap与同并发度折算，参考为`inbox/bench-eval-machine-2026-11-07.json`的空闲单实例结果。所有bot和C++编译在沙箱内，离线运行；本宿主不能裸用plain。对局输出用全新的private目录，保留失败与重试。
6. 全量校验后，只按11.5第8条重新检查10.2第1、2、4、6、7条，按地图簇给区间。原始结果与逐图明细留private，对外提取经过检查的聚合汇总。
7. **任何要求未达到就停下报告并提出方案。** 不继续建阶梯、不先改参数、不重抽地图。后续获准调参仍限附录A，每次同时重跑公开与calibration两套完整矩阵。

### 现有工具需要注意

- 地图：`arena/games/outpost/mapgen.py`、`maps.py`；公开地图生成入口是`tools/generate_public_maps.py`。不能把隐藏种子或输出清单加进公开生成脚本。
- 批运行：`arena/tournament.py`已有隐藏输入必须配私有输出的检查，并在批目录内保存快照、缓存和结果；实施前仍核查全部旁路日志和调用者。
- `tools/analyze_zoo.py`目前的`eligiblePublicD6Matrix`明确要求**40张公开图、3680局**，不能把24图复核硬说成公开D6通过。它的总布尔还包含公平性/长度等其他项，不能直接代替新增第8条的指定验收集合。
- 分析器会写逐局CSV和带完整审计列表的JSON，隐藏批次的分析输出必须仍在private。`tools/publication.py`是已知格式的发布检查，不是隐私脱敏器，不能单凭它通过就公开隐藏分析报告。
- 校验器：`arena.games.outpost.replay.verify`；`tools/audit_replays.py`可做批量复核。避免把私有逐局结果输出到公开测试日志。

## 4. 留出通过后才做

- 按BRIEF第5节开发进攻/经济/控制主线及强度档，构造约12级阶梯；M作为L2参照，最终按校准确认定位。
- 在calibration校准、拟合Bradley–Terry Elo及地图bootstrap区间，完成11.5第1–4条。
- 按11.5第5、6条执行真正隔离的新会话测试。不能用已经看过隐藏实现的本构建会话冒充公开材料标准预算自测；两阶段正式预算和测试自身记录仍有效。
- 执行第7条：9个Z和M逐个对L6+各级，**只用胜负分**，每个提交在每一级平均≤0.1。未达标就加强阶梯，不能自行放宽；不公开隐藏bot输给具体打法的对应关系。
- 过程分仍是雏形，不自行冻结公式或改评分局数。到自测需要主分数时核对批准口径，遇到新歧义按BRIEF 3.3记录，不能默认采用尚未冻结的公式。
- B全部完成后写`reports/phase-B.md`，更新data/logs、清单与STATUS，然后停止等审查；没有C阶段授权。

## 5. 保密、用量与现有证据

- 隐藏资产、隐藏生成元数据及相关对局只在private；按要求登记HIDDEN.sha256。不得复制到data、logs、runs或公开bot目录。对外只发布允许的代号、风格、摘要和统计，不公开布局、实现或弱点。
- 公开bot之间的实际对局也不上传。保留本机完整原件和失败，不用删除数据换取目录整洁；发布范围见`docs/REPOSITORY.md`。
- **不再采集构建token统计，不读会话文件凑用量。** CPU小时继续分范围记录，缺失写未知，不重复加RUSAGE_CHILDREN。正式预算自测仍遵守BRIEF 5.3。
- A最终40图3680局通过，验收前两种哈希种子各198测试通过；目录整理的专项检查为两种种子各79项。这些都是既有证据，本轮文档更新没有重跑它们。
- A原始运行在`runs/development/`；整理前555份证据在`runs/local-evidence/509f1f8-before-summary-only/`，不要清理。当前数据位置见`data/phase-a/catalog.json`。
- 旧Git历史仍有A阶段曾公开的明细；这不是上传B隐藏内容的许可。本轮没有改写历史，也没有新增推送授权。

## 6. 可复制的启动提示词

> 继续在WSL的`~/projects/AgentEvalLab-HumanRaceWar`推进B阶段。先检查Git状态并保留用户改动，执行`git pull --ff-only`，按`/process-review`流程检查hooks和inbox新意见。完整阅读AGENTS、DESIGN、BRIEF、STATUS及`docs/PHASE_B_HANDOFF.md`，首次接手按AGENTS补读交接/实现/覆盖文档。
>
> A已通过（`inbox/2026-11-08-phase-a-accepted.md`），standard-1和动物园v15冻结。上一会话只更新了文档和交接，没有生成private资产或启动B对局。先生成并登记私有calibration/grading地图，再做24张calibration上的v15留出复核（种子17/29、换边、含M自对弈，预计2208局）。第8条未过立即停下报告并提出方案，不改参、不挑图、不建阶梯；通过后才按BRIEF第5节推进阶梯及剩余验收。
>
> 所有bot/编译在bwrap内离线运行；隐藏资产和相关原始输出只在private。不上载任何逐局数据，只发布审查汇总。构建token不再统计，CPU照旧，正式标准预算自测要求不变。小步本地提交，不擅自推送；B完成后报告并停下等审查，不进入C。
