# 当前会话隔离约定

用户最新指令把GPT拆为工具会话与Claude对接/评测会话。原2026-11-13裁定的规则、预算、源码保密和T5通知停点不变；旧“两工作者”、共享index及旧lane安排不作为当前权限。完整启动说明见[CLAUDE_EVALUATION_HANDOFF](CLAUDE_EVALUATION_HANDOFF.md)。

## 分开工作，不共用写入点

- 工具GPT：主仓库`~/projects/AgentEvalLab-HumanRaceWar`、main，专做T6。
- 对接GPT：独立worktree`~/projects/HRW-claude-eval`、claude-evaluation，从已验收基线`a919da7`开始，专做T5。
- Claude作者：`~/projects/HRW-claude`；其源码两个GPT均不读改或转交。

两个GPT各写自己的文件树、STATUS、MANIFEST、Git index、private和ledger；不改共享Git配置、不切对方分支、不直接写对方目录、不自动合并。用户安排公开汇总的最终集成。新worktree只按字节复制协议列出的最小已冻结输入，保留原协议并另记路径映射/摘要；不链接主private，不复制整库或旧HIDDEN/总账，不冒称拥有原全量登记。自己的输入包封存为本地总账起点，之后逐轮登记。

只有对接GPT可在用户通知后接收交付，并写作者`handoff/in/`反馈。工具GPT不接触作者工作区、交付和源码；收到公共框架问题时仅处理不含作者代码的摘要。两者不互相转交作者代码或隐藏输入。

## 资源与工具版本

仍共享原TMPDIR和CPU/编译锁；评测与作者大批自测由用户错峰，不抢锁或换CPU池。所有bot/编译经离线bwrap，不回退plain、不重测。T6开发期间只做代码/纯检查；新工具未经CA审查及用户错峰实机验收不得用于计分，不能提前拷到评测分支替代已验收流程。T6不改arena/引擎/SDK/规则/锁或旧默认行为，因此原T5框架版本继续可用。

## 授权与停止

新对接会话首次只准备隔离worktree和最小输入，随后等用户明确通知Claude交付并停止大批自测，再按已批准T5范围check/评测。不能靠目录出现、资源空闲或旧收条默许启动。每轮反馈后停止；里程碑按原裁定交CA。T6独立提交审查，最多2次交付，不借网络中断重置预算。

不恢复DeepSeek/pilot或旧1864/4400额度；全部失败保留，旧绝对路径只作历史。无需全局冻结/窗口循环。双方仅本地提交，不推送；B未完成，C不启动。
