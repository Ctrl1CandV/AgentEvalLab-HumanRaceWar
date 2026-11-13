# 目录与上传范围

2026-11-13。开发机运行/存储，GitHub只作公开审查与聚合，不是对局数据库。当前GPT/Claude分工见AUTHORS，归档按ARCHIVING执行，旧全局lane窗口不再使用。

## 目录入口

| 目录/文件 | 用途 |
|---|---|
| `arena/`、`sdk/`、`bots/public/`、`maps/` | 框架、SDK、公开bot与地图；保持原代码布局 |
| `rules/`、`tests/`、`tools/` | 规则配置、可运行测试与构建/分析工具 |
| `STATUS.md` | 不超过40行的当前状态；原文保存在`docs/history/STATUS-before-new-division-20261113.md`，旧handoff只作历史 |
| `data/balance.json`、`zoo-matrix.csv`、`timing.json` | 当前平衡、聚合胜率矩阵和效率入口 |
| `data/phase-a/acceptance/` | 最后验收、资源、效率和本轮发布检查汇总 |
| `data/phase-a/matrices/` | 每个候选及最后复跑的独立聚合矩阵，包含失败版本 |
| `data/phase-a/regressions/`、`diagnostics/` | 策略反例及骚扰/开局诊断汇总 |
| `data/phase-a/usage/`、`history/` | 用量快照与早期开发汇总 |
| `data/phase-b/`、`reports/phase-B-holdout.md`、`phase-B-damage22.md` | 首次留出/D22历史失败、第二份审查分析、新holdout布局、已关闭的L0问题、dev01–dev04主线开发、CPU与来源；隐藏/合并原件只留private，公开对局原件只留runs |
| `logs/` | 当前必要的测试诊断；历史完整日志不再上传 |
| `docs/history/`、`reports/archive/` | 有审查价值的历史说明，不作为当前待办 |
| `runs/` | 本机原始运行、结果库、完整回放、旧日志与证据归档；不入Git |
| `private/` | 隐藏资产、对局及原始分析；HIDDEN为一次性存量基线，轮清单在manifests/、追加总账ledger.jsonl，均只留本机 |

## 哪些内容不上传

实际对局的回放、逐局表、结果库、尝试记录、逐局审计索引都留在本机，不能改名为报告或拆成小文件后上传。公开bot之间的示例回放也不例外。必要的单测夹具由测试代码合成，不拿实际对局文件充当公开夹具。

保留的是聚合局数/胜平负、按地图类型的矩阵、bootstrap区间、失败统计、资源/效率汇总，以及审查必要的诊断日志。汇总必须覆盖全部样本和失败，不因不上载明细而挑选结果。

原始分析输出写入 `runs/`（隐藏输入仍只写 `private/`）；将审查需要的聚合部分纳入 `data/`。`tools/publication.py`的检查覆盖已知逐局格式，不能代替人工审查任意改名或新格式。pre-commit检查暂存内容，不用忽略规则掩盖已跟踪文件。

## 新归档方法

T1后最后一次全量登记形成只读HIDDEN基线；以后新轮目录设只读、写清单并追加总账，平时核新轮与链，里程碑/B交审再全量核验。发布钩子兼查基线及新轮摘要。旧DeepSeek工作区与交付只存档，不清理、不复活；新Claude工作区不是主仓库clone。见`docs/ARCHIVING.md`。

## 本机归档与历史

整理前的555份证据保存在：

```
runs/local-evidence/509f1f8-before-summary-only/
```

其本地 `MANIFEST.sha256` 核对原始字节。精简JSON中的`_publication`标记原始副本位置、摘要和省略的明细区段；它们是既有测量的汇总副本，不是新实验。对局及失败没有删除，原 `runs/development/` 也未清理。

历史文档中保留的旧路径对应当时快照；当前汇总位置见 `data/phase-a/catalog.json`。根 `MANIFEST.sha256`只覆盖本次可上传的审查树，不用于声称原始运行已上传。

本次普通提交不会清除旧Git历史。`509f1f8`及以前已有逐局数据；最新树变小不等于完整clone的历史体积已变小。没有改写历史、强推或删除远端分支。
