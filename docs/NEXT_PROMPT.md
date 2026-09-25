# Coding Codex 执行 Prompt：多牌型开局选择

项目所有者已恢复此前批准的“多牌型开局选择”任务。个人启动器在页面刷新后也由所有者确认显示“已连接”；本任务不继续连接差异诊断，也不把刷新现象解释为已证实的代码或网络根因。这是一项完整的算法实现与离线验收任务，不要拆成一串仅做探针的 H3 子阶段。开始时阅读根 `AGENTS.md`、适用 Skill、`docs/PROJECT_STATUS.md` 顶部、`docs/CLEAN_HANDOFF.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`README.md`、开局公式/DeepSeek Agent/公开候选结构/RAG/推荐路径及对应测试；检查 Git status、diff、HEAD，保留他人修改。以实际源码为准，不把历史执行报告当事实。

目标：对固定四人、级牌 `2`、无贡单局的合法**开局自由首出**，不再将本地经验等同于“小单优先”。从完整 canonical `legal_actions()` 和公开 observation 出发，让每个有效开局都能获得有来源的候选结构与首出意图比较；在公开证据形成清晰首选时，本地公式可直接选择单张、自然对子、三张、顺子或其他有明确经验依据的合法牌型。若多个路线存在实质性取舍，向 DeepSeek 提供简洁、具体的模型前比较，由其选择实际展示的合法 ID。尽可能扩大人类经验对各种开局牌力与牌型的覆盖，但**覆盖不等于每局强制本地直选**，也不预设单张、某一牌型或某个点数永远优先。

可复用的已核实来源是 `rag/experience_corpus/basic_human_experience.md` 与 `rag/experience_provenance.json` 中的 B 级开局/组牌原则，特别是王春国《如何打好一把掼蛋的前半程》关于围绕强弱定位组牌、小单/对子/三张/顺子首攻与回手的条件性描述；现有 C 级条目仍只能作为可撤回提示。来源治理字段仍只留在 registry，不进检索评分、知识正文或 prompt。先建立可审计的“来源主张 → 公开适用前提 → 候选比较 → 本地直选或模型前信息”映射，再实现；不得补编未核实口诀、固定点数偏好或未经校准的秘密权重。特别要比较动作后的余组、孤张用途/负担、拆组、通配/炸弹/控制资源、可公开验证的回手路线与队友/对手紧急性。不能把所有参与某个理论组合的单牌一律判为不可出，也不能把“未识别到用途”断言为未来无用。

实现时保留现有 only-pass/立即出完优先级、引擎合法性边界、`OPENING_FORMULA_ENABLED` 开关与原始 action ID。公式仅处理满足公开开局/free-lead 门槛的状态，不影响跟牌或非开局；输入畸形时继续 fail closed。明确、稳定地解决跨牌型候选比较和并列冲突，避免候选顺序、花色或 hard-coded seed 决定策略。若本地直选，source 使用既有 `local_opening_formula`；若让模型选择，成功结果保持原始展示候选 ID 与 `model` source，不能添加或恢复任何成功模型后的策略动作覆盖。尽量复用现有 `action_structure`、router、RAG、recommendation 与 prompt 投影；必要变更保持最终候选 `<=80`、推荐 ID 闭环和有界 prompt，不把大段逐候选重复说明重新引入。

验收至少包括：引擎生成的真实 27 张初始局面、强/中/弱牌及多种牌型组合；确有清晰非单张首出的本地直选正例；低成本单张优于高价值单张、自然对子/三张清理、顺子不拆高价值结构、回手不足、资源冲突、队友/对手公开紧急等正反例；所有本地动作均属于完整 canonical 集；模型分支的实际禁网 Request 具有对应关系/反例、候选闭环和 `model` source；固定种子多局初始状态的直选牌型分布与 `None` 比例，报告事实而不人为追求单一覆盖率。对 seed `47005` 不读取或改写固定 workspace evidence，也不把该次 `platform_error` 当作模型时延证据。若需要解释速度，只报告离线本地命中率、请求路径与 prompt 规模；没有计时证据不能宣称真实延迟改善。

运行直接相关测试、主规则回归和全量 `unittest`，显式禁用测试进程的 dotenv 加载；执行 `git diff --check`，检查无现场 seed/点数特判、无新后置覆盖与旧 decision source 主动路径。不要修改 engine、Botzone 协议、CLI 运行模式、`.env`、Codex/个人两个 workspace、旧 ledger 或规划 docs；不运行 Botzone/live/connector/browser、真实 DeepSeek 或网络。只暂存并提交自己改的业务、知识与测试文件。报告源策略覆盖映射、不同牌型直选的真实引擎实例计数、模型分支比例、测试结果、commit、最终 Git status 与任何保留的外部修改；不声称由此证明胜率或解决平台 `platform_error`。
