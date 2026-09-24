# Coding Codex 执行 Prompt

任务：一次连贯的“来源攻略→启发式决策链”整合。先核对 Git status、diff、HEAD 和最近提交，确认包含 H3-A11 `e2b5e435d7328fa5d847d8931c5d7053137d5e6a`，保留任何外部修改；阅读适用 `AGENTS.md`、检查 `.agents/skills/`，阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 及当前来源 registry、经验 corpus、RAG、开局公式、公开结构、router、recommendation、prompt、候选剪枝和相关测试。

目的不是继续修 seed `47004` 的单张 Q、对子或炸弹个案，而是充分吸收已找到、可核对的攻略，再在整合后的同一版本检查这些旧问题。DeepSeek 仍是合法候选中的主要决策者；开局本地公式服务于时延约束，不另造一套覆盖模型的规则 AI。

## 整合实施

1. 先从 `docs/STRATEGY_SOURCE_AUDIT.md`、`rag/experience_provenance.json` 及对应可访问的公开正文建立工作中的覆盖矩阵：逐条记录可行动定性原则、可观察触发条件、策略目标、候选间取舍、反例/冲突和当前落点。只读核对已登记的三篇具名专家文章与已批准 C 级转载的实质正文；允许为核对公开来源浏览网页，但不要复制大段受版权保护文字、未披露方法的统计或绝对化断言。不能从仅有目录/商品介绍的出版物推导打法。C 级可用定性内容应作为明确可撤回的软假设充分利用，不因等级低而整体丢弃；作者、URL、等级与激活状态只保留在独立治理 registry，不进入知识正文、评分或模型输入。无需为条目数设人为上限或达标数字，目标是覆盖已核对的实质建议而不是扩写空泛口号。
2. 在一个实现任务中同步落地来源策略：将大而泛的经验拆成条件化、可检索的知识单元；从公开 observation 与完整 canonical actions 派生必要的结构/牌权/队友/对手/残局关系；让 router、RAG、recommendation、候选对照和最终 prompt 对同一策略条件达成一致。每项可行动原则都要有公开激活条件、适用的合法候选取舍及能推翻它的反例；仅供记牌或说明不确定性的原则则明确标为信息背景，不伪造动作对照。既有十个域可继续使用，但不得仅验证 metadata 标签或总覆盖数；真实最终 prompt 需在适用状态表达具体取舍，不适用时不强行检索。保持 final candidate `<=80`、推荐 ID 闭环、原始 action ID/source 保真和 fail-closed 降级。
3. 把开局公式整理成清晰的来源条件表：何时可快速本地直接选择、何时只作为模型前定式推荐、何时不适用。可根据已核对的人类打法扩充适用条件，不要仅因谨慎而把所有内容压成一句泛化 RAG；但本地直出必须用公开条件排除拆组、协同、阻断、回手和资源歧义，且不能由 C 级软假设单独驱动。不要新增神秘分数、现场 seed/点数特判或成功模型后的策略覆盖。若来源之间有条件冲突，向 DeepSeek 展示取舍及反例，而不是硬编码统一动作。
4. 修改范围限于与上述整合直接相关的 `agents/`、`rag/` 和 `tests/`；必要时可改 `evaluation/` 的现有离线 fixture，不改 `engine/` 规则真值、Botzone 协议/证据、配置、`.env` 或规划 docs。先补关系型与多 seed 引擎测试，覆盖开局/自由领牌、拆组与清孤张、控制/回手、跟牌、队友协同、危险对手、炸弹/通配、残局、记牌不确定性及冲突场景。测试必须穿过实际检索和最终禁网客户端请求组装，不只检查 registry 或中间对象。用 fake transport 验证模型成功动作仍是最终候选中的原始 ID、source=`model`。

## 整合后验收，旧问题最后检查

1. 完成整合实现、直接相关测试、主规则回归和全量测试后，再只读核对 `D:\VsCodeProject\BotzoneWorkspace` 已审计的 seed `47004` 六份 evidence 路径、大小、SHA-256 与 `docs/PROJECT_STATUS.md` 旧 inventory 一致。若不符，不读正文、不找替代；仍交付已通过的通用整合结果，并报告旧局复核 `inconclusive`。若一致，只在内存中读取 ACK trace 的原始公开 observation/canonical actions，禁网重放三个历史观察：四/五炸残余关系、较高普通单张开局、自然对子/单张清理。只检查当前本地公式会直出还是让给模型、关键候选是否可见、来源原则/具体比较/反例是否进入最终请求；历史所选动作不等于当前模型结果。若整合后仍有可复现输入缺口，只报告层级与反例，交给下一独立修复任务；不要在本轮再追加现场点数特判。
2. 本任务不调用真实 DeepSeek、不运行 Botzone/live/connector/browser/preflight、不清理 evidence、不读旧 H3 ledger、系统 Temp 或 `.env`。任何历史手牌、逐动作牌面、原始 ID、prompt、模型文本、URL、token、凭据、match/binding 标识及异常正文不得输出或持久化。旧局只是后验覆盖检查，不能证明新版模型将选什么或胜率提高。H3-A7–A11 的 RuleBased 续局代理标签不作为整合验收门槛，也不再新增此类代理阶段。

## 交付

提交仅本轮自有业务/知识/测试文件，按明确路径暂存；运行相关、主规则与 `python -m unittest discover -q`，检查完整 diff 与 `git diff --check`。报告来源覆盖矩阵的已纳入/未纳入及理由、三类旧问题的整合后低敏检查、候选/prompt/source守恒、测试数、commit、最终 Git status 和保留的外部修改。规划 Codex 先独立复审实现，再安排一次集中真实模型/现场验证；只有该后验验证仍有具体问题，才另立针对性修复，不再按 H3-A 字母后缀无限拆任务。
