# T6工具：默认关闭，先审查再验收

代码审查入口：`reports/phase-B-public-tools-t6-01-review-request.md`。首稿只通过纯检查；**CA审查待做、用户bwrap验收未跑，不能接到T5计分/取舍**。四个新tools模块不改arena、引擎、SDK、规则、机器锁或旧默认。当前Claude作者不得兼任读取主仓库的CA审查会话。

## 先审查，再由用户错峰验收

```sh
# 默认只输出计划、implementationSha256，不运行bot
.venv/bin/python -B -m tools.accept_t6
# CA确认该摘要版本，用户确认作者自测/T5评测均空闲后，亲自运行一次
.venv/bin/python -B -m tools.accept_t6 --execute --reviewed-sha256 <SHA> --exclusive-window --out runs/t6-acceptance01
```

验收仅公开bot与public/scrimmage图：jobs1两局、jobs6六局，正常4编译/16启动，含标准三次框架重试预留64启动。两次交付的预留仍低于T6总帽40编译/400启动；每交付只运行一次，不自动整批重试。回传`acceptance-summary.json`聚合，原始回放/索引留本机。脚本不自行签发CA/生产批准。

## 清单与CPU画像

完整JSON样例在`tools/examples/t6-public.json`：固定标签/源码SHA、地图SHA、配对、种子、jobs、既有锁、游戏/编译/启动/墙钟帽及故障停止条件。源码只字节校验/标准snapshot，不作AST/import或语义阅读。

```sh
# 只冻结，不执行；保存输出的frameSha256
.venv/bin/python -B -m tools.experiment freeze tools/examples/t6-public.json --out runs/t6-example
# 以下只用于经审查、错峰的非计分操作；开关不可省略
.venv/bin/python -B -m tools.experiment run runs/t6-example --frame-sha256 <SHA> --enable-experimental
.venv/bin/python -B -m tools.profile_bot --from-experiment runs/t6-example
```

profile前端可用`--bot <目录> --opponents <公开目录...> --maps <公开map文件...> --jobs N --timing <现有固定锁> --out <新目录>`；同样默认仅冻结，显式`--enable-experimental`才执行。报告INIT、TURN（含故障TURN）的精确最近秩p50/p99/最大、核号和超限回合。超名义TURN额度可能合法消耗BANK，不等于超时；声明并发不表示每时刻满载。头/身份/CPU合计检查不是引擎重放，验收脚本另用旧验证器且复用已有恢复凭据。

## 必须知道的边界

- 仅新批次，无resume/覆盖/整批重试。整计划按每局最坏8启动及全部C++输入预留，不依赖及时停止守住帽值。输入与工具版本变动就停，不热改工具继续运行。
- 外层每0.1秒观测持久化输出，不是零延迟派发钩子。截止时中断自己的标准控制器，最多15+5秒清理后仅强停自己持有的子进程，不向sidecar PID发信号；不承诺失败后绝不多派一局。CPU/编译租约仍由标准tournament负责，外层不保证额外独占CPU或OS隔离。
- 无人工收条时只允许公开非计分验收。诊断/非公开输入需`--approval <本机收条>`，字段见`experiment_plan.approval()`；必须绑定当前工具/框架与真实8局验收，不能拿合成检查、缺项或旧版本冒充通过。这是操作者收条，不是密码学认证。
- 私有输入只能输出private；超限JSONL、CPU SQLite、日志及回放全部只留本机。哈希链终点/行数另存run.json；损坏/截断即停，原字节保留，不自动修复，也不声称防同UID伪造。
- 不改TMPDIR/锁目录、不回退plain、不测速、不访问作者工作区。工具通过验收也不自动授予新对局额度；实际运行仍按各自用户授权及错峰安排。
