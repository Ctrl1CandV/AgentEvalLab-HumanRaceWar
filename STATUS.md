# 状态

更新：2026-11-13。依据`inbox/2026-11-13-phase-b-new-division.md`；B未完成，C未启动。只本地提交，不推送。

## 当前停点
- T1–T4已按顺序完成并停止；`~/projects/HRW-claude/`已就绪，由用户开启Claude会话。GPT未代开作者模型会话。
- T4有108份公开材料加清单，根任务书及jobs1/jobs6预算投影齐备；bot和handoff/in/out为空，无Git或链接，原锁与预算未改、0测速。
- 8池/80张dev图/原种子与jobs6原锁的私有评测v1协议已登记；见reports/phase-B-claude-workspace.md及data/phase-b/claude-workspace.json。
- T4编译、bot、引擎步、check、计分、测速均0；材料隔离不证明模型/会话独立，真实版本和自测数待交付登记。

## 已收束
- T1结束DeepSeek：79028文件字节复核，59777复用、19251新回收；工作区/审查树只读，lane结束。D-c01作低层候选，其余只存档，零运行。
- T2最后存量基线677710项通过；旧658449中仅lane/追加笔记两项预期变化，旧字节可核。后续只读轮清单加追加总账；旧STATUS原字节在docs/history。
- T3完成2080局：直接87/0/73、半分174<176，不采纳E100%，保留E-r02；池提高3.5417pp不替代直接门槛。
- T3实际8编译/4160启动/0重试、check、测速或候选修订，零故障/超时/警告，2080回放各验证一次；见reports/phase-B-gpt-mainlines-final.md。
- A-r02、E-r02、C-r02原字节引用已冻结，GPT不再开发策略。全部失败保留，T3已关闭，旧1864/4400等额度不恢复、不结转。

## 下一项与有效边界
- T5等待用户通知Claude交付：最多3候选，每候选先check；首版1280局，后续同作者两段式、正常新增1440，硬帽2080局/2小时/0测速。反馈后停止。
- Claude按BRIEF-CLAUDE每轮1会话/8小时/30000自测调参局/jobs≤6，从公开材料独立起步；到达里程碑停交CA。
- GPT只写主仓库及作者handoff/in反馈，不读改或委派其源码；不向作者泄露隐藏输入、回放、逐局信息或隐藏逐对弱点。
- 双方不同时大批运行，沿用原TMPDIR和CPU/编译锁；bot/编译离线bwrap，不裸用plain、不重测或抢锁。
- T6本批未启动；新计分工具CA审查和用户验收前不得用于计分。旧lane窗口不再使用，不再开DeepSeek任务。
- 不改冻结规则/引擎/SDK/standard-1/地图/计量锁；public开发、dev取舍/临时BT、calibration正式校准、grading正式评分、holdout仅B末一次。
- 待裁定B-SCORE-001在阶梯冻结前处理；不迁移Windows，不读/复制/清理仓外调试文件，不推送。
