# HumanRaceWar 1.0.0 迁移与复核

在 **AgentEvalLab 所在的评测机**按顺序执行。只使用 CA 确认的公开提交以及用户线下拷来的第 2 版 tar 和 `.sha256`。下文的空白环境演练是在开发机做的，不代替评测机复核。七步串行执行；整个过程不并发运行其他 arena 命令。

## 开始前

确认 Python 3.13、g++、bubblewrap 和 GitHub SSH 访问可用，至少留 12 个 bot 核及另外一个 runner 核。用普通用户执行，不用 root 或 plain。将 `HRW_REVIEWED_COMMIT` 设为 CA 确认的完整提交号，再执行下面的变量定义。路径须为绝对路径，`HRW_HOME` 开始时必须不存在。**不要使用或改动 CA 的 `~/projects/AgentEvalLab-HumanRaceWar` 审查仓库。**

```sh
export HRW_REVIEWED_COMMIT="${HRW_REVIEWED_COMMIT:?先指定 CA 确认的完整提交号}"
export HRW_HOME="${HRW_HOME:-$HOME/projects/HRW-1.0.0}"
export HRW_PACKAGE="${HRW_PACKAGE:-$HOME/hrw-release/humanracewar-1.0.0-private-2.tar}"
export HRW_LOCK_DIR="${HRW_LOCK_DIR:-$HOME/.local/state/hrw-locks}"
```

后面每段都使用这四个变量。尤其是 `HRW_LOCK_DIR`，须传给该机上所有 HRW 宿主命令和任务工作区的本地测试命令；即使它们的 `TMPDIR` 不同，也必须共用这一目录。不要改名、移动时限锁或复用开发 WSL 的锁。

## 1. 准备全新 checkout

```sh
: "${HRW_REVIEWED_COMMIT:?}" "${HRW_HOME:?}" "${HRW_PACKAGE:?}" "${HRW_LOCK_DIR:?}"
set -eu
umask 077
test ! -e "$HRW_HOME"
test ! -L "$HRW_HOME"
mkdir -p "$(dirname "$HRW_HOME")"
git clone --depth 1 --single-branch --branch main --no-tags --no-checkout \
  git@github.com:Ctrl1CandV/AgentEvalLab-HumanRaceWar.git "$HRW_HOME"
cd "$HRW_HOME"
if ! git cat-file -e "$HRW_REVIEWED_COMMIT^{commit}" 2>/dev/null; then
  git fetch --depth 1 --no-tags origin "$HRW_REVIEWED_COMMIT"
fi
git switch --detach "$HRW_REVIEWED_COMMIT"
test "$(git rev-parse HEAD)" = "$HRW_REVIEWED_COMMIT"
python3.13 -m venv --without-pip .venv
.venv/bin/python --version
.venv/bin/python -c 'import sys; sys.exit(sys.version_info[:2] != (3, 13))'
g++ --version
bwrap --version
(cd "$(dirname "$HRW_PACKAGE")" && sha256sum --check "${HRW_PACKAGE##*/}.sha256")
mkdir -m 700 private
mkdir -m 700 private/migration
tar --extract --keep-old-files --no-same-owner --directory=private --file="$HRW_PACKAGE"
test -f private/ladder/ladder-1.0.0.json
test -f private/ladder/adjacent-reference-1.0.0.json
```

浅克隆只取迁移所需的公开版本；若 CA 确认的提交不在浅克隆内，按完整提交号补取。对照 [C 报告](reports/phase-C.md)的 SHA-256。除了相邻基准所需的逐局判定记录，不包含逐局原件、回放或作者档案。holdout 随包保全，不再打。

## 2. 运行测试

```sh
: "${HRW_REVIEWED_COMMIT:?}" "${HRW_HOME:?}" "${HRW_PACKAGE:?}" "${HRW_LOCK_DIR:?}"
set -eu
umask 077
cd "$HRW_HOME"
export PATH="$HRW_HOME/.venv/bin:$PATH"
.venv/bin/python -B tools/run_tests.py --json > private/migration/tests.json
.venv/bin/python -B - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('private/migration/tests.json').read_bytes())
allowed = {
    'tests.test_review_balance.ReviewBalanceRuntimeTests.test_empty_tmpdir_falls_back_to_tmp': '/tmp 不可写',
    'tests.test_author_workspace.AuthorWorkspaceTests.test_public_lock_projection_jobs1': 'jobs1 public timing lock belongs to another machine',
    'tests.test_author_workspace.AuthorWorkspaceTests.test_public_lock_projection_jobs6': 'jobs6 public timing lock belongs to another machine',
    'tests.test_author_workspace.AuthorWorkspaceTests.test_legacy_wrapper_projection_does_not_export_its_outcomes': 'jobs6 public timing lock belongs to another machine',
}
if (r['testsRun'] != 418 or not r['passed'] or r['failures'] or r['errors']
        or r['skipped'] != len(r['skippedTests'])
        or any(allowed.get(t['name']) != t['reason'] for t in r['skippedTests'])):
    raise SystemExit('测试未通过或出现不允许的跳过。见 private/migration/tests.json。')
print(r['testsRun'], 'tests;', r['skippedTests'])
PY
```

开发机须运行全部 **418** 项且无跳过。其中 `test_empty_tmpdir_falls_back_to_tmp` 仅在 `/tmp` 不可写时允许跳过；`test_public_lock_projection_jobs1`、`test_public_lock_projection_jobs6`、`test_legacy_wrapper_projection_does_not_export_its_outcomes` 仅在原 WSL 锁不属于本机时允许跳过。测试时也使用此处的共享锁目录，只有测试回退路径的用例会临时覆盖环境。其他失败或跳过必须停止迁移。

## 3. 测速并冻结本机两把锁

```sh
: "${HRW_REVIEWED_COMMIT:?}" "${HRW_HOME:?}" "${HRW_PACKAGE:?}" "${HRW_LOCK_DIR:?}"
set -eu
umask 077
cd "$HRW_HOME"
mkdir -m 700 private/host-bench
for jobs in 6 1; do
  .venv/bin/python -B -m arena bench --jobs "$jobs" --sandbox bwrap \
    --reference package/benchmark-reference.json --out "private/host-bench/jobs$jobs" \
    > "private/host-bench/receipt-jobs$jobs.json"
  bench_file=$(.venv/bin/python -B -c 'import json,sys; print(json.load(open(sys.argv[1]))["resultFile"])' "private/host-bench/receipt-jobs$jobs.json")
  .venv/bin/python -B -m tools.freeze_release_timing --bench "$bench_file" --jobs "$jobs" \
    --out "private/host-bench/timing-lock-jobs$jobs.json"
done
```

`grade`、`calibrate`、`scrimmage` 和负载评分使用 jobs 6 锁；例行本地自测示例使用 jobs 1 锁。两把锁只在本机使用，不在一次迁移中反复测速。

## 4. 相邻复核

```sh
: "${HRW_REVIEWED_COMMIT:?}" "${HRW_HOME:?}" "${HRW_PACKAGE:?}" "${HRW_LOCK_DIR:?}"
set -eu
umask 077
cd "$HRW_HOME"
.venv/bin/python -B -m arena calibrate --mode adjacent \
  --ladder private/ladder/ladder-1.0.0.json --maps private/maps/calibration \
  --reference private/ladder/adjacent-reference-1.0.0.json \
  --jobs 6 --fixed-timing private/host-bench/timing-lock-jobs6.json --out private/migration/adjacent \
  > private/migration/adjacent-cli.json
.venv/bin/python -B - <<'PY'
import json, os
from pathlib import Path
r = json.loads(Path('private/migration/adjacent/results.json').read_bytes())
if (not r['passed'] or r['games'] != 1344 or r['infraErrors']
        or r['lockDirectory'] != str(Path(os.environ['HRW_LOCK_DIR']))):
    raise SystemExit('相邻复核未通过或未使用指定锁目录。')
PY
```

同开发机基准打 56 对，共 1,344 局。代码先校验阶梯、12 图、源码和引擎身份。L0→L1、L1→L2 只诊断；其余 10 对先比有限 Elo 级距（绝对差 ≤50），任一侧非有限则比上一级得分率（绝对差 ≤0.05）。要求无缺局、故障局数不超过基准加 2；`gameAgreement` 只报告。退出码为 2 或配置不一致都不能算通过，保留原件供 CA 判断。

## 5. 核对评分和噪声

```sh
: "${HRW_REVIEWED_COMMIT:?}" "${HRW_HOME:?}" "${HRW_PACKAGE:?}" "${HRW_LOCK_DIR:?}"
set -eu
umask 077
cd "$HRW_HOME"
.venv/bin/python -B - <<'PY'
import json, os, subprocess, sys
from pathlib import Path

root = Path('private/migration')
ladder = 'private/ladder/ladder-1.0.0.json'
common = ['--ladder', ladder, '--maps', 'private/maps/grading',
          '--fixed-timing', 'private/host-bench/timing-lock-jobs6.json']
keys = ('headline', 'headlineOutcomeOnly')
locks = str(Path(os.environ['HRW_LOCK_DIR']))

def grade(source, name, loaded=False):
    out = root / (name + '.json')
    command = ['-m', 'tools.release_noise'] if loaded else ['-m', 'arena', 'grade', '--jobs', '6']
    with (root / (name + '-cli.json')).open('x') as log:
        subprocess.run([sys.executable, '-B', *command, '--submission', source, *common, '--out', str(out)],
                       stdout=log, check=True)
    r = json.loads(out.read_bytes())
    if (r['status'] != 'complete' or r['games'] != 392 or r['infraErrors'] or r['lockDirectory'] != locks
            or r['scoringProposal'] != 'P1' or r['scoringStatus'] != 'frozen for ladder 1.0.0 (user 2026-11-26)'):
        raise SystemExit('评分未完成或使用了不同的锁目录、计分方案。')
    return {k: r[k] for k in (*keys, 'games', 'wallSeconds')}

def diff(left, right):
    return {k: left[k] - right[k] for k in keys}

def within(delta):
    return all(abs(value) <= .03 for value in delta.values())

bases = {}
for bot, expected in [('Z-idle', 0.000000), ('M-balanced', 0.452381)]:
    observed = grade('bots/public/' + bot, bot + '-idle')
    delta = observed['headlineOutcomeOnly'] - expected
    bases[bot] = {**observed, 'outcomeDeltaFromDev': delta}
    if abs(delta) > .03:
        raise SystemExit(bot + ' 的胜负主分与开发机相差超过 0.03。')

heavy = json.loads(Path('data/phase-c/release-fix.json').read_bytes())['noiseReference']
[source] = ['private/' + m['source'] for level in json.loads(Path(ladder).read_bytes())['levels']
            for m in level['members'] if m['code'] == heavy['code']]
idle = grade(source, 'heavy-idle')
loaded = grade(source, 'heavy-loaded', loaded=True)
first = diff(loaded, idle)
repeat = None if within(first) else grade(source, 'heavy-idle-repeat')
second = diff(loaded, repeat) if repeat is not None else None
passed = within(second if second is not None else first)
summary = {'publicBaselines': bases, 'heavy': heavy['code'], 'devBaseline': {k: heavy[k] for k in keys},
           'idle': idle, 'loaded': loaded, 'repeatIdle': repeat, 'idleMinusDev': diff(idle, heavy),
           'loadedMinusIdle': first, 'loadedMinusRepeatIdle': second, 'passed': passed}
(root/'score-checks.json').write_text(json.dumps(summary, indent=2) + '\n')
if not passed:
    raise SystemExit('负载与空闲的主分差超过 0.03。保留三次评分原件。')
PY
```

公开锚的胜负主分只同开发机对照。负载用六个纯 CPU 忙循环。最重成员是 E-r02，开发机自评 `headline=0.603547`、`headlineOutcomeOnly=0.599817`；[聚合数据](data/phase-c/release-fix.json)保留完整精度。跨机分差只报告。负载对本机首个空闲评分超差时才补第二个空闲评分，按负载对第二次的两种分差判定，三次都保留。

## 6. 准备并验证任务工作区

这一步用新建的验证工作区。正式发放时另行按白名单导出，并附同样两把锁，但不预填参赛 `bot/`。

```sh
: "${HRW_REVIEWED_COMMIT:?}" "${HRW_HOME:?}" "${HRW_PACKAGE:?}" "${HRW_LOCK_DIR:?}"
set -eu
umask 077
cd "$HRW_HOME"
export PATH="$HRW_HOME/.venv/bin:$PATH"
workspace="${HRW_HOME}-task-check"
.venv/bin/python -B -m tools.prepare_author_workspace --role release --out "$workspace" \
  > private/migration/public-export.json
for jobs in 1 6; do
  cp "private/host-bench/timing-lock-jobs$jobs.json" "$workspace/timing-lock-jobs$jobs.json"
  cmp "private/host-bench/timing-lock-jobs$jobs.json" "$workspace/timing-lock-jobs$jobs.json"
done
cd "$workspace"
sha256sum --check --quiet PUBLIC-MANIFEST.sha256
cp -R sdk/cpp/example/. bot/
"$HRW_HOME/.venv/bin/python" -B - <<'PY'
import json, re, subprocess
from pathlib import Path
[commands] = re.findall(r'^```sh\n(.*?)^```$', Path('README.md').read_text(encoding='utf-8'), re.M | re.S)
subprocess.run(['bash', '-e'], input=commands, text=True, check=True)
[check] = Path('runs/check').glob('*/check.json')
r = json.loads(check.read_bytes())
t = json.loads(Path('runs/example/summary.json').read_bytes())
if not r['passed'] or r['sandbox'] != 'bwrap' or t['completed'] != 2 or t['tasks'] != 2 or t['status'] != 'complete':
    raise SystemExit('公开包的 SDK 检查或两局示例未通过。')
PY
```

锁是宿主随后附的文件，不进公开材料清单。命令块从导出包 `README.md` 原样执行：短检查通过，再完成两局 jobs 1 示例。

## 7. 宿主练习赛

在验证工作区用 M-balanced 副本演练。正式任务由宿主在两阶段之间执行同一条 `scrimmage` 命令，输入换成第一阶段已冻结的提交；不要把宿主原始运行目录放进任务工作区。

```sh
: "${HRW_REVIEWED_COMMIT:?}" "${HRW_HOME:?}" "${HRW_PACKAGE:?}" "${HRW_LOCK_DIR:?}"
set -eu
umask 077
cd "$HRW_HOME"
workspace="${HRW_HOME}-task-check"
test ! -e private/migration/step6-sdk-bot
mv "$workspace/bot" private/migration/step6-sdk-bot
mkdir -m 700 "$workspace/bot"
cp -R bots/public/M-balanced/. "$workspace/bot/"
.venv/bin/python -B -m arena scrimmage --submission "$workspace/bot" --jobs 6 \
  --fixed-timing private/host-bench/timing-lock-jobs6.json --out "$workspace/scrimmage" \
  > private/migration/public-scrimmage.json
test -f "$workspace/scrimmage/results.json"
test -f "$workspace/scrimmage/results.md"
test -f "$workspace/scrimmage/turns.csv"
```

预期 12 局全部完成，生成上述三个文件及至多三份败局回放；不输出计分细节或锁目录。

## 用时

| 步骤 | 开发机完整演练 | 评测机预留 |
| --- | ---: | --- |
| 1 准备 | 待测 | 5–15 分钟，不含安装和拷贝等待 |
| 2 测试 | 待测 | 5–10 分钟 |
| 3 两把锁 | 待测 | 5–20 分钟 |
| 4 相邻复核 | 待测 | 10–45 分钟 |
| 5 评分与噪声 | 待测 | 每次评分预留至多 45 分钟，通常 4 次，超差才做第 5 次 |
| 6 公开工作区 | 待测 | 5–10 分钟 |
| 7 练习赛 | 待测 | 2–10 分钟 |

## 迁移通过条件

| 步骤 | 必须满足 |
| --- | --- |
| 2 测试 | 418 项，0 失败和 0 错误；只能因上列理由跳过指定用例。开发机演练 0 跳过。 |
| 4 相邻复核 | 身份相符、1,344 局齐、`infraErrors=0`、10 个判定级对全部过线、故障局不超过基准加 2、`passed=true`；`lockDirectory` 等于 `HRW_LOCK_DIR`。 |
| 5 评分与噪声 | 每轮 392 局、无框架缺局；Z-idle / M-balanced 的胜负主分分别与 0.000000 / 0.452381 相差 ≤0.03。负载与合格空闲对照的 `headline`、`headlineOutcomeOnly` 均相差 ≤0.03；跨机差只报告。 |
| 6 工作区 | `release` 角色导出成功，两把锁按固定名原样附入，清单全部核对；README 的短检查和两局示例原样运行并通过。 |
