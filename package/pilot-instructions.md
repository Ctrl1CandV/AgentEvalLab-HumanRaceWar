# 公开材料两阶段试探

目标：独立编写尽可能强的前哨bot，尽力赢。先读`rules.md`和`README.md`。只能使用本工作区的公开材料、自己本次产生的代码和笔记；模型开发、测试和评价全程不联网，不寻找工作区以外的文件。不得读取或恢复构建者的会话、隐藏对手、开发记录或其他作者的代码。bot与C++编译只能通过arena的bwrap运行。

## 阶段一

用户在此目录启动一个全新的GPT/pi会话。上限约6M token、2.5小时，任一用尽即停。在初始为空的`bot/`里实现提交，先过`check`，可对公开bot在public地图上自测。把自己的设计与结果写在`NOTES.md`。阶段末保留`bot/`和`NOTES.md`快照，不调用同一会话继续阶段二。

## 中场：由用户运行，不调用模型

当前没有正式scrimmage命令，本次用tournament替代：预先固定M-balanced、Z-rush、Z-eco三个公开对手，open-01和corridor-01两张scrimmage图，交换座位共12局。这只是本次试探的安排，不是正式阵容的冻结。

```sh
python3.13 -m arena tournament --bot bot \
  --opponents bots/public/M-balanced bots/public/Z-rush bots/public/Z-eco \
  --maps maps/scrimmage/open-01.map maps/scrimmage/corridor-01.map \
  --jobs 1 --sandbox bwrap --reference benchmark-reference.json \
  --freeze-timing --out runs/pilot-practice
```

保存全部结果和失败；反馈使用胜平负、结束原因、最终局内比分和运行诊断，不编造正式任务分数、不添加评分公式或过程评分解释。实际调用与12局是否完成应记入预算记录。

## 阶段二

用户另开一个新会话，预算约8M token、3小时，任一用尽即停。只读本工作区公开材料、自己的阶段一代码/NOTES和中场结果，继续改进。不要从旧会话恢复隐含上下文；最终提交仍是`bot/`。

## 交付与预算记录

由用户在`BUDGET.md`记录两个阶段各自的模型、会话标识、开始/结束时间、实际token计量值及其来源、中断/超限、12局练习赛记录和是否发生外部材料访问。无法计量的字段标未知，不能填预算上限冒充实测。

结束后停止，把最终bot、NOTES和BUDGET交用户本机转交。不要推送到GitHub。接收方只能原样存档、计算摘要和运行评测，开发阶梯的会话不阅读这个bot的源码；它不作为阶梯调参对手。此次试探不抵扣以后要求的正式独立会话测试。
