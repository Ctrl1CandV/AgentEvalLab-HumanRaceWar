# 状态

更新：2026-11-08。**第二份B审查的R1/R2及N1/N2/N3已完成。N1全部失败项仅差1图，新留出判定生效，v15前置复核按新标准通过；N2有反例，不改M、不运行v16。全新holdout 24图已冻结、布局及独立复核通过，未打对局。准备阶梯时发现L0指定两bot不接近，现按BRIEF 3.3停下等待B-L0-001构成裁定。D22仍拒绝，没有完整阶梯，B未完成，C未启动。**

最新停点：[`reports/phase-B-ladder-preflight.md`](reports/phase-B-ladder-preflight.md)；N1/N2/N3：[`reports/phase-B-review-analysis.md`](reports/phase-B-review-analysis.md)；D22报告：[`reports/phase-B-damage22.md`](reports/phase-B-damage22.md)；原计划：`docs/PHASE_B_DAMAGE22_PLAN.md`。D22的一轮授权已用完，standard-1仍为伤害20。后续权限以新审查第六节及用户明确授权为准：N1过关才启用新标准；N2成立才可选另存v16小修M；前置/新holdout布局检查满足后可继续B，不自动改游戏参数或提前使用holdout。

- A已获审查通过：[`inbox/2026-11-08-phase-a-accepted.md`](inbox/2026-11-08-phase-a-accepted.md)。standard-1、游戏引擎/SDK和动物园v15未改；本轮只按R1修改运行器的预算复用，框架指纹会变化，不能再宣称整个arena字节未变。
- 首次留出报告：[`reports/phase-B-holdout.md`](reports/phase-B-holdout.md)；原始结论和数据保留。D22数据在[`data/phase-b/damage22/`](data/phase-b/damage22/)。两份都是失败停点报告，不是B完成报告。
- 工作目录仍为WSL `~/projects/AgentEvalLab-HumanRaceWar`，hooks为`.githooks`；不改写历史。此前留出/D22的7个提交已按用户授权推送至`42f6294`，本机当前又有审查提交`13360d7`；本次修改只做小步本地提交。

## 第二份B审查逐条回复（`inbox/2026-11-08-phase-b-holdout-review.md`）

本机已有审查提交`13360d7`，与本地origin/main一致，工作区起初干净，hooks为`.githooks`。前两次`git pull --ff-only`在现有SSH代理连接处超时；没有改认证/代理，也不宣称再次联网同步成功。用户随后要求按本机审查处理。审查原件保留；先前`42f6294`已按用户要求推送，本轮只获准本地提交。

| 分类/条目 | 处理方式与相关文件 | 验证/证据 | 未解决项与状态 |
|---|---|---|---|
| 必须改 R1 固定配对/校准限额 | `arena/core/timing.py`、`arena/tournament.py`、`arena/match.py`、CLI新增固定预算；`tools/freeze_batch_timing.py`从完整基线核对全部回放头后封存；DESIGN 6.2、BATCH同步 | 先复现缺失接口4个错误；新增5项及完整228项通过，含真实bwrap首次冻结、续跑/配对禁止重测；数值/摘要/后端/并发/回合变动拒绝；最后5项在hashseed=0/1通过，6文件LSP零诊断，`data/phase-b/review-validation.json`保留修前失败 | 正式评分D4不变；后续校准入口须使用固定模式 |
| 必须改 R2 接战前相同不算机制发现 | `reports/phase-B-damage22.md`4.1改为确定性/配对一致性检查，限定里程碑而非全部轨迹 | 原数值不变；注明第一次战士接战不一定是第一次造成伤害 | 已改 |
| 必须分析 N1 距门槛地图数 | `tools/review_holdout.py`核对四份档案，保留两座簇和类型/尺寸计数；`data/phase-b/margins.json` | 全部8个实际失败关系/条件均只差1图；不存在更远的实际失败项 | 新标准生效；敏感性条件不是不存在策略缺陷的统计证明 |
| 必须分析 N2 M目标选择假设 | 原基线public20局/calibration12局maze全部重放；离线bwrap诊断副本只读原观察，原M不改；`tools/review_maze.py`、`data/phase-b/maze-hypothesis.json` | 9538回合stdout逐行一致、状态哈希全过；public半数负局和calibration三分之一负局大部分时间并不塔数落后，且存在拆塔反例 | 假设未获完整支持，跳过M修改；不换其他策略问题尝试 |
| 必须分析 N3 经济/骚扰的类型克制 | `data/phase-b/type-counters.json`按类型给原v15双胜/双负计数 | 两套均open/corridor偏经济、maze偏骚扰；island跨集反转。总体24/48是优势抵消 | 已完成；不把小样本类型标签当普遍规律 |
| 已批准的条件式留出标准 | DESIGN 11.5、BRIEF 5.0按审查第三节写入；N1完成后启用 | 原v15 calibration按新标准全部通过；public 10.2不改，D22仍拒绝，第4/6/7项仍点估计 | 已生效；不改写旧判定 |
| 可选建议 M v16 | 按N2结果保留v15及全部10个bot，不开展可选试验 | 冻结源码不变，没有新增5888局 | 已跳过；不是漏做必需矩阵 |
| 必须项 新holdout与后续B | `tools/prepare_final_holdout.py`分plan/build；从干净`6da1630`先登记新种子，再生成24图；原48张隐藏图和catalog不变 | 五集合116图互异，独立检查1392条家门矿/1160个塔基，新24图再生一致；`data/phase-b/final-holdout-maps.json`只含汇总，holdout对局0 | 布局前置已完成；后续阶梯因新问题B-L0-001暂停，未做最终复核，C未授权 |
| 新问题 B-L0-001（BRIEF 3.3） | L0指定Z-random/Z-miner与同级≤80 Elo的目标存在明显不一致；`tools/check_ladder_anchors.py`只读已有资料 | 两套基线Z-miner均胜87.5%；两bot BT差338.04 Elo；不是全阶梯联合拟合或正式校准失败。证据`data/phase-b/ladder-anchor-preflight.json` | 不擅改构成/豁免门槛；等待是否允许另选/另做L0基线的裁定 |

新增分析验证：完整237项在hashseed=0通过，零失败/错误/跳过；包含新增9项的27项`test_review_*.py`在hashseed=1通过，4文件LSP零诊断。见`data/phase-b/analysis-validation.json`。原始证据只留private；N1/N3约0.000106宿主CPU小时，N2约0.001718宿主和0.000909诊断bot CPU小时，编译及完整总量未知。没有新平衡对局，也没有重测速度系数。

## 需要决定的事

**B-L0-001：DESIGN 11.1的L0名字是否必须固定？** 已有public/calibration中Z-miner对Z-random分别70/80、42/48，两bot BT差约338 Elo，明显不像同级接近。尚无完整阶梯，不能把两bot诊断冒充联合校准失败；但也不能无说明地更换指定bot。建议允许保留冻结v15动物园，为L0另选/另做强度接近且风格不同的基线，仍按完整校准执行原80 Elo门槛。未获得该裁定前停在这里，不重新申请已经获准的N1/holdout中间审查，也不自行改阈值。

最终验证：完整249项（hashseed=0）通过，零失败/错误/跳过；地图8项及锚点4项另在hashseed=1通过，8个分析/地图/锚点Python文件LSP零诊断。`data/phase-b/preflight-validation.json`保留测试及计量汇总。地图生成/复核/再生约0.000947 CPU小时，锚点只读分析约0.000108小时；登记和完整阶段总量未知。新登记后138,043个私有文件摘要全过；原始文件与失败证据全部保留，只本地提交、未推送。

## 首份2026-11-08审查逐条回复（历史）

| 意见 | 本轮处理、证据与未解决项 | 实施状态 |
|---|---|---|
| A通过，可进入B；冻结standard-1/v15 | 核对源码、规则、框架/SDK及评测机参考摘要，未改冻结输入 | 已落实；A通过不等于B通过 |
| 新增11.5第7条防“一招鲜” | DESIGN已写入9个Z及M对L6+各级校准，仅胜负分，每级≤0.1；不放宽、不披露隐藏bot的具体失利关系 | 未执行；前置留出失败，没有阶梯 |
| 新增11.5第8条留出复核 | 24张calibration、17/29、换边、M自对弈，2208局完成并全部回放验证；第1/2项失败，第4/6/7项通过 | **首次留出未过即停；随后获准的D22也失败，没有重抽/建阶梯** |
| DESIGN 17的B验收改为8条 | 已保留前置留出及最终停点 | 已落实；B整体未完成 |
| 取消构建token记录，CPU照旧 | 未采集构建token；CPU分bot、match、校验、控制、地图及bench记录，未知环节明确标注 | `data/phase-b/usage.json`；正式预算自测仍按BRIEF 5.3，尚未执行 |
| 隐藏地图、bot及相关对局只能在private；登记摘要 | 两套地图各24张已冻结，四类各6张；生成计划、元数据、缓存、bench、原始对局、分析及日志全留private并登记 | 已落实；没有隐藏bot，grading未用于对局；公开仅汇总 |
| M作为L2参照，按校准确认定位 | 接受审查结论，但没有擅改M或硬定Elo定位 | 前置失败，未做阶梯校准 |
| B全部完成后报告并停下 | 本次按失败停点写`reports/phase-B-holdout.md`，不冒充B完成；更新汇总及清单 | D22失败报告等待审查；未执行两项会话自测或防“一招鲜”，不进C |

## 原标准下的留出结果（历史；新标准复核见上）

- 48张隐藏地图全部通过既有布局检查、互不重复且不与public/scrimmage重复；按原计划逐字节再生一致。独立BFS的576个家门矿及480个塔基检查全过。先冻结地图，后运行，没有按胜负挑图。
- 唯一批次`private/phase-b/holdout-v15/`：2160局不同名配对+48局M自对弈，**2208次尝试全部complete**；框架错误、配置错误、bot故障及协议警告均为0。2208份回放全过，450个聚合单元经独立计数一致。
- **10.2(1)失败：** Z-eco、Z-harass均无胜率严格低于50%的单一打法克制者；相互各24/48。Z-eco对Z-rush为30/48，Z-harass对Z-rush为28/48。
- **10.2(2)失败：** M总体最低40/48=83.33%，但maze对Z-towers仅6/12=50%，低于55%；95%地图簇区间[16.67%,83.33%]。
- 第4项：排除idle/同名后的1728局无平局。第6项：M自对弈拆基地14/48、回合上限34/48，均在20%–80%。第7项：分类型M最低50%，无单一打法赢M。
- 区间以地图为簇；每类型只有6张，不能把12个座位样本或确定性重复当独立地图。区间宽不能豁免点估计门槛，24图复核也不是新的公开40图D6。

## D22结果与处理

- public 3680局、calibration 2208局全部完成并通过回放验证；零框架/配置错误、bot故障和协议警告。5888份实际PARAM/地图/种子核对通过；900个矩阵单元独立计数及配对边际核对一致。
- **calibration仍失败第1、2项：** 经济对速攻30→26/48、骚扰对速攻28→26/48，彼此仍24/48，没有严格克制者。M对铺塔总体40→42/48，但maze仍6/12，新增胜局来自corridor。
- **public新增第1、6项失败：** 骚扰对经济36→40/80，失去克制者；M自对弈拆基地20→14/80=17.5%。其余原门槛没有放宽。
- 预定6组全队列共1536份基线/候选回放另做轨迹诊断。探索性转移分组显示：maze持续输掉的6局都没打中敌基地，塔分差中位仍−248；公开自对弈6局由拆基地退为塔分结算，其中4局候选没打中任何基地。支持优先检查有效推进/目标选择，不足以断言拥堵就是根因。
- **拒绝D22，不覆盖默认。** 不继续统一加伤盲调；建议先审查策略瓶颈、拆开处理M推进与单一打法克制问题。当时塔价175或改bot均未获新授权；后续仅M指定规则的条件式许可及本次跳过决定见上。grading未用于对局或筛选；calibration是开发集复测，不再称新留出。
- 运行从干净`cc3fc28`启动；`5cedf4c`加入只读轨迹诊断，结果后补充的分组标为探索性。首次plan路径表示错误在启动bot前被拒绝，回归先复现后修复，失败保留。
- 运行前全套217项、整理时全套223项通过；配对分析5项及分组补充在两种哈希种子下通过，5个新Python文件Pyright零诊断。完整汇总在`data/phase-b/damage22/validation.json`。
- bot/match harness/全回放验证三类共约0.606457 CPU小时；额外轨迹回放0.032484小时，控制/测试等另列，编译及阶段完整总量未知。各批正常暖机折算的CPU限额不同，11776份基线/候选回放头普查见`runtime.json`；游戏参数仍只改伤害，v15不按时钟/LIMIT决策。
- public原始对局仅留`runs/development/phase-b-damage22-public/`；calibration及合并原始分析仅留`private/phase-b/damage22/`。公开仅聚合证据，全部失败保留。停止后原68,841个私有文件摘要未变，更新登记后137,638个文件全部核对一致；公开清单随提交更新。只本地提交，不推送。

## 首次留出工具、检查与用量（历史）

- 工具提交`4ba9e0a`：`tools/generate_hidden_maps.py`先持久化私有计划；`tools/phase_b_holdout.py`分plan/run/analyze并逐项核对冻结输入及2208任务。路径拒绝逃逸/链接，续跑不重抽；完整分析只写private，公开副本按字段白名单提取。
- 启动HEAD实际为`6b8664d`，当时工具/文档未提交，随后原样提交为`4ba9e0a`；不伪称干净提交启动。对局执行的引擎/SDK、源码、地图均按字节冻结。汇总见`data/phase-b/provenance.json`。
- 开工全套203项通过；新增9项合成工具测试在`PYTHONHASHSEED=0/1`各通过，3个新文件Pyright零诊断。没有宣称新增工具后重跑完整212项；失败后未追加B对局，只核对计数、运行合成工具测试和整理报告。
- 本批bot/match harness/回放校验分别0.068523/0.122689/0.038340 CPU小时；地图生成/独立复核分别约1.674/1.850秒。其余控制/bench范围另列，编译和完整总量未知，不叠加RUSAGE_CHILDREN冒充完整用量。机器为i5-14600KF，可见20逻辑CPU，jobs=6，速度系数0.6012284089。
- 本轮测试原件留`runs/development/phase-b-preflight/`；隐藏原件及完整分析只留private。生成、计划和结束静止检查点登记`private/HIDDEN.sha256`；全部68,841个私有文件摘要已核对一致。公开聚合矩阵不是逐局表；所有失败与原件都保留。
- 暂存汇总已检查真实隐藏生成种子、地图原文和任务ID均未泄露，已知格式发布检查通过。首次报告提交被摘要钩子拒绝（公开聚合JSON与私有派生摘要相同）；保留原件及登记，公开JSON去掉重复矩阵，完整聚合矩阵只在CSV列一次，并重新核对。未绕过钩子。提交时再核对实际范围与MANIFEST，只本地提交，不推送。

## 保留的A阶段依据

- `reports/phase-A.md`、`data/phase-a/matrices/zoo-standard-1-final.json`：40图3680局条件全过，最终复跑不是新增独立样本；A通过结论不改写。
- 交审前两个哈希种子各198项，整理时专项各79项，都是既有验证。累计61,979次尝试：61,789 complete、186 infra_error、4 configuration_error，原失败保留。
- 历史bot/宿主CPU约2.561/3.579小时，回放复核另约1.311小时；完整历史总量未知，不与本轮混算。
- 原始运行在`runs/development/`，整理前555份原件在`runs/local-evidence/509f1f8-before-summary-only/`，没有删除或重新加入Git。

新会话先读本文件、`reports/phase-B-damage22.md`、首次留出报告及inbox，不把`docs/PHASE_B_HANDOFF.md`的原始启动快照当作“尚未运行”。目录与发布范围见`docs/REPOSITORY.md`；旧历史仍有A阶段曾公开的明细，不声称已清除，更不以此作为上传B隐藏内容的许可。
