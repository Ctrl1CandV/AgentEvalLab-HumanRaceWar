# 相关工作

2026-11-27 核对。每条都打开过 arXiv 摘要页、会议页面或原文页面，至少核了标题、作者、年份和编号；会议信息以会议官网或 arXiv 备注为准。没能核到的标"未核实"。这不是系统综述，漏掉的工作肯定有。

条目格式：**标题**（作者，出处，年份，编号）链接。下面一两句写它做了什么，"关系"写它和 HRW 的异同。

## 1. 模型写代码对战（最近的邻居）

- **CodeClash: Benchmarking Goal-Oriented Software Engineering**（John Yang, Kilian Lieret, Joyce Yang, Carlos E. Jimenez, Muhtasham Oblokulov, Aryan Siddiqui, Ofir Press, Ludwig Schmidt, Diyi Yang；ICML 2026 poster；arXiv 2511.00839）<https://arxiv.org/abs/2511.00839> · [ICML 页面](https://icml.cc/virtual/2026/poster/63924)
  - **做了什么：** 模型分多轮修改自己的代码库，代码库之间在竞技场里对战。主表有 6 个竞技场：BattleSnake、CoreWar、Halite、Poker、RoboCode、RobotRumble。按胜率用最大似然拟合 Elo。CC:Ladder 让模型逐个挑战人写的解，RobotRumble 有 58 个，Core War 有 264 个，没有模型爬完。
  - **相关发现：** 论文原话是模型"往往只读日志的前几行"，会编造输掉的原因，改了代码不检验效果，"强模型输了几轮之后也很难恢复"。
  - **关系：** 和 HRW 最近。区别在于 CodeClash 的主排名是模型之间的相对 Elo；HRW 对固定的隐藏阶梯计分，有绝对锚点。
- **StarSkirmish Bench v0.1**（Kai McPheeters，网页，2026-09-26）<https://starskirmish.com/bench/v0-1/>
  - **做了什么：** 模型在 1 小时墙钟内用 C++（BWAPI 4.4.0、OpenBW）写一个星际争霸：母巢之战的神族 bot，在 3 张天梯图上打神族内战。分数是对 12 个参照 bot（9 个人写、3 个 demo）的期望胜率，再线性缩放成 0–100：最弱的 demo bot "Four Gate Dragoon" 为 0，人写 bot Stardust 为 100。
  - **方法细节：** 每个模型跑 5 次取平均评级，不报区间。Elo 是参照 bot 和全部模型 bot（共 62 个参赛者）放在一起联合拟合的。页面说 3 个 demo bot 的源码模型都能读；开发时模型可以和参照 bot 打练习赛、读对局记录；人写 bot 的源码是否可见，页面没有说。
  - **关系：** 和 HRW 最像，都是"写 bot，按分级参照计分"。HRW 的区别：评分对手在开发时打不到；版本冻结并做相邻复核；按 CPU 时间计时、有噪声检查；报区间。
- **Combining Code Generating Large Language Models and Self-Play to Iteratively Refine Strategies in Games**（Yoram Bachrach, Edan Toledo, Karen Hambardzumyan 等 14 人；IJCAI 2025 Demo Track，pp. 10999–11003）<https://ijcai.org/proceedings/2025/1249>（DOI 10.24963/ijcai.2025/1249）
  - **做了什么：** LLM 写出下棋的代码，这些生成的 bot 互相对弈，一轮轮迭代变强。
  - **关系：** 用自对弈来改进代码策略，是论文 3（模型怎么用反馈）的参照。注意这是演示轨道的短文，不是主会论文。
- **Evaluating LLMs in Open-Source Games**（Swadesh Sistla, Max Kleiman-Weiner；NeurIPS 2025；arXiv 2512.00371）<https://arxiv.org/abs/2512.00371>
  - **做了什么：** 玩家提交的是程序而不是动作，而且程序能读到对方的代码，由此研究"程序均衡"，以及合作和欺骗策略如何出现。
  - **关系：** 同样是"写程序对战"。但那里对手代码可见，HRW 隐藏阶梯的源码在沙箱里读不到（DESIGN 6.1）。
- **RevengeBench: Reverse Engineering Code-Space Policies from Behavioral Experiments**（Babak Rahmani, Sebastian Dziadzio, Joschka Strüber, Sergio Hernández-Gutiérrez, Matthias Bethge；预印本 2026；arXiv 2606.26094）<https://arxiv.org/abs/2606.26094>
  - **做了什么：** 从 CodeClash 锦标赛里取 75 个有 Elo 的 LLM 生成策略。学习者观察一个隐藏策略，自己设计对手去试探它，再提交可执行代码复原它。复原出的代码在锦标赛里能带来优势。
  - **关系：** 这说明对手只要能被反复试探，"隐藏"就不牢靠。HRW 的被测模型开发时只能对公开 bot 和练习赛，打不到隐藏成员，这一点要在论文 1 里讲清楚。
- **From Code to Play: Benchmarking Program Search for Games Using Large Language Models**（Manuel Eberhardinger, James Goodman, Alexander Dockhorn, Diego Perez-Liebana, Raluca D. Gaina, Duygu Çakmak, Setareh Maghsudi, Simon Lucas；arXiv 2412.04057，备注称投往 IEEE Transactions on Games 专刊）<https://arxiv.org/abs/2412.04057>
  - **做了什么：** 用 LLM 控制变异的进化爬山，为迷你 Atari、Baba is You、TAG 桌游等任务合成代码。
  - **关系：** 讲程序搜索，不是在预算内的一次性开发。生成的代码是否都是下棋策略，摘要没写清。
- **Language Models Speed Up Local Search for Finding Programmatic Policies**（Quazi Asif Sadmine, Hendrik Baier, Levi H. S. Lelis；TMLR 2024）<https://mlanthology.org/tmlr/2024/sadmine2024tmlr-language/>
  - **做了什么：** LLM 给出程序化策略的初始候选，再用局部搜索改进，测试环境之一是 microRTS。消融显示，LLM 的知识很大一部分来自 DSL 里有意义的函数名。
  - **关系：** RTS 程序化策略这一支，和 HRW 的 SDK 只给几何、不给战术的选择有关。
- **InnateCoder: Learning Programmatic Options with Foundation Models**（Rubens O. Moraes, Quazi Asif Sadmine, Hendrik Baier, Levi H. S. Lelis；IJCAI 2025；arXiv 2505.12508）<https://arxiv.org/abs/2505.12508>
  - **做了什么：** 用基础模型生成程序化的"选项"，再组合成完整策略，在 MicroRTS 和 Karel 上测试。
- **Choosing Well Your Opponents: How to Guide the Synthesis of Programmatic Strategies**（Moraes, Aleixo, Ferreira, Lelis；IJCAI 2023；arXiv 2307.04893）<https://arxiv.org/abs/2307.04893>
  - **做了什么：** 提出 2L 算法，合成的 microRTS 策略在模拟锦标赛中胜过前两届比赛的人写冠军。
  - **关系：** 用什么对手来指导合成，正是阶梯选材的问题。作者名单只核到检索摘要这一层。

## 2. 分级锚点和与人类可比的分数

- **BotzoneBench: Scalable LLM Evaluation via Graded AI Anchors**（Lingfeng Li, Yunlong Lu, Yuefei Zhang 等 10 人；预印本 2026；arXiv 2602.13214）<https://arxiv.org/abs/2602.13214>
  - **做了什么：** 8 款游戏：井字棋、五子棋、Ataxx、黑白棋、国际象棋、两人德州扑克、斗地主、国标麻将。0 级是随机合法着；往上从 Botzone 平台挑现成 bot，依据是平台 Elo 和对下一级的胜率，"一般控制在 70%–90%"。同级尽量混合规则、搜索、监督学习、强化学习等实现，每级 1–4 个。LLM 每步直接出招，评分是（级，进度）二元组，跨游戏不可比。
  - **关系：** 分级锚点的思路和 HRW 相同，但它是实时对局，锚点也来自公开平台。它挑锚点的办法是 game-family-plan 第 4.2 节 (c) 的参照。
- **CodeElo: Benchmarking Competition-level Code Generation of LLMs with Human-comparable Elo Ratings**（Shanghaoran Quan, Jiaxi Yang, Bowen Yu 等 17 人；arXiv 2501.01257）<https://arxiv.org/abs/2501.01257>
  - **做了什么：** 把代码直接提交到 CodeForces，Elo 对齐平台的人类评级。
  - **关系：** 一种"绝对锚点"，锚在人类选手分布上；HRW 锚在冻结的 bot 上。
- **ALE-Bench: A Benchmark for Long-Horizon Objective-Driven Algorithm Engineering**（Yuki Imajuku, Kohki Horie, Yoichi Iwata, Kensho Aoki, Naohiro Takahashi, Takuya Akiba；NeurIPS 2025 Datasets & Benchmarks；arXiv 2506.09050）<https://arxiv.org/abs/2506.09050>
  - **做了什么：** 题目取自 AtCoder 启发式比赛，按分数评、长时程迭代，与人类比较。
  - **关系：** 同样是"在预算内做工程、靠迭代"。区别是没有对手，难度来自题目本身。
- **Measuring AI Ability to Complete Long Software Tasks**（Thomas Kwa, Ben West, Joel Becker 等 26 人；arXiv 备注 NeurIPS 2025；arXiv 2503.14499）<https://arxiv.org/abs/2503.14499>
  - **做了什么：** 用"人类完成所需时间"作绝对尺度，跨年份追踪模型能力。
  - **关系：** 这是"分数跨时间可比"的另一种做法，可以和 HRW 的冻结阶梯对照着写。
- **ARC-AGI-3**（ARC Prize Foundation）<https://arcprize.org/arc-agi/3>
  - **做了什么：** 没有说明的交互式网格游戏，要求在环境里探索、发现目标、建立世界模型；按相对人类的行动效率评分。公开、半私有、私有游戏集分开。
  - **待核：** 官方页面没写发布日期，第三方报道称 2026-03-25 发布（未核实官方来源）。
  - **关系：** 它用隐藏游戏集防污染、以人类为基线，可作 G6（规则发现）的参照。但它不是对抗游戏。

## 3. 模型直接出招（实时对局）

- **Game Arena: Strategic LLM Evaluation in Competitive Environments**（Bovard Doerschuk-Tiberi 等 62 人；技术报告；arXiv 2609.31473）<https://arxiv.org/abs/2609.31473> · [项目页](https://www.kaggle.com/game-arena)
  - **做了什么：** Kaggle 的国际象棋、扑克、狼人杀。国际象棋用 BT 拟合 Elo，最低分模型定为 0，用 bootstrap 求区间，另和 Stockfish 各等级做了近似对照；扑克用 BB/100；狼人杀用 GTE。
  - **相关发现：** 报告原话是"在每个游戏环境内强弱分层明显，但跨游戏不一致"。另有对提示和解析器影响结果的讨论。
  - **关系：** 支持"一个榜单不能代表所有游戏"，也就是多游戏画像的必要性。它是实时对局，排名是模型间相对的。
- **lmgame-Bench: How Good are LLMs at Playing Games?**（Lanxiang Hu, Mingjia Huo, Yuxuan Zhang, Haoyang Yu, Eric P. Xing, Ion Stoica, Tajana Rosing, Haojian Jin, Hao Zhang；ICLR 2026 poster；arXiv 2505.15146）<https://arxiv.org/abs/2505.15146> · [ICLR 页面](https://iclr.cc/virtual/2026/poster/10007223)
  - **做了什么：** 6 款单人游戏（平台、解谜、叙事类），用统一的 Gym 式接口，感知、记忆、推理模块可以分别开关；评了 13 个模型。摘要称相关分析显示"每个游戏探测的能力组合各不相同"（因子分析的具体做法未细查）。
  - **关系：** 论文 2 的直接先例。区别是它没有对手，也不写代码。
- **BALROG: Benchmarking Agentic LLM and VLM Reasoning On Games**（Davide Paglieri, Bartłomiej Cupiał, Samuel Coward, Ulyana Piterbarg 等 13 人；ICLR 2025；arXiv 2411.13543）<https://arxiv.org/abs/2411.13543>
  - **做了什么：** 多个游戏环境上的代理评测，简单的游戏还行，难的游戏明显吃力。
- **TextArena**（Leon Guertler, Bobby Cheng, Simon Yu, Bo Liu, Leshem Choshen, Cheston Tan；预印本 2025；arXiv 2504.11442）<https://arxiv.org/abs/2504.11442>
  - **做了什么：** 57 个以上文本对抗游戏，在线和人类及其他模型对局，用 TrueSkill 排名。
- **SnakeBench**（Greg Kamradt，ARC Prize Foundation，2025）<https://arcprize.org/blog/snakebench> · <https://snakebench.com/>
  - **做了什么：** 模型之间直接对战贪吃蛇，用 TrueSkill 排名。ARC Prize 的结论是，目前的模型还玩不出有意思的对局。
- **Large Language Models Play StarCraft II: Benchmarks and A Chain of Summarization Approach**（Weiyu Ma, Qirui Mi, Yongcheng Zeng 等 8 人；NeurIPS 2024 poster；arXiv 2312.11865）<https://arxiv.org/abs/2312.11865>
  - **做了什么：** TextStarCraft II 把星际 2 转成文本环境，LLM 代理能赢内置 Lv5 AI。
  - **关系：** 实时模式在 RTS 上的代表，以内置 AI 的难度等级作锚点。
- **CivRealm: A Learning and Reasoning Odyssey in Civilization for Decision-Making Agents**（Siyuan Qi, Shuo Chen, Yexin Li 等；ICLR 2024 spotlight；arXiv 2401.10568）<https://arxiv.org/abs/2401.10568>
  - **做了什么：** 基于 Freeciv 的不完全信息、多人、带外交的环境。RL 和 LLM 代理在完整游戏里都很吃力。
- **We Made Top AI Models Compete in a Game of Diplomacy. Here's Who Won.**（Alex Duffy，Every，2025-06-04）<https://every.to/p/diplomacy>
  - **做了什么：** 最多 7 个 LLM 玩改版外交，谈判、结盟、背叛，共 15 局，在 Twitch 直播；文章称代码已开源（仓库链接取自文章，没有单独核实）。
  - **关系：** 宣传手法的参照，用于展示池直播（game-family-plan 第 9.6 节）。它不是严格的评测。
- **AI GameStore: Scalable, Open-Ended Evaluation of Machine General Intelligence with Human Games**（Lance Ying, Ryan Truong, Prafull Sharma, Kaiya Ivy Zhao 等 12 人；arXiv 备注 NeurIPS 2026；arXiv 2602.17594）<https://arxiv.org/abs/2602.17594>
  - **做了什么：** 用 LLM 加人工改编 100 款应用商店和 Steam 上的游戏，和人类比较。最好的视觉语言模型在多数游戏上不到人类平均的 10%。
- **Confident at the moment of action: belief miscalibration in LLM play under hidden information**（Bhushan Kashinath Joshi；预印本 2026；arXiv 2608.24691）<https://arxiv.org/abs/2608.24691>
  - **做了什么：** 在一个国际象棋隐藏信息变体里，让模型每回合报告对隐藏王的概率。它的论点是：只看胜负会漏掉信念质量差的问题，赢了的模型信念也可能很差。
  - **关系：** 支持在胜负之外加过程指标（HRW 的 P1）。G1 若做信念类诊断，可以参考它。

## 4. 多游戏和能力结构

- **Triangulating LLM Progress through Benchmarks, Games, and Cognitive Tests**（Filippo Momentè, Alessandro Suglia, Mario Giulianelli, Ambra Ferrari, Alexander Koller, Oliver Lemon, David Schlangen, Raquel Fernández, Raffaella Bernardi；EMNLP 2025 Findings；arXiv 2502.14359）<https://arxiv.org/abs/2502.14359>
  - **做了什么：** 交互游戏比 MMLU 这类静态基准更能区分模型；认知测验显示，执行功能和社会情感能力与游戏表现关系更密。
  - **关系：** 论文 2 的论据，说明"游戏测到了静态基准测不到的东西"。
- **Observational Scaling Laws and the Predictability of Language Model Performance**（Yangjun Ruan, Chris J. Maddison, Tatsunori Hashimoto；NeurIPS 2024 spotlight；arXiv 2405.10938）<https://arxiv.org/abs/2405.10938>
  - **做了什么：** 用约 100 个公开模型说明，基准成绩可以用一个低维的能力空间解释。
  - **关系：** 论文 2 要回答"新游戏是否只是这个低维空间的又一次测量"，它也给出了多少模型才够做这类分析的参照。
- **Sample size in factor analysis**（Robert C. MacCallum, Keith F. Widaman, Shaobo Zhang, Sehee Hong；Psychological Methods 4(1):84–99，1999）<https://doi.org/10.1037/1082-989X.4.1.84>
  - **做了什么：** 因子分析所需的样本量没有固定下限，取决于公因子方差和每个因子有几个指标。
  - **关系：** 用来说明为什么一二十个模型只够做描述性分析（game-family-plan 第 7 节）。

## 5. 评测理论

- **Re-evaluating Evaluation**（David Balduzzi, Karl Tuyls, Julien Perolat, Thore Graepel；NeurIPS 2018；arXiv 1806.02643）<https://arxiv.org/abs/1806.02643>
  - **做了什么：** 提出 Nash averaging，让评测不受冗余任务和冗余对手的影响。
  - **关系：** HRW 每级放不同风格的 bot、级内取平均，就是从这里来的（DESIGN 第 2 节）。G3 的阶梯检查也要用它。
- **α-Rank: Multi-Agent Evaluation by Evolution**（Shayegan Omidshafiei, Christos Papadimitriou, Georgios Piliouras, Karl Tuyls, Mark Rowland, Jean-Baptiste Lespiau, Wojciech M. Czarnecki, Marc Lanctot, Julien Perolat, Remi Munos；Scientific Reports 9:9937，2019）<https://www.nature.com/articles/s41598-019-45619-9>（arXiv 1903.01373）
  - **做了什么：** 用演化动力学给多智能体排序，适用于存在循环克制的情形。
- **Real World Games Look Like Spinning Tops**（Wojciech M. Czarnecki, Gauthier Gidel, Brendan Tracey, Karl Tuyls, Shayegan Omidshafiei, David Balduzzi, Max Jaderberg；arXiv 2004.09468，2020；正式发表的会议未核实）<https://arxiv.org/abs/2004.09468>
  - **做了什么：** 现实中的博弈像"陀螺"：纵向是强弱，中段有大量非传递的循环。
  - **关系：** 解释 HRW 阶梯顶端为什么"谁克谁"多于"谁更强"，也说明搜索阶梯的风格为什么要多样。
- **The Leaderboard Illusion**（Shivalika Singh, Yiyang Nan, Alex Wang, Daniel D'Souza, Sayash Kapoor 等 13 人；预印本 2025；arXiv 2504.20879）<https://arxiv.org/abs/2504.20879>
  - **做了什么：** Chatbot Arena 的私下测试、选择性公布、数据不均等，让排名对平台本身过拟合。
  - **关系：** 相对榜单和公开对手容易被针对，这是隐藏阶梯的动机之一。

## 6. 多游戏框架和游戏生成

- **OpenSpiel: A Framework for Reinforcement Learning in Games**（Marc Lanctot, Edward Lockhart, Jean-Baptiste Lespiau 等；arXiv 1908.09453，2019）<https://arxiv.org/abs/1908.09453>：大量游戏环境，以及搜索和学习算法。可以作搜索阶梯（G3、G4）的算法来源。
- **General Video Game AI: a Multi-Track Framework for Evaluating Agents, Games and Content Generation Algorithms**（Diego Perez-Liebana, Jialin Liu, Ahmed Khalifa, Raluca D. Gaina, Julian Togelius, Simon M. Lucas；arXiv 备注已被 IEEE ToG 接收；arXiv 1802.10363）<https://arxiv.org/abs/1802.10363>：VGDL 和 GVGAI 竞赛，"同一个代理玩很多游戏"。
- **Ludii -- The Ludemic General Game System**（Éric Piette, Dennis J.N.J. Soemers, Matthew Stephenson, Chiara F. Sironi, Mark H.M. Winands, Cameron Browne；ECAI 2020；arXiv 1905.05013）<https://arxiv.org/abs/1905.05013>：用"ludeme"积木描述上千款棋盘游戏。
- **General Game Playing: Overview of the AAAI Competition**（Michael Genesereth, Nathaniel Love, Barney Pell；AI Magazine 26(2):62–72，2005）<https://doi.org/10.1609/aimag.v26i2.1813>：给出形式化的游戏描述，让系统不经人为干预就能玩，是多游戏评测的源头。
- **Design and Implementation of TAG: A Tabletop Games Framework**（Raluca D. Gaina, Martin Balla, Alexander Dockhorn, Raul Montoliu, Diego Perez-Liebana；arXiv 2009.12065，2020）<https://arxiv.org/abs/2009.12065>：现代桌游的通用接口，带动作空间、分支因子、隐藏信息等统计（摘要没提前向模型和搜索代理的预算设置，未核实）。
- **The Design Of "Stratega": A General Strategy Games Framework**（Diego Perez-Liebana, Alexander Dockhorn, Jorge Hurtado Grueso, Dominik Jeurissen；arXiv 2009.05643，2020）<https://arxiv.org/abs/2009.05643>：回合制策略游戏框架，用 YAML 定义游戏，围绕前向模型设计代理。和我们"一个框架、多款策略游戏"的思路最近。
- **GAVEL: Generating Games Via Evolution and Language Models**（Graham Todd, Alexander Padula, Matthew Stephenson, Éric Piette, Dennis J.N.J. Soemers, Julian Togelius；NeurIPS 2024；arXiv 2407.09388）<https://arxiv.org/abs/2407.09388>：用 LLM 加进化在 Ludii 规则空间里生成新游戏。可以参考它批量产出候选规则、再用代理筛选的做法，但正式题目仍要人工设计和审查。
- **Ludax: A GPU-Accelerated Domain Specific Language for Board Games**（Graham Todd, Alexander G. Padula, Dennis J.N.J. Soemers, Julian Togelius；预印本；arXiv 2506.22609）<https://arxiv.org/abs/2506.22609>：把棋盘游戏 DSL 编译到 GPU。和我们的"只用标准库、按 CPU 计时"方向不同，只作参考。

## 7. RTS、bot 比赛和长时程代理

- **StarCraft II: A New Challenge for Reinforcement Learning**（Oriol Vinyals, Timo Ewalds 等 25 人；arXiv 1708.04782，2017）<https://arxiv.org/abs/1708.04782>：SC2LE 环境。HRW 深度备忘已经引过它。
- **The First microRTS Artificial Intelligence Competition**（Santiago Ontañón, Nicolas A. Barriga, Cleyton R. Silva, Rubens O. Moraes, Levi H. S. Lelis；AI Magazine 39(1):75–83，2018）<https://ojs.aaai.org/aimagazine/index.php/aimagazine/article/view/2777>
  - **做了什么：** 三个赛道各用 4 张公开图和 4 张隐藏图。硬编码的 bot 在标准图上表现很好，在非标准图上明显变差。
  - **关系：** 支持隐藏地图的必要性，和 HRW 的公开图与 dev 图成绩差距（约 14 个百分点）一致。
  - **注：** `reports/phase-B-ceiling-game-depth.md` 引的是 ualberta 上的 PDF 链接，本次打开时 TLS 中断，改用 AAAI 期刊页。
- **Lux AI Season 2 规则** <https://github.com/Lux-AI-Challenge/Lux-Design-S2/blob/main/specs.md> 和 **NeurIPS 2024 Lux AI Season 3（Kaggle）** <https://www.kaggle.com/competitions/lux-ai-season-3>：资源、领地、长时程的 bot 比赛。第三季据参赛者总结有不可直接观测的常数（官方规则未细查）。HRW 设计时参考过 Halite 和 Lux（DESIGN 第 2 节）。
- **MLGym: A New Framework and Benchmark for Advancing AI Research Agents**（Deepak Nathani, Lovish Madaan, Nicholas Roberts 等 19 人；预印本 2025；arXiv 2502.14499）<https://arxiv.org/abs/2502.14499>：13 个研究型任务，前沿模型主要靠调超参提升，很少拿出新方法。和"模型多花工夫是否真能变强"（天花板实验、论文 3）有关。

## 8. 综述

- **AI for Games in the Foundation Model Era**（Meng Luo, Yanlin Li, Hao Li 等 10 人；预印本，2026-09 首版，2026-11 修订；arXiv 2609.16679）<https://arxiv.org/abs/2609.16679>
  - **做了什么：** 130 页，按"AI 输出怎么被使用"分成六种角色。结论之一是评测在有边界的游戏对局上最成熟。
  - **关系：** 写论文时的综述入口。

## 9. 未核实或未查

- RobotRumble、CodinGame 联赛、Battlecode、Stockfish fishtest、Halite 官方站：DESIGN 第 2 节引过，这次没有逐条打开核对。
- Spinning Tops 的正式发表信息，Choosing Well Your Opponents 的完整作者名单（只核到检索摘要）。
- StarSkirmish 的人写参照 bot 的源码是否对模型可见，页面没有说。
- ARC-AGI-3 的官方发布日期。

## 10. 对照表

"未细查"指这次没读全文，不等于没有。

| 工作 | 模型怎么参与 | 锚点 | 评分对手 | 噪声控制 | 过程分 |
| --- | --- | --- | --- | --- | --- |
| **HRW 1.0.0** | 写 bot，两阶段，有固定预算 | 绝对：M-balanced = 0，版本冻结，跨机器相邻复核 | 28 名成员中 23 名隐藏，评分图隐藏；开发时打不到 | 按 CPU 时间计时、机器绑定的计时锁、负载噪声检查、地图簇 bootstrap 区间 | 有：P1 占 25%，另报只看胜负的主分 |
| CodeClash | 写代码，多轮修改代码库 | 相对：模型间 Elo；CC:Ladder 是人写解的序列 | 其他模型；CC:Ladder 的人写解 | 大量锦标赛；计时未细查 | 排名看胜负；另有代码库质量分析 |
| StarSkirmish v0.1 | 写 bot，1 小时墙钟 | 两端固定（0 = 最弱 demo，100 = Stardust），但和模型 bot 联合拟合 | 12 个参照 bot，开发时可打练习赛 | 每模型 5 次运行取平均，不报区间 | 无 |
| BotzoneBench | 实时出招 | 绝对：分级 AI 锚点，（级，进度） | Botzone 平台 bot | 双座、固定种子、失败重赛 | 无 |
| Kaggle Game Arena | 实时出招 | 相对：BT Elo，最低者为 0；另近似对照 Stockfish | 其他模型 | bootstrap 区间 | 无，按游戏各用指标 |
| lmgame-Bench | 实时，单人游戏 | 游戏内得分 | 无 | 未细查 | 无，但感知、记忆、推理模块可开关 |
| TextArena、SnakeBench | 实时出招 | 相对：TrueSkill | 其他模型或人 | 未细查 | 无 |
| ALE-Bench | 写代码，启发式优化 | 题目得分，对照人类排名 | 无 | 未细查 | 分数本身是连续的 |
| CodeElo | 写代码，竞赛题 | 对齐人类 CodeForces 评级 | 无 | 未细查 | 无 |
| ARC-AGI-3 | 实时交互 | 相对人类的行动效率 | 无对手；有私有游戏集 | 未细查 | 行动效率 |
| AI Diplomacy | 实时谈判 | 无固定锚点 | 其他模型 | 15 局，没有统计 | 无 |

## 11. HRW 补上的空白

据我们所查，还没有一项工作同时具备以下六点：

1. 模型在写明的 token 和时间预算内写 bot，分两阶段，中间有一次自动练习赛；
2. 评分对手是分级的多风格阶梯，绝大部分隐藏，模型开发时打不到，因此不能像 RevengeBench 那样被反复试探；评分图也隐藏；
3. 锚点绝对，版本冻结，从不重标，迁移到另一台机器时做相邻复核，所以分数能跨时间、跨机器比较；
4. 按 CPU 时间计时，用机器绑定的计时锁统一每回合算力，并做负载噪声检查；
5. 过程分经过与强度的一致性、防刷分和区分度三项检验；
6. 有预登记、只用一次的留出复核，有加力作者的天花板实验，失败项如实披露。

最接近的是 StarSkirmish：同样写 bot，同样按分级参照定 0–100。但它的参照在开发时能打到，评级和被测 bot 联合拟合，没有区间，按墙钟限时。CodeClash 以模型间相对 Elo 为主。BotzoneBench 有分级锚点，但它是实时出招。

HRW 也有明显的短板，写论文时要正视：

- 只有一款游戏，别人有 6–8 款（lmgame-Bench、BotzoneBench、CodeClash）；
- 评测过的模型少；
- 没有与人类比较（ARC-AGI-3、CodeElo、ALE-Bench 都有）；
- 隐藏部分不能公开，和 NeurIPS 数据集轨道"代码和数据公开"的要求之间有张力（见 paper-plans.md 第 4 节）。
