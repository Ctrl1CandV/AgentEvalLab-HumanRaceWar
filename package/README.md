# 中期试探与独立作者的公开材料清单

这是用户2026-11-09授权的B阶段准备工作，不是C阶段正式任务包验收。清单`public-files.json`列明共同源文件和两个角色的任务说明；`tools/prepare_author_workspace.py`据此导出独立目录，生成并验证逐文件摘要。未列出的文件不会复制，未来增加模块必须重新审查清单。

```sh
.venv/bin/python -m tools.prepare_author_workspace --role pilot --out ~/projects/HRW-pilot
.venv/bin/python -m tools.prepare_author_workspace --role deepseek --out ~/projects/HRW-deepseek
```

目标目录必须不存在，不覆盖用户代码，也不clone主仓库。只复制公开规则、SDK、arena、公开bot、public/scrimmage图、命令说明和角色任务书；不含构建者AGENTS、DESIGN/BRIEF、作者管理文档、开发结果、评分实现、隐藏输入、实际对局、Git远程或个人配置。

`benchmark-reference.json`从既有评测机空闲测量提取必要字段，不重新测量，也不包含逐次测量记录或宿主路径。工作区自测按实际并发测量并冻结本地预算；作者间的统一评测仍由主工作区使用同一机器绑定预算。

检查只证明初始文件范围、摘要和公开CLI/地图检查可用，不证明独立会话已启动、记忆已清除或bot已经通过运行验证。第0步不执行新对局、编译或基准。用户启动注意事项及作者边界见`docs/AUTHORS.md`；两个任务说明不混发。
