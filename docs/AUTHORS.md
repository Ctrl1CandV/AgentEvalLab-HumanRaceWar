# 作者与会话分工

用户在T6期间进一步拆分GPT职责，覆盖2026-11-13旧“两工作者”表；其他约束继续有效。具体准备/评测交接见[CLAUDE_EVALUATION_HANDOFF](CLAUDE_EVALUATION_HANDOFF.md)，进度只见各worktree的STATUS。

| 角色 | 工作区 | 职责 | 禁止 |
|---|---|---|---|
| 工具GPT（原会话） | `~/projects/AgentEvalLab-HumanRaceWar`，main | T6公共工具、测试、文档和自己的本地提交 | 不接收/评测Claude交付，不读其源码，不写阶梯策略 |
| 对接/评测GPT（新会话） | `~/projects/HRW-claude-eval`，claude-evaluation | 用户通知后的字节接收、已验收工具统一评测、反馈与本分支报告 | 不读改或转交Claude源码，不改框架/SDK/规则，不用未验收T6工具，不写主worktree |
| Claude作者 | `~/projects/HRW-claude` | 从零独立开发强bot，只用公开材料自测，交付后停止 | 不访问其他项目，不改arena/SDK/规则/公开bot，不推送 |

新增评测GPT不是新增bot作者，不能冒称一次独立策略开发。GPT旧三线保持T3冻结，后续不开发；DeepSeek线结束，旧DeepSeek/pilot工作区已授权删除，原始文件、失败和D-c01仍只读归档，不续轮。

## 作者材料与交付

- 作者工作区由T4按`package/public-files.json`建成，根任务书BRIEF-CLAUDE及两份原预算公开投影齐备；不向已开始的作者工作区同步本轮新工具或改材料。
- Claude每轮按原任务书最多1会话/8小时/30000自测调参局/jobs6，最多交付3候选；只用public开发，离线bwrap，不重测或改TMPDIR/CPU锁。
- 对接GPT等待用户通知，按字节核路径、类型、体积、清单和SHA，副本只放自己的private；不语义读取/AST/import源码，不代修或交给别人。作者自测与自制账本不是统一评测证据。
- T5先check，再用T4原冻结协议和旧标准tournament。首版1280局，后续同作者两段式、正常新增1440局，每候选仍受2080局/2小时帽；不把GPT版当作者前版，不扩大旧额度。

## 隔离与停点

每个GPT只写自己的worktree、STATUS、index、私有清单和总账。只有对接GPT写作者handoff/in反馈；不互写、不自动合并、不建立旧冻结窗口。用户安排评测与作者自测错峰，工具会话目前只做代码和纯检查。

反馈给作者只含check、总分、公开对手逐对/隐藏对手合计、临时Elo/区间、故障/超时、CPU分位和结束方式/同作者取舍；不给隐藏地图、回放、逐局结果、实现或隐藏逐对弱点。每轮反馈后停止。连续采纳两次或临时Elo约M+600时交CA；正在写bot的作者会话不得兼任读取主仓库的CA审查。目录/会话分离不等于OS隔离或正式独立性证明。均不推送，由用户安排分支集成与推送。
