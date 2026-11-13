# 前哨：独立公开材料工作区

这是公开材料的副本，不是构建仓库的克隆，没有Git历史或远程。规则见`rules.md`，参数见`standard-1.json`；SDK、arena和10个公开bot均可阅读。地图有40张public和4张scrimmage；开发与调参只用public。没有隐藏地图、隐藏对手、其他作者代码、逐局开发结果或评分实现。

`PUBLIC-MANIFEST.sha256`登记初始材料，不包含你随后编写的bot和对局。只在本目录工作，不修改规则、arena、SDK、公开bot或预算锁。文档中提到但这里没有的构建者路径不属于这份材料，不要到其他目录寻找。`bot/`和`handoff/in/`、`handoff/out/`初始为空；第一轮由作者自行建立`NOTES.md`并先写计划。

Claude先读根目录`BRIEF-CLAUDE.md`，交付后停止；其他历史导出角色只按自己工作区已有的任务书行动。本README不提供开启其他作者任务或恢复旧轮次的授权。

## 运行环境

使用已安装的Python 3.13、GCC和bubblewrap；框架只用标准库，不需要pip安装依赖。本宿主不是外层bot沙箱，bot和C++编译必须由arena通过离线bwrap执行。不能裸跑、手工裸编译或回退plain；沙箱不可用、机器不匹配或CPU繁忙时，停下告知用户，不改配置或抢锁。

```sh
python3.13 --version
python3.13 -m arena --help
# 写好bot后做基础合规检查；此命令不接受固定时限参数，不是评测预算压力测试
python3.13 -m arena check bot --sandbox bwrap --out runs/check-r01
```

## Claude固定预算命令

Claude工作区提供`budget-lock-jobs1.json`与`budget-lock-jobs6.json`。它们是既有机器绑定锁的公开元数据投影：保留原测量数值、CPU分配、机器绑定和全部预算，标明原锁摘要；删除原封装中的私有结果、路径和无关原始测速记录。不是新测速，也没有改变原锁。

| 并行 | TURN / INIT / BANK | 墙钟余量 | 进程CPU硬限 |
|---|---|---|---|
| jobs1 | 53 / 1050 / 1575 ms | 263 ms | 22 s |
| jobs6 | 60 / 1200 / 1800 ms | 300 ms | 24 s |

```sh
# 小规模自测：一张公开图，对M双座2局
python3.13 -m arena tournament --bot bot --opponents bots/public/M-balanced \
  --maps maps/public/open-01.map --jobs 1 --sandbox bwrap \
  --fixed-timing budget-lock-jobs1.json --out runs/r01-small
# 完整公开自测：10对手 × 40图 × 两座 = 800局；用jobs6确认实际负载下的CPU余量
python3.13 -m arena tournament --bot bot --opponents bots/public/* \
  --maps maps/public --jobs 6 --sandbox bwrap \
  --fixed-timing budget-lock-jobs6.json --out runs/r01-public
# 同一版本中断续跑：原命令的所有输入和参数不变，只追加--resume
# 与自己上一份交付比较；第一轮没有上一版，不编造比较
python3.13 -m arena tournament --bot bot --opponents handoff/out/r01/bot \
  --maps maps/public --jobs 6 --sandbox bwrap \
  --fixed-timing budget-lock-jobs6.json --out runs/r02-v-r01
# 单局只可用jobs1锁
python3.13 -m arena match --a bot --b bots/public/M-balanced \
  --map maps/public/open-01.map --sandbox bwrap \
  --timing budget-lock-jobs1.json --out runs/single
python3.13 -m arena replay verify <回放路径>
python3.13 -m arena replay summary <回放路径>
```

Claude不得运行bench或重新freeze-timing。`benchmark-reference.json`是白名单中保留的历史公开参考，不是重新测速的许可。锁只适用于原机器和标注的并发；不要改数字、改CPU编号或换锁来绕过匹配。实际时限从开局`LIMIT`读取，不要写死。

每次改bot使用新的输出目录，不能覆盖旧结果或在旧矩阵里混入新源码。保留所有失败尝试、结果和回放于`runs/`，如实记录总局数、CPU最大值和自测结果，不上传。check通过不代表变强。

同用户的运行器共用原TMPDIR下的CPU和编译锁。不要改TMPDIR、锁目录或删除锁；GPT统一评测与作者大批自测由用户错开，不同时运行。最多jobs6，不抢占已租用CPU。目录分离不是OS隔离，也不证明会话或模型独立；用户启动时仍须核对上下文、记忆和工具范围。本材料未修改认证、全局配置或安全设置，不推送。
