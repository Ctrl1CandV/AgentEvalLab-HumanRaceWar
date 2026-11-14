# Claude对接/评测会话交接

用户在T6开发期间明确拆分：当前GPT只做公共工具；新增GPT会话专门对接Claude并统一评测；Claude继续在自己的工作区写bot。此分工取代2026-11-13文件中旧“两工作者”表，其他预算、源码保密和停点不变。用户自行开启新会话，工具会话不代开、不转交作者源码。

## 工作区与唯一写入者

| 角色 | 工作区/分支 | 写入范围 |
|---|---|---|
| 工具GPT（原会话） | `~/projects/AgentEvalLab-HumanRaceWar` / `main` | T6公共代码、测试、文档及本worktree的Git/STATUS/清单/私有日志 |
| 对接/评测GPT（新会话） | `~/projects/HRW-claude-eval` / `claude-evaluation` | 自己worktree的private、汇总/报告、STATUS、清单、Git；另可写作者`handoff/in/`反馈 |
| Claude作者 | `~/projects/HRW-claude` | 自己的bot、笔记、自测和交付 |

两个GPT不共用index、私有总账或STATUS，不直接写对方worktree；不需要旧lane、全局冻结或逐包释放窗口。对接分支不自动合并到main，不推送；公开汇总的最终集成由用户安排。工具会话不得把未验收T6代码接到计分路径。

## 新会话首次准备（零运行）

1. 先读本交接、原裁定和主仓库`STATUS.md`。不访问作者源码、NOTES或自测输出；作者已开始，但尚未收到交付通知。
2. 核`git worktree list`和目标是否存在。若均不存在，从主仓库执行：
   ```sh
   git worktree add -b claude-evaluation /home/claude-dev/projects/HRW-claude-eval a919da76020a64a3c2dd24be06ded015beda2391
   ```
   目标/分支已存在就核对，不覆盖、不force、不reset/stash。若会话工具仍以主仓库为默认cwd，之后所有命令显式`cd /home/claude-dev/projects/HRW-claude-eval`，文件读写用新worktree绝对路径，避免误写主目录。该基线含T1–T4和旧目录删除记录，不含当前未验收的T6工具；arena/SDK仍是已验收字节。后续只在新worktree工作，不修改共享Git配置。现有hooks应为`.githooks`。
3. 读新worktree的AGENTS、DESIGN、BRIEF，按本用户新分工覆盖其旧角色描述。使用Python3.13；可从新worktree调用主仓库`.venv/bin/python`的绝对路径，先只读import验证arena确实来自新worktree。不要复制venv、认证或个人配置，也不建指向主仓库private的链接。
4. 只从主仓库复制最小已冻结输入包，逐文件按字节核摘要，不读取任何bot实现：
   - `private/phase-b/claude-workspace-20261113/protocol.json`、`PROTOCOL.md`；摘要与`data/phase-b/claude-workspace.json`核对。
   - `private/ladder/gpt-final-20261113/final.json`。
   - 协议列出的80张dev地图、3个私有固定对手A-r02/E-r02/C-r02及jobs6原机器锁；其余5个对手用本worktree公开目录，逐一核协议源码摘要。
   建议输入包置于新worktree的`private/ladder/claude-eval-inputs/`，参考bot各自叶目录内只放原源码，元数据另放外层。原协议字节保留不改；另写本地路径映射及执行绑定，明确仅改存储路径，不改SHA、规则、SDK、种子、锁、对手、地图或门槛。保持原maps有序列表和selectionStage，不用目录glob重排替代40+40事前划分。先封存输入包，用本worktree的`tools/archive_round.py`建立独立轮清单/总账；不要复制或覆盖主仓库HIDDEN/ledger，不重扫旧全库。
5. 首次准备完成后停止等待用户明确通知交付；不因作者目录有文件就自动接收、启动check或评测。不得读取/恢复已删除的DeepSeek/pilot工作区或运行其私有工具。

## 接收工具的已知兼容边界

旧`tools/receive_author_delivery.py`只支持单个`bot/`，且旧清单校验只允许`bot/*`；新版Claude任务书允许`bots/<名字>/`及覆盖笔记等交付文件的清单。不要把合法新版包误判为bot失败，也不要要求作者删改原清单迎合旧接口。可在自己的private中用小型纯字节保全脚本按T5的路径/类型/体积/SHA/二读边界原样归档，保留脚本和收条；它不做计分、调度或策略分析。通用接口兼容问题以不含源码的摘要交工具会话，不私建控制器。实际合规/胜负证据仍来自旧已验收check/tournament。

## 每次用户通知后做T5

- 只按字节接收`handoff/out/r<NN>/`：核路径、普通文件、体积、SHA256SUMS及二读一致性，副本只放本worktree的`private/ladder/claude/<代号>/`。禁止源码阅读、grep/AST/import、代改、转交其他模型；不打开带作者源码正文的编译日志。作者需自行修复自己的代码。
- 用旧已验收check、标准tournament、原机器锁和已冻结协议；不用本次未验收T6工具，不另造私有控制器、资格轮、CPU份额档或策略修复。沿用原TMPDIR/CPU/编译锁，bot和C++编译只经离线bwrap，不回退plain、不测速。用户确认作者停止大批自测后才运行；核不到资源就等或停，不抢锁。
- 对手、地图有序列表/事前划分、双座、种子和机器锁只以原私有协议为准，不在此公开转录；不混入其他轮矩阵或擅换对手。
- 首版每候选1280局；后续先对自己的保留版做原两阶段直接门，再做池分数下降门。具体阈值查原协议，不在反馈或本公开交接中泄露隐藏细节。保留版须有同协议完整可比池结果才可复用，正常新增1440局；缺失/协议不同不能暗跑2720局，先停报。
- 每轮最多3候选，每候选上限2080局、对局墙钟2小时、0测速。bot故障按原规则计负；框架标准重试每局最多3次，仍失败停报，不删失败或默许新额度。不复用旧1864/4400等余额，不改E或GPT三线。
- 临时BT和共同地图簇bootstrap的参数按原私有协议，保留分离/不可识别抽样，不伪计数/截断；CPU从实际回放聚合。每份新完成回放引擎验证一次，复用标准恢复审计凭据；不要重步已审计旧回放。
- 反馈只写作者`handoff/in/feedback-r<NN>.md`：check、总分、公开对手逐对/隐藏对手合计、临时Elo/区间、故障/超时、CPU中位/p99/最大、结束方式和同作者取舍。禁止隐藏输入、回放、逐局表、隐藏逐对弱点及其他作者实现。
- 模型版本、真实会话数、自报自测/调参局数与统一评测局数分开记录；不知道就写未知，不把作者自报当评测证据或独立性证明。每轮反馈后停止；连续采纳两次或临时Elo约M+600时停交CA，再安排风格/档位。

公共框架问题只提供不含作者源码的问题摘要给工具会话，不自行改框架/SDK/规则。所有原始材料、失败和索引留本机private；公开仅一页报告/聚合，本地提交自己的分支，不推送。B未完成，C未启动。当前Claude作者不得兼任阅读主仓库的CA审查会话。
