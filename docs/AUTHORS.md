# 两个工作者的分工

执行依据：[2026-11-13用户裁定](../inbox/2026-11-13-phase-b-new-division.md)。进度只见[STATUS](../STATUS.md)，不在本文重复。

| 工作者 | 工作区 | 负责 | 禁止 |
|---|---|---|---|
| GPT | `~/projects/AgentEvalLab-HumanRaceWar` | 统筹、公共框架/工具、统一评测、集成、阶梯组装、B交审 | 不再写阶梯bot；不读改Claude源码；不向作者泄露隐藏资料 |
| Claude | `~/projects/HRW-claude` | 从零写强bot，公开材料自测，交付后停止 | 不访问工作区外目录；不改arena/SDK/规则/公开bot；不看其他作者实现；不推送 |

GPT的T3仅原样评测已有E候选，不是重新开发策略。DeepSeek作者及原协调线结束，工作区与交付只读存档，不再续轮；D-c01保留作正式校准时的低层候选，历史记录不消失。

## Claude材料与交付

- 由`tools/prepare_author_workspace.py --role claude`按`package/public-files.json`导出公开材料、`BRIEF-CLAUDE.md`及说明，另提供原jobs1/jobs6预算的公开元数据投影，保留机器绑定、去除私有结果/路径，原锁不改、不测速；不clone主仓库，不建Git，不留链接或个人上下文。
- 初始`bot/`及`handoff/in/out/`为空。用户在T4就绪通知后开启Claude会话；GPT不代开、不委派bot开发。
- Claude每轮按任务书最多8小时、30000自测/调参局、jobs6，最多交付3个bot；全部bot和编译使用离线bwrap，不能裸用plain，不重测或改TMPDIR/CPU锁。
- 用户通知交付后GPT才按字节接收，核路径、类型、体积、清单和SHA，不读取或改动源码。作者自测/脚本/账本不是评测证据。
- 接收副本放`private/ladder/claude/<代号>/`；先check，再按T4冻结协议统一评测。首版1280局，后续与自己的保留版按BRIEF5.1.1(3)比较，不以GPT bot冒充前版。

## 写入与反馈

GPT只写主仓库及Claude的`handoff/in/`反馈；Claude只写自己的工作区。两目录不重叠，不需要旧全局静止窗口。CPU密集任务仍由用户错峰，沿用同一TMPDIR和CPU/编译锁。

反馈只含check、总得分、公开对手逐bot战绩、隐藏对手合计、临时Elo/区间、故障/超时、CPU中位/p99/最大、结束方式和新旧取舍，不给隐藏地图、回放、逐局结果或隐藏bot逐对弱点。模型、真实会话数、自测自报和本机评测局数分别记入私有笔记。

每轮反馈后停止。Claude任一主线连续采纳两次或临时Elo约达M+600时，停交CA审查，再安排里程碑和后续风格/档位。目录分离不是OS隔离，作者身份不冒充正式独立自测。双方都不推送，由用户推送。
