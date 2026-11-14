# 状态

更新：2026-11-14。依据`inbox/2026-11-13-phase-b-new-division.md`；B未完成，C未启动。只本地提交，不推送。

## 当前停点
- T1–T4已完成，用户已报Claude开工。用户最新拆分：本会话只做T6工具；新增GPT专做Claude对接/T5，另用HRW-claude-eval worktree及claude-evaluation分支。
- T4初建有108份公开材料加清单，任务书及jobs1/jobs6预算投影齐备；初始bot和handoff/in/out为空，无Git或链接，原锁与预算未改、0测速；不窥探作者后续源码。
- 8池/80张dev图/原种子与jobs6原锁的私有评测v1协议已登记；见reports/phase-B-claude-workspace.md及data/phase-b/claude-workspace.json。
- T6稿01被CA禁止实机；稿02修复三项阻塞，36工具契约+6进程证据+19既有回归双seed/LSP7文件0，待CA复核。真实bot/编译/bwrap/引擎/check/新局/测速/CPU租用均0，可信进程夹具另计，不得计分。
- P1已改：四组正常/在途截止，jobs6含ACK后控制器异常退出、未派发队列及真实进程重叠；所有清理/升级夹具均是整体通过前置，实机路径未跑。
- P2已改：controllerReaped与后代unknown分开，只有专用验收子reaper空树+ECHILD可确认；安全强清不判通过。
- P3已改：空回放先复现StopIteration后转绿；完整无头拒绝、未完成计部分/无头并保留原件。
- 用户已确认Claude对接交接，独立评测worktree已存在；本会话不访问其工作内容，只做T6。规则见docs/CLAUDE_EVALUATION_HANDOFF.md。

## 已收束
- 用户后续授权清理已完成：DeepSeek79028份已有归档重核，pilot107份全部补存，79135份源/副本两次核字节后删除两个原工作区；只读档案及D-c01保留，Claude未动，零运行。
- T1关闭DeepSeek及lane的历史保留；旧工作区现按后续用户授权删除，恢复索引见private/maintenance/workspace-retirement-20261113/backup/recovery-index.json。
- T2最后存量基线677710项通过；旧658449中仅lane/追加笔记两项预期变化，旧字节可核。后续只读轮清单加追加总账；旧STATUS原字节在docs/history。
- T3完成2080局：直接87/0/73、半分174<176，不采纳E100%，保留E-r02；池提高3.5417pp不替代直接门槛。
- T3实际8编译/4160启动/0重试、check、测速或候选修订，零故障/超时/警告，2080回放各验证一次；见reports/phase-B-gpt-mainlines-final.md。
- A-r02、E-r02、C-r02原字节引用已冻结，GPT不再开发策略。全部失败保留，T3已关闭，旧1864/4400等额度不恢复、不结转。

## 下一项与有效边界
- T5等待用户通知Claude交付：最多3候选，每候选先check；首版1280局，后续同作者两段式、正常新增1440，硬帽2080局/2小时/0测速。反馈后停止。
- Claude按BRIEF-CLAUDE每轮1会话/8小时/30000自测调参局/jobs≤6，从公开材料独立起步；到达里程碑停交CA。
- 两个GPT各写自己的worktree/index/STATUS/private/总账，不互写或自动合并；只有对接GPT写作者handoff/in反馈，均不读改/转交源码，不泄露隐藏输入/逐局/隐藏逐对弱点。
- 作者自测、T5评测、T6实机验收由用户错峰，沿用原TMPDIR和CPU/编译锁；bot/编译离线bwrap，不裸用plain、不重测或抢锁。
- T6原6小时模型/2交付及40编译/400启动总帽不重置；稿02预留8编译/144启动，含队列的18计划局，源码01实际0。若本稿再未通过即停重划，不交第三稿。
- 复核入口reports/phase-B-public-tools-t6-02-review-request.md；先由CA确认五模块版本，再由用户错峰运行一次，当前不允许运行或计分。
- 不改冻结规则/引擎/SDK/standard-1/地图/计量锁；public开发、dev取舍/临时BT、calibration正式校准、grading正式评分、holdout仅B末一次。
- 待裁定B-SCORE-001在阶梯冻结前处理；不迁移Windows，不读/复制/清理仓外调试文件，不推送。
