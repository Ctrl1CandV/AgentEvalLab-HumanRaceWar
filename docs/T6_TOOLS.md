# T6工具交付02：默认关闭，仍待CA与用户验收

交付01已被CA阻塞，**禁止运行旧验收脚本**。本稿修复停止/清理证据和空回放；只完成合成契约与可信Python进程夹具检查，真实bot/bwrap/编译/引擎步骤均0，不能用于计分。审查入口：`reports/phase-B-public-tools-t6-02-review-request.md`。源码指纹现在覆盖五模块（含process_evidence），旧批准收条无效。

## CA确认版本后，用户亲自错峰验收

```sh
# 默认只输出计划/源码摘要，不启任何进程夹具或bot
.venv/bin/python -B -m tools.accept_t6
# 仅在CA明确允许，且作者自测和T5评测均空闲时运行一次
.venv/bin/python -B -m tools.accept_t6 --execute --reviewed-sha256 <新SHA> --exclusive-window --out runs/t6-acceptance02
```

四组均用公开bot和public/scrimmage图：正常jobs1两局、jobs6六局；在途停止jobs1计划两局、jobs6计划八局。停止计划先观察实际worker、双沙箱及叶进程的两遍核身份重叠区间，再收紧真实墙钟截止；jobs1走SIGINT清理，jobs6在ACK后故意异常退出标准控制器，验证worker父死亡路径。停止后ACK任务集不得增加，且须有未派发任务。jobs6多留两任务是为了真实检查队列未派发，不只是已有全部任务收尾。

保守预留每交付8编译/144启动/18计划局，两份同规模也仅16/288，小于原40/400总帽（稿01实际0）。不自动整批重试。另有SIGINT、TERM、KILL及异常控制器可信Python夹具，单独记录，不是bot启动。四组和所有夹具不齐不能整体通过；只返回本机acceptance-summary.json聚合，原件不上传。两次交付失败后停划范围，不开第三稿。

## 清单与画像

JSON样例`tools/examples/t6-public.json`绑定标签/源码、SDK、地图、种子、jobs、原锁、预算与停止条件；不解释或import bot源码。

```sh
# 只冻结，保存frameSha256；以下执行仅在获得相应授权后使用
.venv/bin/python -B -m tools.experiment freeze tools/examples/t6-public.json --out runs/t6-example02
.venv/bin/python -B -m tools.experiment run runs/t6-example02 --frame-sha256 <SHA> --enable-experimental
.venv/bin/python -B -m tools.profile_bot --from-experiment runs/t6-example02
```

profile前端用`--bot <目录> --opponents <公开目录...> --maps <公开map...> --jobs N --timing <原锁> --out <新目录>`，默认仅冻结。分别报告INIT/TURN（含故障）、最近秩p50/p99/max、核号和超限。合法消耗BANK不等于超时；实际进程重叠也不证明CPU满载或普遍时限上界。完整回放无头拒绝；未完成的空文件/空gzip计入部分/无头数量，保留原件。

## 证据边界

- 通用run.json只记controllerReaped，后代状态unknown（未启动则not-started），不再把控制器退出叫“整个树清理确认”。15秒SIGINT、5秒TERM再KILL，记录升级，不能据此推断后代已结束。
- 用户验收的专用子进程才启用进程局部subreaper；控制器结束后核空子树和ECHILD，等待中的异步退出可收束。超时仅对内核确认的自身子进程做安全清理，仍判失败/unknown，不能清理后冒称自然通过。无全局安全设置改动，不向sidecar PID发信号、不扫无关进程。
- ACK是“不再派发”的证据边界；外层每0.1秒轮询，不保证触发请求前零延迟停发。afterActiveWorkers/controllerExitOnAck仅显式公开验收可用，正常/私有诊断无此故意异常退出。
- 仅新批次，无resume/覆盖/整批重跑；事前按每局最坏8启动预留。私有输入只能输出private，须有绑定当前代码与完整真实验收的人工收条；它不是密码学认证。哈希链及外部终点不能防同UID伪造。
- 原始CPU SQLite、超限JSONL、日志/回放均留本机；不改arena/规则/SDK/锁/TMPDIR，不测速或回退plain。工具验收不自动授予计分资格、新对局额度或阶段通过。
