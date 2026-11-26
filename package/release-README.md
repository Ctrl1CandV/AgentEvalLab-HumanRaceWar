# 前哨：公开任务工作区

先读 `rules.md`、`sdk/README.md` 和相应阶段的 `TASK-PHASE1.md` 或 `TASK-PHASE2.md`。工作区只有公开材料；`bot/` 初始为空。可以阅读 SDK、arena 和十个公开对手。开发只用 `maps/public/`，`maps/scrimmage/` 只用于中场练习。

```sh
sha256sum --check PUBLIC-MANIFEST.sha256
python3.13 -m arena check bot --sandbox bwrap --out runs/check
# 小规模开发局，使用宿主提供的同机 jobs=1 时限锁。
python3.13 -m arena tournament --bot bot --opponents bots/public/M-balanced \
  --maps maps/public/open-01.map --jobs 1 --sandbox bwrap \
  --fixed-timing timing-lock-jobs1.json --out runs/example
```

宿主把 `timing-lock-jobs1.json` 和 `timing-lock-jobs6.json` 放在工作区根目录，不列入 `PUBLIC-MANIFEST.sha256`。不要改名、移动或修改；`--jobs` 必须与锁匹配。

只用 Python 3.13 或 C++ 标准库。bot 和 C++ 编译只走离线 bubblewrap；不要直接执行或编译提交。实际时限从开局 `LIMIT` 读取。沙箱或匹配的预算锁不可用时，请报告，不回退到 plain 或自改时限。中场的公开练习赛由宿主在两个阶段之间运行，结果写入 `scrimmage/`。
