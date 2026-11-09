# 前哨：独立公开材料工作区

这里是公开材料的独立副本，不是构建仓库的克隆，没有Git历史或远程。`rules.md`是规则全文，`standard-1.json`是参数；SDK、引擎及运行工具均可阅读。`maps/public/`有40张地图，`maps/scrimmage/`有4张。没有隐藏对手、隐藏地图、其他作者的代码、开发结果或评分实现。`PUBLIC-MANIFEST.sha256`记录初始材料，不包含你之后写的bot和对局。

只在本目录工作，不要到上级或其他项目目录查找材料，也不要修改规则、工具、SDK或公开bot。`rules.md`和SDK说明中提到的构建仓库测试/文档路径不属于这份材料；工具命令以本README为准，不要为寻找那些路径离开工作区。`bot/`初始为空。你的开发任务和联网权限以用户给你的任务书为准；无论如何，bot、C++编译和对局始终离线。

## 命令

需要已安装的Python 3.13、GCC 11和bubblewrap。本开发宿主不是外层bot沙箱，必须使用bwrap，不能裸跑bot、手工裸编译C++或回退到plain。框架只用标准库，不需要pip安装依赖。

```sh
python3.13 --version
python3.13 -m arena --help
# 在bot/写好main.py，或顶层C++源码后：
python3.13 -m arena check bot --sandbox bwrap --out runs/check-r01
# 新版本日常测试：10个公开对手 × 40图 × 两座 = 800局
python3.13 -m arena tournament --bot bot --opponents bots/public/* \
  --maps maps/public --jobs 1 --sandbox bwrap \
  --reference benchmark-reference.json --freeze-timing --out runs/r01-public
# 中断后同一版本续跑：源码与所有参数必须不变
python3.13 -m arena tournament --bot bot --opponents bots/public/* \
  --maps maps/public --jobs 1 --sandbox bwrap \
  --reference benchmark-reference.json --freeze-timing --out runs/r01-public --resume
# 下一版或与上一版直接比较：用同一机器、同一jobs的原锁，不重新挑系数
python3.13 -m arena tournament --bot bot --opponents versions/r01/bot \
  --maps maps/public --jobs 1 --sandbox bwrap \
  --fixed-timing runs/r01-public/timing-lock.json --out runs/r02-v-r01
python3.13 -m arena replay verify <回放路径>
python3.13 -m arena replay show <回放路径> --turn 25
python3.13 -m arena replay summary <回放路径>
```

`versions/r01/bot`由你在修改前原样保存；第一轮没有上一版，不能编造比较。改变bot后使用新的输出目录，不能覆盖旧结果或对旧矩阵续跑。完整结果、失败尝试与回放都留在`runs/`，如实记录，不上传。`check`只是合规检查，不是强度证明。

`benchmark-reference.json`只有既有空闲参考值和公开硬件信息，没有重新测速。tournament会按本地实际并发测量一次并冻结；实际CPU限额由LIMIT传给bot，不能写死。固定锁只适用于原机器和原并发；移机后要重新测量/冻结，不能改数字假装兼容。

同用户的arena运行器共用系统临时目录里的CPU与编译锁。不要修改TMPDIR、删除锁或抢占已租用CPU。默认`--jobs 1`便于小规模自测；若其他工作占满CPU，和用户协调错开批次，不连续重试或修改限额。机器上的别的程序并不会因此被自动隔离。

## 会话与交付

新会话从本目录开始，不恢复构建者或另一作者的会话，不读取工作区外的笔记或记忆。材料目录隔离不是同一WSL用户下的OS访问控制：用户还需在启动时核对项目上下文和记忆/工具范围，确保没有加载其他项目的AGENTS或历史。这里没有替用户修改pi的认证、全局配置或安全设置。

DeepSeek使用`docs/BRIEF-DEEPSEEK.md`，按其中节奏交付`handoff/out/r<NN>/`并停下；反馈放在`handoff/in/`。标准预算试探使用`PILOT.md`，由用户另开两次干净会话并记录真实预算；不要把试探当作正式验收。每个工作区只提供与自己任务对应的那份说明。
