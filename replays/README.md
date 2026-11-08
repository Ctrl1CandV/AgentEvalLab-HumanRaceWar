# replays

少量有代表性的对局回放，用来审查有没有退化的打法：
- 每次更新最多 10 局，每局不超过 200 KB；
- 只放公开 bot 之间的对局；有隐藏 bot 参与的对局，一律不放这里。

`phase-a-v15-maze-loss.hrw.jsonl.gz`：最终zoo v15/P7矩阵中M对铺塔在maze-01的败局，52,494字节，M以1025对1073塔分失败。保留这一未解决的个别败局，不用示例回放代表完整矩阵；其全部PARAM也用于核对standard-1默认配置。

格式见 DESIGN 第 8 节，可以用 `.venv/bin/python -m arena replay show <回放路径> --turn 25` 查看。

`runtime-smoke.hrw.jsonl.gz`：Python/C++ 公开 SDK 示例在 `tests/fixtures/smoke.map` 上的首个 CLI 开发局，300 回合；17,148 字节，双方无警告或故障，C++ 以累计卸货量 820 对 660 胜出。`replay verify` 可逐回合核对。这是工具连通性示例，不是正式地图或平衡验收局。全部测试局和失败尝试仍保留在本地 `runs/`，汇总见 `data/runtime-tests.json`。
