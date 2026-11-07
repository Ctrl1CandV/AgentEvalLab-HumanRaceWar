# Bot SDK v1

- Python：`sdk/python/hrw.py`；入口文件 `main.py`。
- C++：`sdk/cpp/hrw.hpp`；入口为目录顶层的 `*.cpp`，GCC 11 / C++20。
- `read_setup` 读开局消息；发 `READY` 后循环 `read_turn`，用 `send` 输出指令和 `END`。
- 未知消息关键字跳过；EOF 结束循环；消息中途 EOF 报错。C++ 的 seed 保留为十进制字符串，不截断任意长度的协议种子。
- `neighbors`、曼哈顿 `distance`、多源 `bfs` 只处理几何；BFS 默认只走 `.`，可传入阻挡坐标。
- SDK 不含策略。两种语言的 `example/` 会采矿、满载返家、每 30 回合尝试出一个守家战士；未校准强度，两者不保证走相同路线。

示例和用户 bot 都只能在沙箱内执行，C++ 编译也一样。不要直接在当前 WSL 宿主运行示例。运行器向 Python 提供 `/sdk` 搜索路径，向 C++ 编译器提供 `-I/sdk`；用户也可将相应单文件 SDK 复制进自己的 bot 目录。
