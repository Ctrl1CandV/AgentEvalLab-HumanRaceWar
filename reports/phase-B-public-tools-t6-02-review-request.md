# T6交付02复核请求：先裁定可运行性，不启动实机

交付01被CA阻塞，未运行。此为第二次、最后一次软件交付，基线86e360a；**五模块**联合SHA256：`c7b462c05f94c5fcbb3a8b2493ac252301b7af3907ad3c036f6dbe77a71d2d35`。旧四模块摘要/收条失效；当前仍无实机验收或计分资格。

请只审公开源码与说明，不读private、runs、作者或评测worktree，不执行bot、编译、bwrap或引擎步骤。对照用户反馈`inbox/2026-11-14-t6-delivery01-review.md`：

1. `tools/accept_t6.py`与`experiment_plan.validate_acceptance_cases()`：正常两组不能整体通过；必须另有jobs1/jobs6真实在途截止。jobs6在ACK后故意以70退出标准控制器，绕过其正常finally，实测worker父死亡清理；两组都要证明ACK后不再增加job声明、有未派发任务、已有worker及整个自有树结束。所有可信信号/异常退出夹具也必须成功。
2. `tools/experiment.py`：通用输出只确认controllerReaped，descendantCleanupState保持unknown；不再写cleanupConfirmed。接受路径记录真实墙钟截止、ACK任务集及升级信号，不能将异步后代结束等同于控制器退出。
3. `tools/process_evidence.py`：仅专用验收/夹具子进程启用进程局部subreaper；空内核子树+ECHILD才确认结束，等待失败后的安全强清不得转成PASS。仅信号自身Popen或内核确认的自身子进程，不信号sidecar PID、不扫描无关进程。worker+双沙箱+叶进程两遍核身份给出共同存活区间，不声称CPU满载或时限普遍上界。
4. `tools/profile_bot.py`：空头的完整回放拒绝，未完成的零文件/空gzip计partial/missing-header且不改原件；对应回归已见原StopIteration后转绿。

检查`tests/test_experiment_tools.py`、`tests/test_process_evidence.py`及`docs/T6_TOOLS.md`。36+6项新工具/证据检查与19项既有回归双seed共122次最终检查通过，7文件LSP0；真实信号夹具是可信Python进程，不是bot/bwrap。真实在途停止、异常标准控制器及并发的bwrap路径未运行，不能因上述通过就宣告已验收。

预算：四组2+6+2+8共18计划局，8编译/144启动最坏预留。jobs6停止例增加两任务以保留待派发队列；两份同规模16编译/288启动仍低于原40/400（稿01实际0）。可信夹具另列，不重置6小时模型帽或实际额度。

请明确三项阻塞是否解决、是否允许用户在作者自测/T5评测均空闲时运行**该SHA版本**的公开非计分验收脚本；若有阻塞给具体行号/触发条件/影响，不先让用户盲跑。若第二次交付不通过，停止重划范围，不开第三稿。即使实机通过也不自动签发计分资格或新对局额度。不推送。
