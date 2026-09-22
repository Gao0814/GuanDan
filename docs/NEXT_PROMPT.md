# Coding Codex 执行 Prompt

任务：H3-A5——一次性修正“来源经验的公开适用条件”与八场诊断中的场景语义，不直接优化某个动作、更不增加成功模型后的覆盖。H3-A4r技术审计已完成：8次success、0重试，合法候选与`model` source守恒。但当前八个fixture全被公开phase分为残局；`neutral_soft_pair`实际渲染炸弹C级条目`exp_bomb_wildcard_001`，没有渲染目标对子C级`exp_soft_pair_probe_001`，且该局没有炸弹/通配候选；`low_cost_single`也未检验开局。因此本任务先修“知识投影是否适用”和“fixture是否真的代表目标”，不得据旧类别声称模型选择错误。

## 开始与边界

1. 阅读适用`AGENTS.md`、检查`.agents/skills/`；本任务不是Botzone live或清理。阅读`README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`及相关生产代码、语料和测试。检查Git status、diff、HEAD及最近提交；HEAD须包含`81506f802f22e492d2cfec54f92061e45f5ffa04`，保留他人修改，提交只包含自有文件。
2. 允许最小修改`agents/rag_advisor.py`、必要的知识语义metadata/loader、`evaluation/h3_model_probe_fixtures.py`和直接相关`tests/`。不得改`engine/`规则真值、DeepSeek成功动作路径、Botzone协议、来源registry的治理等级/作者信息，或新增模型后策略覆盖。若需其它生产文件，先以具体反例说明必要性并保持最小范围。不能在业务代码中硬编码现场seed、牌面或绝对路径。
3. 真实DeepSeek请求/重试、Botzone/live/connector/browser/preflight均为0；不读写`.env`、`D:\VsCodeProject\BotzoneWorkspace`、seed`47004` evidence、系统Temp流文件或旧`h3-a2r.jsonl`/`h3-a4.jsonl`/`h3-a4r.jsonl`。不创建新的仓库外evidence。H3-A4r的原fixture/代码状态由其Git HEAD和ledger封存；本任务修改后的fixture是新版本，不能与旧动作类别称作同状态对照。

## 实现目标

1. 在现有RAG检索中建立通用、fail-closed的公开候选适用条件，而不是为某个source ID或点数写特判。`exp_bomb_wildcard_001`的正文要求候选涉及炸弹或逢人配：没有这种canonical候选时，不得检索、接受或渲染该C级假设；有真实机会时仍可检索。`exp_soft_pair_probe_001`只在其既有opening/midgame、自由领牌或跟牌范围内，且存在符合语义的自然对子机会时激活。所有机会只从`observe()`与完整`legal_actions()`公开payload得出，规则合法性仍由引擎负责；未知/畸形条件fail closed。作者、等级、URL、治理状态不进入检索评分、冲突扫描或prompt；C级仍是可撤回软假设，不升级为硬公式。
2. 修正诊断fixture和必要资格断言：`low_cost_single`确实进入公开`opening / lead_opening`（保留结构安全小单、高单/控制资源及常见对子竞争）；`neutral_soft_pair`确实处于公开opening或midgame、存在自然pair/triple与普通single，实际RAG命中并在最终prompt渲染`exp_soft_pair_probe_001`，而不是用任意C级marker充数。其余六场应保持各自公开关系/紧急性目标；明确哪些本来就是endgame，不要求全部变成opening。构造必须经引擎`observe()`和完整canonical`legal_actions()`，不得伪造hand_count、phase、RAG hit或模型输入，不使用现场seed/动作ID。
3. 测试既要有“无炸弹/通配候选却检索到炸弹C级”的原反例，也要有有机会时可检索的正例；对子软假设的适用/不适用、source ID与最终实际请求prompt渲染分别断言。八场新版本资格仍须全部`ready`，保持80项上限、推荐闭环、request body绑定、分类覆盖、原始合法ID/source和无后置覆盖。不要为了强行ready而放宽旧资格门槛；若某个场景目标本身与公开策略冲突，给出固定低敏失败阶段并交回规划Codex，不编造策略最优答案。

## 验证与交付

- 运行新/相关RAG、provenance、H3 fixture、recommendation、DeepSeek prompt与Botzone observability定向测试，主规则回归及`python -m unittest discover -q`；捕获可审计汇总，检查`git diff --check`与完整diff。离线多状态检查至少覆盖“有/无炸弹通配机会”“有/无自然对子机会”和opening/midgame/endgame边界，不只一个固定fixture。
- 只按明确路径暂存并提交本轮自有源码/语料/tests，报告commit、变更范围、八场新版本公开phase/RAG scene/目标soft source的固定低敏摘要、反例结果、测试计数、最终Git status和任何外部修改。不得输出手牌、牌面、action ID、prompt、模型文本或凭据；不报告策略胜率或H3-A4r改善。
