# 开发版公开地图集

当前包含 public 40 张（open/corridor/island/maze 各 10 张）和 scrimmage 4 张（每类 1 张）。public 每类的边长为 24、28、32、36、40，各两张；scrimmage 为 32。全部中心旋转对称，地图文件直接复用 MAP/ORE/END 格式。

2026-11-07已升级为生成器v2，并按D5步行距离要求重新生成、独立BFS检查及逐字节再生验证。**布局检查本身不代表平衡验收**：其后standard-1/zoo v15已用全部40张public图通过D6数值条件与公平检查，见 `reports/phase-A.md`；等待阶段审查，不作为留出地图保证。原 `tests/fixtures/smoke.map` 仍只是规则/管道测试图，不混入正式数量。

## 使用

```sh
mkdir -p runs
.venv/bin/python -m arena mapgen --type corridor --size 32 --seed 7 > runs/corridor-7.map
.venv/bin/python -m arena mapcheck maps/public/corridor-01.map
.venv/bin/python -m arena match --a sdk/python/example --b sdk/cpp/example --map maps/scrimmage/maze-01.map
.venv/bin/python tools/generate_public_maps.py
```

`mapgen` 的地图写到 stdout，种子、被拒候选、摘要和检查结果写到 stderr；没有联网和 bot 执行。尺寸支持 24–40 的任意整数，种子为无符号 64 位整数。生成失败时递增种子重试，最多 128 个候选，不降低检查标准。`catalog.json` 记录每张图的请求种子、实际种子、拒绝记录、SHA-256 和布局指标。

批量生成脚本对已存在的相同文件不做修改，遇到不同内容立即拒绝覆盖。评分和校准应读取冻结后的文件，不能现场换种子重生成。

## 当前生成配置

- 伪随机数为自带 SplitMix64，固定 64 位整数运算及无偏有界抽样，不调用 Python `random`。
- 以旋转对应的坐标对生成墙、矿和塔基；基地位于 `(2,2)` 与对称位置。先生成连通地形，再逐对放置资源，资源不能切断空地连通性。
- open 为约 5% 稀疏墙；corridor 为带双格开口的平行隔墙；island 为九个通过窄口相连的区域；maze 为五乘五房间网格上的对称随机连通骨架。基地周边保留出兵空地。
- 每方家门矿恰为 6 格、各 400，共 2,400；每方中场矿 10 格、各 600，共 6,000；共享中心矿 10 格、各 600，共 6,000。总量 22,800，塔基 10 个。所有这些数值都取 DESIGN 的起点配置，没有调参。
- 分区采用曼哈顿距离：离最近基地 4–8 的矿为家门矿；两基地距离都超过 8 且距离差绝对值不超过 4 的为中心矿；其余离最近基地超过 8 的为该方中场矿。
- `basePath` 为两个基地相邻空地之间最短步数加 2，只把基地格作为路径端点，不允许穿过建筑。要求至少 `1.2 × max(W,H)`。
- 检查全部空地连通、资源可邻接到达、资源分区总量、8–12个塔基、任意卸货点距任意矿至少3、每基地距离2内空地至少8。
- D5：每格家门矿与本方基地相邻空地之间最短步数≤12；至少半数塔基能找到同一格矿，同时满足曼哈顿距离3–5和相邻空地之间步行≤6。不进入建筑/矿格，不给步行距离加端点，与basePath的定义不同。后续放矿/塔时也检查是否把已有家门路径绕长。

分区与路径端点口径I11已获同意，v2已补齐D5。旧44图独立检查发现40条家门矿步行违规（含双方和scrimmage）；新44图均通过。17个地图文件改变，墙体/基地不变，未改门宽或环路。44个整图种子候选拒绝0个（位置候选按新约束过滤，不计作种子重试），所有图10个塔基均满足近矿步行要求；规定仍是至少一半，没有放宽阈值。旧资产备份在本地 `runs/development/review-2026-11-07/maps-v1-before-walk/`，历史提交和 `data/mapgen-tests.json` 保留；本批证据见 `data/review-bench-map-tests.json`。

`mapcheck` 检查的是上述默认生成配置，不是对自定义比赛地图新增资格限制；`match` 仍沿用原有结构解析器，不改变游戏规则或 bot 协议。
