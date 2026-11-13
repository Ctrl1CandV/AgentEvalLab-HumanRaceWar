# HumanRaceWar 构建者说明

## 当前分工与任务依据

以 `inbox/2026-11-13-phase-b-new-division.md` 和用户最新指令为准；同日blockage-review的A、B1/B3/B4/B5有效，旧角色表和工作包已被取代。

- 只有两个工作者：GPT在本WSL仓库负责统筹、框架、工具、评测、集成和阶梯组装；Claude在`~/projects/HRW-claude`从零写强bot。
- GPT不再写阶梯bot；T3只原样评测已经冻结的E100%候选，不改源码。GPT不读、不改Claude源码，也不把它交给其他人。
- DeepSeek线已经结束，工作区和原始交付只读保留；不再开会话、发任务、反馈或接收窗口。不读、不执行其作者代码，只可按字节归档。
- GPT只写主仓库和Claude工作区的`handoff/in/`反馈。Claude只写自己的工作区。不再使用旧E/协调方lane和全局冻结/释放窗口。
- T1→T2→T3→T4依次完成，无中间审查停点。T3技术停则停止且不做T4；T4就绪后停报，由用户启动Claude。T5等用户通知；T6只能在T4后开始，验收前不得用于计分。

## 每次开工

1. 检查`inbox/`，完整阅读`docs/DESIGN.md`、`docs/BRIEF.md`、`STATUS.md`及当前任务裁定。
2. 首次接手补读`docs/WSL_HANDOFF.md`、`docs/IMPLEMENTATION_NOTES.md`、`tests/COVERAGE.md`。
3. 检查Git状态，保留用户改动，确认`core.hooksPath=.githooks`。不reset/stash或绕过hook。
4. 使用`.venv/bin/python`或`python3.13`，不是系统3.10。测试入口为`.venv/bin/python tools/run_tests.py`；零运行任务只跑确认不含bot/编译/引擎步的纯测试。

## 运行与证据

- 框架只用Python标准库；新工具安装先问用户。
- 所有bot和C++编译都在离线bwrap中运行；WSL/pi不等于bot沙箱。plain仅用于已有明确外层沙箱，不裸跑，不回退。
- 沿用固定机器锁、jobs、CPU/编译锁和TMPDIR；两边大批运行错峰，不抢锁、不重测或改变配置绕占用。
- T3单独批准最多2080局dev、8编译、4160启动另加标准框架重试、至多1check、2小时对局墙钟；候选字节不变。取舍和技术停按new-division执行，不写新控制器。
- 旧E trial01、资格02和强度01继续关闭；剩余1864局不恢复，旧额度不结转。T3不是恢复旧轮次。
- T2后按`docs/ARCHIVING.md`做每轮只读清单和`private/ledger.jsonl`追加总账。旧HIDDEN是一次存量基线，不每轮重扫。里程碑/B交审再全量核验。
- 原始失败、阴性结果、前像、源码快照和逐局资料全部保留。CPU和墙钟分开，未知项不编造；构建不统计token，正式标准预算自测另按BRIEF要求。

## 安全与发布

- 不读取、打印或迁移凭据，不读pi的`auth.json`，不复制个人认证配置，不改代理或安全设置。
- 隐藏bot、地图、相关对局和原始分析只在`private/`；公开对局原件留本机`runs/`，都不上传。
- 公开仅代码、测试、文档和聚合，不公开隐藏实现/弱点、逐局表、回放或索引。提交前执行发布检查，旧基线和新轮清单的隐藏摘要均受保护。
- 不改规则、SDK、standard-1、胜负、协议、计分或验收门槛。B-SCORE-001在阶梯冻结前再裁定；过程分仍是未冻结雏形。
- 只在本WSL仓库开发，不进行Windows迁移，不与旧Windows备份双向开发。
- 小步本地提交，署名`gpt-6-astra`，GitHub noreply邮箱；不改写历史。**不推送，由用户推送。**
- B未完成，C不启动；阶段完成按BRIEF交审，不将构建检查通过当成阶段验收。
