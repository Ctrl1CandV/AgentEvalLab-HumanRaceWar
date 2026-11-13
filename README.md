# AgentEvalLab-HumanRaceWar

AgentEvalLab的CA竞技场题族：被测模型为“前哨”编写bot，由固定对手阶梯评测。A已通过；B未完成，C未启动。

## 工作入口

- [STATUS.md](STATUS.md)：当前停点、有效授权、上限和下一步，保持40行以内。
- [2026-11-13新分工](inbox/2026-11-13-phase-b-new-division.md)：当前任务与权限；取代旧E/DeepSeek协调窗口。
- [专项审查](inbox/2026-11-13-phase-b-blockage-review.md)：分析依据，旧角色表/工作包以新分工为准。
- [路线](docs/PHASE_B_ROADMAP.md)、[分工](docs/AUTHORS.md)、[工作区约定](docs/SESSION_COORDINATION.md)。

## 两个工作者

GPT在本WSL主仓库负责统筹、框架、公共工具、评测、集成和阶梯组装，不再写阶梯bot。Claude在`~/projects/HRW-claude`从零开发强bot，只看公开材料；GPT不读改其源码。用户在T4就绪通知后启动Claude，任务书为[BRIEF-CLAUDE](docs/BRIEF-CLAUDE.md)。DeepSeek线结束，原件只读保留。

阶段准备按T1→T2→T3→T4顺序；T3技术停不做T4，T4就绪后停报。T5等用户通知交付；T6新计分工具须先验收。本地提交，推送由用户负责。具体进度不在本页重复。

## 运行与资料

主工作区：`~/projects/AgentEvalLab-HumanRaceWar`。使用Python3.13、GCC11、bubblewrap；所有bot和C++编译均经离线沙箱，不能在宿主裸用plain。测试入口`.venv/bin/python tools/run_tests.py`可能包含bot/编译，零运行任务只选择已确认的纯测试。运行用法见[运行说明](docs/RUNTIME.md)、[固定预算](docs/BATCH.md)、[WSL历史交接](docs/WSL_HANDOFF.md)。本轮不迁移Windows。

[DESIGN](docs/DESIGN.md)规定目标，[BRIEF](docs/BRIEF.md)规定流程，规则全文在[rules](rules/rules.md)。测试覆盖见[tests/COVERAGE](tests/COVERAGE.md)，报告索引见[reports](reports/README.md)。

## 归档和发布

按[归档约定](docs/ARCHIVING.md)：一次性存量基线，之后每轮只读清单和追加总账；不再每轮全扫。历史STATUS原字节在[docs/history](docs/history/STATUS-before-new-division-20261113.md)。

全部原始对局、失败、回放、逐局表和私有清单只留本机`private/`或`runs/`；远端只上传公开代码、测试、文档和聚合。隐藏实现、地图、逐局记录、凭据均不上传。目录约定见[REPOSITORY](docs/REPOSITORY.md)。

每次clone启用发布钩子：

```sh
git config core.hooksPath .githooks
```

旧Git历史和旧失败保留，不强推、不改写；纯检查和字节保全不等于强度或阶段验收。
