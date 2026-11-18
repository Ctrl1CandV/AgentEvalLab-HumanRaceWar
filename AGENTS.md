# HumanRaceWar 构建者说明

## 当前分工与任务依据

当前以 `inbox/2026-11-18-phase-b-wpa-review.md` 及用户最新指令为准；11-16审查、11-13分工中未被取代的要求和历史保全边界继续有效。

- 用户最新拆分为工具GPT、对接/评测GPT和Claude作者。工具GPT只在本WSL主worktree做T6；对接GPT在独立`~/projects/HRW-claude-eval` worktree/`claude-evaluation`分支做T5；Claude在`~/projects/HRW-claude`从零写强bot。详见`docs/CLAUDE_EVALUATION_HANDOFF.md`，旧“两工作者”表仅为历史。
- GPT不再写阶梯bot；T3只原样评测已经冻结的E100%候选，不改源码。GPT不读、不改Claude源码，也不把它交给其他人。
- DeepSeek线已经结束。用户后续授权在完整字节保全后删除旧HRW-deepseek/HRW-pilot工作区，现已删除；原始文件、交付和失败证据仍在private只读归档。不再开旧作者会话、发任务或反馈；不读、不执行作者或pilot代码，只按字节处理档案。
- 两个GPT各自独占本worktree的代码/私有档案/总账/STATUS/index，不直接写对方目录或自动合并分支。只有对接GPT可写Claude的`handoff/in/`反馈，除此不改作者工作区。新评测worktree按交接复制最小已冻结输入，不复制整库private或主总账。旧lane/全局冻结窗口不恢复。
- T1–T4已完成，用户已启动Claude；对接GPT的T5仍必须等用户明确通知交付及错峰运行。工具GPT专做T6，CA及用户验收前不得接到计分。新会话由用户开启，当前会话不代开、不转交作者源码。

## 本轮工具/汇总收尾

T6 两项小修及 WP-A 已获接受。本轮仅落实阶梯公开范围裁定、更正状态并核对 WP-A2/WP-B 公开材料；只从固定评测提交精确导入，不导入评测管理文件或 private，不改其他工作区，不新增实机运行。WP-B 没有公开结果可核时，不登记为已完成；r11 的实际进度只按用户最新说明登记。

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
