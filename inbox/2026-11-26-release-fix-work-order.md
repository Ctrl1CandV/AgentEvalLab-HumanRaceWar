# CA 工单 2026-11-26（二）：1.0.0 发布修正和开发机迁移演练

- **给：** 综合会话。
- **来自：** 评测负责人的审查会话。
- **审查版本：** 主仓库 `94f1a77`。
- **性质：** 实施工单。需要判断的事都已经定好，写在下面；你照做，不需要再做设计决定。

## 目标

修好迁移相关的问题，把第 2 版 private 发布包和迁移说明做扎实，并在开发机一个全新的目录里，严格按迁移说明完整演练一遍。演练通过后交给 CA，由 CA 在评测机迁移复核，通过后判定可以输出第一版。

**本轮的验收门槛比上一轮高。** 第十节的每一项都必须满足，不能"记录后继续"。

## 最终审查结论

上一份工单的交付整体合格：阶梯 1.0.0、评分路径、过程分检查、公开导出和保密边界都通过了 CA 的核对。下面几处问题需要修：

1. **`calibrate --mode adjacent` 在任何机器上都会判不通过。** 它拿只用相邻级对局、只用 12 张图的重拟合，去比阶梯文件里用全部对局拟合出的级距。L0 在相邻数据里全输，会变成 −∞；数据量减半也会让级距系统性地偏移。这个比较方法是 CA 上一份工单写错的，不是你的实现错误。
2. **迁移说明缺少给被测模型本地测试用的 jobs 1 时限锁。** 任务说明里写的是 `/path/to/host-jobs1-lock.json` 占位。
3. **锁目录依赖 `TMPDIR`。** 评测机上各个命令的 `TMPDIR` 可能不同，CPU 租用和"一次只评一个提交"的锁会失效。CA 自己的会话每次 `TMPDIR` 都不同，`/tmp` 还是只读。
4. **迁移时的噪声测试用的是 M-balanced。** 它每回合用的 CPU 很少，测不出负载的影响。
5. **评测机上有两个测试因为环境原因失败。**
   - `test_empty_tmpdir_falls_back_to_tmp`：评测机的沙箱里 `/tmp` 是只读的。
   - `test_readonly_filesystems_and_anonymous_file_bypasses`：评测机用的 conda-forge Python 3.13.15 没有 `os.memfd_create`，探针 bot 抛出 AttributeError。这不是隔离漏洞。
6. **astra 提交在 1.0.0 下的分数缺少逐级数据。** 第 6 条第二阶段提交从 12 级时的 0.9187 降到 0.8571，目前说不清下降来自哪里。

## 用户裁定（2026-11-26，已确认）

1. **B 阶段按"1.0.0 带披露"接受。** 第 7 条 Z-harass 对 L8（0.146），以及第 8 条 holdout 中"Z-harass 胜过其他每种单一打法"一项，都披露，不修。
2. **第三次验证中如有模型主分达到或超过 0.9：** 照常计分，不阻塞验证，报告注明"已到 HRW 1.0.0 的上限"。下一版本靠加深游戏（增加复杂度）来拉开区分，不靠加级。
3. **P1 冻结为 1.0.0 的主分方案。** 以后的实验可以修正公式。修正时另起方案号（P2、P3……），旧结果从逐局原始数据重算，旧报告不改。第 6 条仍按只看胜负判定。
4. **批准本修正轮，验收门槛从严。**
5. **AgentEvalLab 的接入由 CA 审查会话负责**，在迁移复核之后进行，本工单不涉及。

## 零、开工

1. `cd ~/projects/AgentEvalLab-HumanRaceWar && git pull --ff-only`。
2. 读本文件全文，再读 `AGENTS.md`、`STATUS.md`、`MIGRATION.md`、`reports/phase-C.md`、`reports/phase-B-ladder-1.0.md`，以及上一份工单 `inbox/2026-11-26-release-work-order.md` 的第三、六、七、九节。
3. 读 `arena/calibrate.py`、`arena/grade.py`、`arena/core/resources.py`、`tools/release_noise.py`、`tools/freeze_release_timing.py`、`arena/scoring.py`、`arena/scoring.json`、`package/release-README.md`。
4. 在评测 worktree 里找到并记下：
   - 开发 WSL 的正式预算锁；
   - 第四节 38 次自评的原件（每份的报告和 `games.json`）；
   - 第 6 条测试时给 astra 的工作区里提供了哪几把时限锁（jobs 1、jobs 6）。
5. 两个 worktree 都检查 `git status`，确认 `core.hooksPath=.githooks`。
6. 先用几句话向用户说明你的理解，然后直接开始。

## 工作顺序

| 组 | 内容 | 依赖 |
|---|---|---|
| 1 | 第一节代码和测试；第二、四、五节；第六节（不打新局） | 无 |
| 2 | 第一节 R1、R2 两次开发机运行；第三节选出最重的成员 | 组 1 的 `calibrate` 改完 |
| 3 | 第七节文档；第八节第 2 版发布包；推送 main（这次推送只为演练，不交审） | 组 1、2 |
| 4 | 第九节开发机完整演练 | 组 3 |
| 5 | 演练结果写进报告和迁移说明；最后推送；告诉用户 | 组 4 |

所有 arena 命令串行执行。演练期间开发机上不跑其他 arena 命令。

## 一、相邻复核改为对照开发机基准

### 1.1 改 `calibrate`

**新参数：**

- `--write-reference PATH`：写一份新基准。PATH 必须在 `private/` 下，且文件不能已经存在。
- `--reference PATH`：和已有基准比较，默认 `private/ladder/adjacent-reference-1.0.0.json`。
- 两个参数互斥。

**对局：** 和现在完全一样，相邻级所有成员配对，阶梯文件里的 12 张 calibration 图，双座，种子不变，共 56 对、1,344 局。

**基准文件的内容：**

- `schemaVersion: 1`、`ladderVersion`、`engineVersion`；
- `ladderSha256`：阶梯文件的字节摘要；
- `calibrationMapsSha256`：12 张图的摘要，按阶梯文件里的顺序；
- `sourceHashes`：全部成员源码摘要；
- `timingLock`：锁的 sha256、jobs、`speedFactor`，以及每回合、初始化、储备的限额；
- `games`：每局的 `taskId`、两名成员代号、地图摘要、座位、`winner`、结束原因、回合数、双方故障；
- `ratings`：相邻拟合的 Elo，有限值写数字，不可识别的写 `"+infinity"`、`"-infinity"` 或 `null`；
- `pairs`：12 个相邻级对，每对写：
  - `eloGap`：上一级成员平均 Elo 减下一级的，任一成员不是有限值时写 `null`；
  - `scoreRate`：这对级之间所有对局里，上一级的平均得分（胜 1、平 0.5、负 0）；
  - `games`：这对级之间的局数；
- `faultGames`：有任何一方故障（编译失败、启动失败、崩溃、超时、无效输出）的局数，并列出它们的 `taskId`。

**比较规则（`--reference`）：**

1. 先核对 `ladderSha256`、`calibrationMapsSha256`、`sourceHashes`、`engineVersion`。任何一项不一致都报配置错误并退出，不算作一次比较。
2. 每个相邻级对都计算：
   - `eloDelta`：本次 `eloGap` 减去基准的 `eloGap`。只在两边都是有限值时计算，否则写 `null`。
   - `scoreDelta`：本次 `scoreRate` 减去基准的 `scoreRate`。总能算出来。
3. L0→L1 和 L1→L2 只作诊断（`gate: false`），列出数值，不参与判定。这和第 1–3 条的规则一致。
4. L2→L3 及以上的 10 对参与判定（`gate: true`），满足下面任一条件即算一致：
   - 两边的 `eloGap` 都是有限值，且 |`eloDelta`| ≤ 50；
   - 任一边的 `eloGap` 不是有限值，且 |`scoreDelta`| ≤ 0.05。
5. `gameAgreement`：按 `taskId` 逐局比较 `winner` 是否和基准相同，平局也算一种结果。分别按级对和总体给出相同局数和比例。
6. `passed` 需要同时满足：
   - 1,344 局全部完成，`infraErrors` 为 0；
   - 10 个参与判定的级对全部一致；
   - 本次 `faultGames` 不超过基准的 `faultGames` 加 2。
7. 结果文件 `results.json` 写逐级对比表、`gameAgreement`、故障局和 `passed`，另写 `lockDirectory`（见第二节）。
8. 退出码：通过为 0；未通过或不完整为 2；配置错误照现有做法报错。

**删除：** `calibrate` 不再读取阶梯文件里的 `calibration.gaps`。阶梯文件本身一个字节都不改。

### 1.2 开发机上跑两次

两次都在评测 worktree 中运行，使用开发 WSL 的正式预算锁和 jobs 6。

- **R1：** `--write-reference private/ladder/adjacent-reference-1.0.0.json`，1,344 局。
- **R2：** 用 `--reference` 和 R1 比较，`--out` 指向新目录，1,344 局。
- **R2 必须 `passed`。** 不通过是第十一节的停点。
- **R2 的 `gameAgreement`** 照实写进报告。低于 99% 也只写明，不停。
- **旧规则的结果：** 用 R1 的相邻拟合级距，按旧规则和 `ladder.calibration.gaps` 逐对比较（±50），列成一张表写进报告，说明旧规则在开发机上也会判不通过。这一项不打新局。

### 1.3 测试（加进 `tools/run_tests.py`）

用合成结果，不打真实对局：

- 写出基准再读回，内容不变；目标文件已存在时拒绝写入；
- `ladderSha256`、地图摘要、源码摘要任一不一致时报配置错误；
- L0 为 −∞ 时，L0→L1 只诊断，不影响 `passed`；
- 参与判定的级对出现无穷值时，改用 `scoreDelta`：差 0.05 时通过，差 0.0501 时不通过；
- `eloDelta` 正好 50 时通过，50.01 时不通过；
- 少一局时 `passed` 为 false；
- 故障局比基准多 2 局时通过，多 3 局时不通过；
- `gameAgreement` 计数正确，平局也要覆盖。

## 二、锁目录、时限锁和迁移说明

### 2.1 锁目录 `HRW_LOCK_DIR`

**`arena/core/resources.py` 的 `lock_directory()`：**

- 环境变量 `HRW_LOCK_DIR` 非空时：
  - 必须是绝对路径，否则报错；
  - 照原样使用这个目录，不再加 `hrw-cpu-locks-<uid>` 后缀；
  - 目录不存在时，用权限 0700 创建，允许连父目录一起创建；
  - 属主和权限的检查和现在相同。
- 变量为空或未设置时，行为和现在完全一样。

**其他要求：**

- CPU 租用、编译锁和评分锁都必须经过 `lock_directory()`。如果发现有锁绕开了它，改成经过它。
- `grade` 和 `calibrate` 的结果文件里写 `lockDirectory`（绝对路径）。`scrimmage` 的输出会放进被测模型的工作区，不写这一项。

**测试：**

- 设置变量后，CPU 租用和评分锁都落在这个目录；
- 相对路径被拒绝；
- 变量为空时，回到 `TMPDIR` 下的原目录。

### 2.2 时限锁

- **评测机上测两把锁：**
  - jobs 6：冻结为 `private/host-bench/timing-lock-jobs6.json`（原名 `timing-lock.json`），用于 `grade`、`calibrate`、`scrimmage` 和噪声测试；
  - jobs 1：先 `bench --jobs 1`，再 `tools.freeze_release_timing --jobs 1`，冻结为 `private/host-bench/timing-lock-jobs1.json`。
- **被测模型的工作区：** 宿主把 jobs 1 锁复制到工作区根目录，固定命名为 `timing-lock-jobs1.json`。
- **跟第 6 条保持一致：** 如果第 6 条时 astra 的工作区里还给过 jobs 6 锁，就照样提供 `timing-lock-jobs6.json`，文档里两把都写上；否则只提供 jobs 1 锁。查不清的话按只提供 jobs 1 处理。用的是哪种，在报告里写明并说明依据。
- **`package/release-README.md`：**
  - 示例命令改为 `--fixed-timing timing-lock-jobs1.json`；
  - 写明"时限锁由宿主放在工作区根目录，不在 `PUBLIC-MANIFEST.sha256` 里；不要改名、移动或修改"；
  - 两个阶段的任务说明里如果提到锁的路径，同样改掉，其他措辞不动。

### 2.3 重写 `MIGRATION.md`

**开头先定义四个变量，后面每段命令都先检查它们已经设置：**

| 变量 | 含义 | 默认值 |
|---|---|---|
| `HRW_REVIEWED_COMMIT` | CA 确认的完整提交号 | 无，必须指定 |
| `HRW_HOME` | 本次迁移用的全新 checkout | `$HOME/projects/HRW-1.0.0` |
| `HRW_PACKAGE` | private 发布包 | `$HOME/hrw-release/humanracewar-1.0.0-private-2.tar` |
| `HRW_LOCK_DIR` | 所有 HRW 命令共用的锁目录 | `$HOME/.local/state/hrw-locks` |

`HRW_HOME` 在开始时必须不存在。评测机上的 `~/projects/AgentEvalLab-HumanRaceWar` 是 CA 的审查仓库，迁移不碰它。

**步骤：**

1. **准备：** clone 到 `HRW_HOME`，切到 `HRW_REVIEWED_COMMIT` 并核对；建 venv，核对版本；校验 tar 的 sha256；解包到 `private/`。
2. **测试：** `tools/run_tests.py`。
   - 写明开发机上的测试项数。
   - 列出允许跳过的测试名称和原因：只有 `/tmp` 不可写时那一项，以及现有的、测试里明确列出的 WSL 专用锁投影项。
   - 其他任何失败或跳过，都停止迁移。
3. **测速：** 冻结两把锁，见 2.2。
4. **相邻复核：** 使用新规则，参数为 `--reference private/ladder/adjacent-reference-1.0.0.json`，判定方法见第一节。另核对 `lockDirectory` 等于 `HRW_LOCK_DIR`。
5. **评分核对：**
   - Z-idle 和 M-balanced 的 `headlineOutcomeOnly` 与开发机的 0.000000、0.452381 相比，绝对差不超过 0.03；
   - 噪声测试按第三节。
6. **准备任务工作区：**
   - 用 `tools/prepare_author_workspace.py --role release` 导出到一个新目录；
   - 按 2.2 复制时限锁；
   - `sha256sum --check PUBLIC-MANIFEST.sha256`；
   - 原样运行 `README.md` 里的 `check` 和小规模 `tournament` 示例。
7. **练习赛：** 写明宿主在两个阶段之间运行 `scrimmage` 的命令，使用 jobs 6 锁和 `HRW_LOCK_DIR`。

**另外写明：**

- 每一步在开发机演练时的实际用时（第九节测得），以及在评测机上应预留的时间；
- 文末放一张"迁移通过条件"表，列出第 2、4、5、6 步的全部判定条件。

## 三、噪声测试改用最重的阶梯成员

- **选人：**
  - 用第四节 38 次自评中阶梯成员的那 28 份；
  - 对每名成员，在它作为提交的全部对局里，把提交一方的 `botCpuNs` 求和，再除以这些对局的回合数之和，得到每回合 CPU；
  - 取最大的那名成员。
- **公开范围：** 报告只写入选成员的代号和它每回合的 CPU 毫秒数。全部成员的数值只留在 `private/`。
- **噪声测试：** `tools/release_noise.py` 的做法不变，仍用 6 个纯 CPU 忙循环、跑满整个评分过程。迁移说明改为测这名成员。
- **判定：**
  - 同一台机器上先做空闲评分，再做负载评分。负载结果和空闲结果相比，`headline` 和 `headlineOutcomeOnly` 的绝对差都不超过 0.03，才算通过。
  - 超出时，再做一次空闲评分。负载结果和第二次空闲结果的两种差都不超过 0.03，才算通过；否则不通过。三份原件都保留。
- **对照数值：**
  - 迁移说明列出这名成员在开发机第四节自评中的两种主分，作为对照；
  - 评测机上空闲评分与开发机数值的差只报告，不作判定；
  - 跨机器的强度一致性由相邻复核负责。
- **M-balanced：** 只保留第 5 步的空闲核对，不再用于噪声测试。

## 四、两个测试

- **`test_readonly_filesystems_and_anonymous_file_bypasses`：**
  - 探针里有 `os.memfd_create` 时，照现在的写法；
  - 没有时，用 `ctypes` 直接调用 memfd_create 系统调用（x86_64 是 319，aarch64 是 279），要求返回 −1 且 errno 为 EPERM；
  - 其他架构跳过这一项检查，并写明原因；
  - 用例里的其他检查不变。
- **`test_empty_tmpdir_falls_back_to_tmp`：**
  - 先试着在 `/tmp` 建一个临时文件，失败就跳过，跳过原因写"/tmp 不可写"；
  - 能写时，断言和现在相同。
- **开发机上这两项都必须真正运行并通过，不能跳过。**

## 五、冻结 P1

- **`arena/scoring.json`：**
  - `status` 改为 `"frozen for ladder 1.0.0 (user 2026-11-26)"`；
  - `proposal` 保持 `"P1"`；
  - 数值一个都不改。
- **`grade` 的报告：** 新增 `scoringProposal`、`scoringStatus` 两个字段，内容取自配置文件。
- **重算核对：** 用冻结后的配置，从第四节 38 份 `games.json` 重算全部主分。`headline`、`headlineOutcomeOnly`、各级分和区间必须和原报告逐位相同，不打新局。配置文件的 sha256 会变，报告里写明新旧两个值。
- **`data/phase-c/release-evaluation.json`：** `scoringProposalFrozen` 改为 true，并加上 `scoringFrozenBy: "user 2026-11-26"`。
- **测试：** 配置状态和方案号能出现在 `grade` 的报告里。

## 六、astra 逐级诊断（不打新局）

- **数据来源：** 四份 astra 提交在第四节的自评结果。
- **写进 `data/phase-c/release-evaluation.json`：** 在 `astraDiagnostics` 的每一份下面加两项：
  - `levelOutcome`：13 级的只看胜负级分；
  - `levelHeadline`：13 级的 P1 级分。
- **和 12 级时的正式结果对照：**
  - 第 6 条两份：对照 `data/standard-budget.json` 的 `tierMeans`；
  - 第 5 条两份：对照第 5 条报告里的逐级结果；
  - 逐级给出 L0–L11 的差。
- **核对赛程：** 比较 1.0.0 和 12 级阶梯文件中 L0–L11 各成员的 grading 图和座位是否相同。
  - 相同，且 L0–L11 的差全为 0：写"L0–L11 的赛程和结果不变，主分变化全部来自新增的 L12"。
  - 否则写明赛程哪里变了、各级分变化多少。
- **写进 `reports/phase-C.md`：** 一张表加两三句结论，并注明哪两份被天花板作者当作可见参照、针对过。
- **公开范围：** 只写级分，不写地图、种子或逐局结果。

## 七、文档和报告

### DESIGN 修改

照下面写，写明"用户 2026-11-26 裁定"：

- **11.4：** 迁移复核改为对照开发机相邻基准，规则照第一节写全，包括 L0→L1、L1→L2 只作诊断，以及无穷值时改比得分率。
- **11.5 第 6 条：** 第三次验证中达到或超过 0.9 时的处理，照用户裁定第 2 条。
- **11.5 第 8 条：** holdout 中"单一打法"一项不通过，已披露，用户接受。
- **12.3：** P1 冻结为 1.0.0 的方案；以后修正公式另起方案号，从逐局数据重算，旧报告不改。
- **第 17 节：** B 按"1.0.0 带披露"接受。C 在本修正轮完成、CA 迁移复核通过后，判定可以输出第一版。

### 报告和状态

- **`reports/phase-C.md`：** 新增"发布修正"一节，内容包括：
  - 改了什么；
  - R1 和 R2 的结果，以及旧规则的对照表；
  - 选出的最重成员；
  - P1 重算核对；
  - astra 逐级诊断；
  - 开发机演练结果和各步用时；
  - 第 2 版发布包的 sha256。
- **`reports/phase-B-ladder-1.0.md`：** 开头加一句"用户 2026-11-26 按带披露接受"。
- **数据：** 演练和修正的聚合放进 `data/phase-c/release-fix.json`，不写地图、种子或逐局结果。
- **其他：** 更新 `STATUS.md` 和 `reports/README.md`。
- **写法：** 先用两三句话写清结果，再列表，用完整的中文句子。

## 八、发布包第 2 版

- **内容：** 在上一版的基础上，加入 `private/ladder/adjacent-reference-1.0.0.json`，其他内容不变。
- **命名和位置：** `~/hrw-release/humanracewar-1.0.0-private-2.tar`，附 `humanracewar-1.0.0-private-2.tar.sha256`。
- **旧包：** 把旧的 `humanracewar-1.0.0-private.tar` 和它的 `.sha256` 移到 `~/hrw-release/superseded/`，不删除。
- **核对：** 逐项按字节核对；确认不含回放、作者档案和基准以外的逐局记录；跑发布检查。

## 九、开发机完整演练

这一节是本轮验收的核心：迁移说明必须能照着原样执行成功。

1. **前提：** 组 3 已推送。`HRW_REVIEWED_COMMIT` 设为推送后的远端提交号。
2. **变量：**
   - `HRW_HOME` 设为全新目录 `~/hrw-rehearsal-1/HRW-1.0.0`，第 n 次演练用 `~/hrw-rehearsal-n/`，旧目录不删；
   - `HRW_PACKAGE` 指向第 2 版发布包；
   - `HRW_LOCK_DIR` 用迁移说明的默认值。
3. **执行：** 从 `MIGRATION.md` 第 1 步到第 7 步，逐段复制命令执行，不手工补任何步骤，不改任何命令。
   - 第 6 步用导出的工作区；
   - 第 7 步把 M-balanced 的副本放进这个工作区的 `bot/` 当作提交。
4. **允许的差异：** 演练在开发机上做，测出的两把锁只放在演练目录的 `private/` 里，不替换开发 WSL 的正式锁。
5. **记录：** 每一步的墙钟时间。
6. **通过条件：** "迁移通过条件"表里的每一条都满足。
7. **中途出问题时：** 文档错了、命令跑不通、判定没过，只要原因是你能修的代码或文档问题，就修复、提交、推送；如果 private 内容变了，就重打发布包；然后换一个新的 `hrw-rehearsal-n` 目录，从第 1 步重来。
8. **作数的演练：** 报告引用的必须是最后一次一步不停、全部通过的演练。在那之后，只允许改迁移说明里的用时数字、报告、`STATUS.md` 和 `data/`。代码或命令有任何改动，都要重新演练。

## 十、验收标准（全部满足才算完成）

| # | 项 | 标准 |
|---|---|---|
| 1 | 完整测试 | 开发机上 0 失败、0 错误、0 跳过，报告总数 |
| 2 | 新测试 | 1.3、2.1、四、五节列出的用例都在，并且通过 |
| 3 | 基准 | R1 已写出；R2 对 R1 `passed`；`gameAgreement` 已报告 |
| 4 | 旧规则对照 | 表已写进报告 |
| 5 | P1 重算 | 38 份全部逐位相同 |
| 6 | 回放兼容 | 重新核对 104 份旧回放，逐字节一致 |
| 7 | 公开导出 | 用 release 角色重新导出；新的清单摘要写进报告；发布检查通过，没有隐藏内容 |
| 8 | 发布包 | 第 2 版已按字节核对，含基准文件；旧包已移到 `superseded/` |
| 9 | 演练 | 最后一次演练一步不停、全部通过；各步用时写进迁移说明 |
| 10 | Git | main 已推送，核对远端提交号；两个 worktree 的工作区干净 |

## 十一、上限、停点和默认做法

### 上限

本工单新增对局合计不超过 10,000 局，预计约 5,600 局：

| 项 | 局数 |
|---|---:|
| R1、R2 | 2,688 |
| 一次演练：相邻复核 | 1,344 |
| 一次演练：Z-idle、M-balanced、最重成员的空闲评分和负载评分 | 1,568 |
| 一次演练：练习赛 | 12 |
| 测试用局 | 少量 |

演练需要重来时，每次约增加 2,900 局。

### 停点（只有这些）

1. R2 对 R1 不通过（同一台机器、同一把锁也对不上）。
2. 演练中的相邻复核不通过，而且原因不是你能修的代码或文档问题。例如用新测的锁打出来的级距差超过 ±50。
3. 任何改动会改变 standard-1 的对局结果（回放核对不一致），而且你修不好。
4. 需要改规则、协议、计分公式，或改本工单没有授权的门槛。
5. 超出上限，或出现自己修不了的技术故障。
6. 全部做完。推送 main，核对远端提交号，然后告诉用户四件事：
   - 可以交 CA 做迁移复核；
   - 最终提交号；
   - 第 2 版发布包的路径和 sha256；
   - 需要拷到评测机的文件：只有 `humanracewar-1.0.0-private-2.tar` 和它的 `.sha256`，其余内容都在 GitHub 上。

停在 1、2 时，照实报告数据，不自行改设计。

### 不是停点

- R2 的 `gameAgreement` 低于 99%：照实写，继续。
- 最重成员在开发机演练中空闲评分与正式自评的差：只报告。
- 第 6 条工作区查不清给过哪几把锁：按只提供 jobs 1 处理，写明。

### 默认做法

遇到本工单没写到的小问题，选不改变任何已有结果、不改规则的做法，在报告里写一句，继续。

### 保密和运行

- **保密：** 隐藏内容不进公开文件；不读隐藏 bot 的源码。
- **运行：** 只在离线 bwrap 里跑；R1、R2 用开发 WSL 的正式锁，不重测速。
- **Git：** 小步本地提交，不改写历史，不用 `--no-verify`。
