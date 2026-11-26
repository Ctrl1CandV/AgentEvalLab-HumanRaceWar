# HumanRaceWar 1.0.0 迁移与复核

在 **AgentEvalLab 所在的评测机**执行，使用最终审查确认的公开提交和用户单独拷来的 private tar。不从 GitHub 下载隐私材料，不在开发 WSL 执行正式验证。以下步骤和时长是运行计划；开发机记录不等于评测机证据。

## 1. 准备（约 5–15 分钟，不含安装等待）

确认 Python 3.13、GCC 11、bubblewrap 已安装，至少为 jobs 6 留出 12 个独占 bot 核和另一个 runner 核。不要用 root 跑沙箱，不使用 plain。

```sh
# HRW_REVIEWED_COMMIT 设为 CA 确认的完整公开提交号。
: "${HRW_REVIEWED_COMMIT:?先指定 CA 确认的完整提交号}"
mkdir -p "$HOME/projects"
cd "$HOME/projects"
git clone https://github.com/Ctrl1CandV/AgentEvalLab-HumanRaceWar.git
cd "$HOME/projects/AgentEvalLab-HumanRaceWar"
git switch --detach "$HRW_REVIEWED_COMMIT"
test "$(git rev-parse HEAD)" = "$HRW_REVIEWED_COMMIT"
git config core.hooksPath .githooks
python3.13 -m venv --without-pip .venv
.venv/bin/python --version
g++ --version
bwrap --version
```

不要在已有文件的仓库里覆盖解包。若评测机已有审查仓库，另建一个干净的 checkout 或 worktree，固定到同一提交，不改变已有分支。将 tar 和 `.tar.sha256` 一并拷到评测机 `~/hrw-release/`。

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

开发机最终检查 407 项，无失败或跳过。评测机预期故障回归与第二评分等待测试通过。WSL 专用锁与异机不匹配时，只允许测试中明确列明的正向投影项跳过；生产评分必须用评测机锁。

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

56 对各打 12 图双座，共 1,344 局。`private/migration/adjacent/results.json` 的 `passed` 应为 `true`，每个相邻级距偏差须在 ±50 Elo 内。若命令退出码为 2，先读结果；不可识别、矩阵不全或超差都不能当成一致。若不一致，保留原 1.0.0，按 [DESIGN 11.4](docs/DESIGN.md#114-校准) 在评测机重新完成正式校准和拟合，登记新版本的阶梯文件；不要调评分图或重用 holdout。重新拟合不包含在 10–45 分钟的复核估时内。

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

每次应完成 392 局，`infraErrors` 为 0。Z-idle 和 M-balanced 的 `headlineOutcomeOnly` 分别和开发机同版记录 **0.000000**、**0.452381** 相比，绝对差均不超过 0.03。全部原值见[自评聚合](data/phase-c/release-evaluation.json)。

噪声工具在六个纯 CPU 忙循环下评分。比较 M-balanced 的 `M-balanced-idle.json` 和 `M-balanced-load.json`：`headlineOutcomeOnly` 和 `headline` 的绝对差均不超过 0.03。若超出，重复上面 M-balanced 的空闲评分命令，将 `--out` 改为 `private/migration/M-balanced-idle-repeat.json`，保留三次原件。开发机按工单使用旧 astra 第二阶段提交；该提交不随包迁移，因此评测机自检用公开锚。若已重新拟合或用户确认了新计分配置，先标明所比版本，不把不可比结果算作通过。

## 对接练习赛

评测宿主在两个阶段之间运行，可从公开材料导出目录执行。用评测机锁的绝对路径，`--out` 指向新的反馈目录。不要把 arena 原始运行目录或正式评分结果放进任务工作区。

```sh
.venv/bin/python -m arena scrimmage --submission /path/to/workspace/bot \
  --fixed-timing "$HOME/projects/AgentEvalLab-HumanRaceWar/private/host-bench/timing-lock.json" \
  --out /path/to/workspace/scrimmage
```

预期填入 `results.json`、`results.md`、`turns.csv` 和至多三份失败回放。此命令不需要 private 阶梯或地图。
