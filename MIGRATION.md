# HumanRaceWar 1.0.0 迁移与复核

在 **AgentEvalLab 所在的评测机**执行，使用最终审查确认的公开提交和用户单独拷来的 private tar。不从 GitHub 下载隐私材料，不在开发 WSL 执行正式验证。以下步骤和时长是运行计划；开发机记录不等于评测机证据。

## 1. 准备（约 5–15 分钟，不含安装等待）

确认 Python 3.13、GCC 11、bubblewrap 已安装，至少为 jobs 6 留出 12 个独占 bot 核和另一个 runner 核。不要用 root 跑沙箱，不使用 plain。

```sh
cd "$HOME/projects"
git clone https://github.com/Ctrl1CandV/AgentEvalLab-HumanRaceWar.git
cd "$HOME/projects/AgentEvalLab-HumanRaceWar"
git config core.hooksPath .githooks
python3.13 -m venv --without-pip .venv
.venv/bin/python --version
g++ --version
bwrap --version
```

先对照最终审查给出的提交号。已有文件的仓库不要覆盖；需要保留现有审查目录时，用新工作区。

```sh
set -eu
package="$HOME/hrw-release/humanracewar-1.0.0-private.tar"
(cd "$(dirname "$package")" && sha256sum --check "${package##*/}.sha256")
umask 077
mkdir -p private
tar --extract --keep-old-files --no-same-owner --directory=private --file="$package"
test -f private/ladder/ladder-1.0.0.json
```

预期 tar 摘要等于最终报告，包含阶梯文件、成员源码与构建文件、三套地图和正式校准记录；不含回放或作者档案。`grade` 和 `calibrate` 会再次核对源码树和实际用到的地图摘要。最终留出图只随包保全，不再打。

## 2. 运行测试（开发机约 2 分钟；预留 5–10 分钟）

```sh
.venv/bin/python -B tools/run_tests.py
```

预期完整套件通过，故障回归与第二评分等待测试通过。开发 WSL 专用固定锁与异机不匹配时，只允许测试说明里列明的正向投影项跳过；生产代码不能用开发机锁。

## 3. 本机测速并冻结（预留 2–10 分钟）

```sh
mkdir -p private/host-bench
.venv/bin/python -m arena bench --jobs 6 --sandbox bwrap \
  --reference package/benchmark-reference.json --out private/host-bench/jobs6 \
  > private/host-bench/receipt.json
bench_file=$(.venv/bin/python -c 'import json; from pathlib import Path; print(json.loads(Path("private/host-bench/receipt.json").read_text())["resultFile"])')
.venv/bin/python -m tools.freeze_release_timing --bench "$bench_file" --jobs 6 \
  --out private/host-bench/timing-lock.json
```

预期测量完成，锁绑定本机硬件、jobs 6、bwrap 和实际限额。以后命令都显式引用这把锁，不在同一轮内重测速。以下命令应串行执行。

## 4. 复核相邻级（按本机速度预留 10–45 分钟）

```sh
.venv/bin/python -m arena calibrate --mode adjacent \
  --ladder private/ladder/ladder-1.0.0.json --maps private/maps/calibration \
  --fixed-timing private/host-bench/timing-lock.json --out private/migration/adjacent
```

每对 12 图双座，共 24 局。比较结果在 `private/migration/adjacent/results.json`，每个相邻级距偏差须在 ±50 Elo 内。区间不可识别、矩阵不全或超差不能当成一致。若不一致，保留原 1.0.0，以评测机完成同级、相邻、隔一级的正式校准并重新拟合，登记新版本的阶梯文件；不要调评分图或重用 holdout 追过线。

## 5. 复核评分与噪声（每次评分目标 ≤45 分钟）

```sh
for bot in Z-idle M-balanced; do
  .venv/bin/python -m arena grade --submission "bots/public/$bot" \
    --ladder private/ladder/ladder-1.0.0.json --maps private/maps/grading \
    --fixed-timing private/host-bench/timing-lock.json \
    --out "private/migration/$bot-idle.json"
done
.venv/bin/python -m tools.release_noise --submission bots/public/M-balanced \
  --ladder private/ladder/ladder-1.0.0.json --maps private/maps/grading \
  --fixed-timing private/host-bench/timing-lock.json --out private/migration/M-balanced-load.json
```

预期两次空闲评分完整；两份 `headlineOutcomeOnly` 分别与开发机同版记录的差不超过 0.03。负载测试用六个纯 CPU 忙循环，比较 M-balanced 空闲与负载的 `headlineOutcomeOnly` 和 `headline`，两种差都不超过 0.03；超出时再测一次空闲，保留三次原件。工作单的开发机噪声用旧 astra 第二阶段提交，该提交不随包迁移，故迁移自检用公开锚。若重新拟合或用户确认新计分配置，应标明所比版本，不把不可比结果当通过。

## 对接练习赛

评测宿主在两个阶段之间运行，可从公开材料导出目录执行。`--fixed-timing` 用宿主提供的锁，`--out` 指向新的反馈目录。不要把 arena 原始运行目录或正式评分结果放进任务工作区。

```sh
.venv/bin/python -m arena scrimmage --submission /path/to/workspace/bot \
  --fixed-timing private/host-bench/timing-lock.json --out /path/to/workspace/scrimmage
```

预期填入 `results.json`、`results.md`、`turns.csv` 和至多三份失败回放。此命令不需要 private 阶梯或地图。
