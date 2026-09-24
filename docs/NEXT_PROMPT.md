# Coding Codex 执行 Prompt

任务：一次连贯的“已核对攻略→启发式决策链”整合。先核对 Git status、diff、HEAD 和最近提交，确认包含 H3-A11 `e2b5e435d7328fa5d847d8931c5d7053137d5e6a`，保留任何外部修改；阅读适用 `AGENTS.md`、检查 `.agents/skills/`，阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`（尤其第 6 节新材料吸收清单）、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 及当前来源 registry、经验 corpus、RAG、开局公式、公开结构、router、recommendation、prompt、候选剪枝和相关测试。

目的不是继续修 seed `47004` 的单张 Q、对子或炸弹个案，而是充分吸收已找到、可核对的攻略，再在整合后的同一版本检查这些旧问题。DeepSeek 仍是合法候选中的主要决策者；开局本地公式服务于时延约束，不另造一套覆盖模型的规则 AI。

## 整合实施

1. 先建立工作覆盖矩阵，逐项给出“新增条件化策略 / 与既有语义合并 / 仅公开信息背景 / 排除”及理由，并记录可观察触发、候选取舍、反例和投影层。资料包括既有 registry 的三篇王春国具名正文、唐人游 C 级转载；用户提供的仓库外 `D:\qq\downloadscao\掼蛋出牌策略详细版.txt`（只读、不入库）及其[公开高度匹配稿](https://post.smzdm.com/p/a5xk3dpl/)；[掼蛋大师策略目录](https://guandanmaster.org/strategy.html)中已筛出的[出牌顺序](https://guandanmaster.org/strategy/play-order-strategy.html)、[控牌](https://guandanmaster.org/strategy/control-tactics.html)、[炸弹时机](https://guandanmaster.org/strategy/bomb-timing.html)、[搭档配合](https://guandanmaster.org/strategy/partner-cooperation.html)和[残局](https://guandanmaster.org/strategy/endgame-guide.html)。两份新材料不是同一来源；公开匹配不证明百条原作者，网站运营方也不是逐篇专家署名。可浏览这些公开正文核对具体定位，但别复制整份百条或大段受版权保护文字。若仓库外文件不可访问，可用公开匹配稿与本文审计清单推进，并明确该限制。
2. 新材料按**单项主张**筛选，不整站或整份批量入库，也不因 C 级而整体弃用。重点把 `docs/STRATEGY_SOURCE_AUDIT.md` 第 6 节的开局角色/试探、清孤张与拆组、四/五炸和通配残余、牌权回手、队友送牌/让牌、危险对手、残局与公开记牌落实到同一条链；已由 B 级或现有 C 级条目覆盖的语义合并，不制造重复 RAG 权重。冲突须保留条件：百条中间单张与低成本小单、对子先行与网站单张先行、四炸经济与五炸清空点数组，都不能变成统一点数/张数公式。排除未披露概率、暗牌必然推断、绝对化“必须炸”、心理/速度/表情及贡还/多局内容。尤其不得采用网站[记牌文](https://guandanmaster.org/strategy/memory-card-method.html)的单副牌数量、[炸弹顺子文](https://guandanmaster.org/strategy/bomb-straight-combo.html)的非法 `JQKA2` 或出牌后变更声明语义；以项目引擎/`docs/INVARIANTS.md` 为规则真值。不能从仅有目录/商品介绍的出版物推导打法。作者/账号、URL、等级、定位与激活状态只留在独立 provenance registry；知识正文、检索评分、冲突扫描、prompt 不含治理信息。C 级通过核对的定性原则仅为可撤回 `soft_hypothesis`，不单独驱动本地直出或模型后覆盖。
3. 在一个实现任务中同步落地来源策略：把可用主张拆成条件化知识，从公开 observation 与完整 canonical actions 派生必要的结构/牌权/队友/对手/残局关系，让 router、RAG、recommendation、候选对照和最终 prompt 对同一条件达成一致。每项可行动主张要有公开激活条件、合法候选间的具体比较和可推翻它的反例；记牌仅呈现公开事实/不确定信号，不虚构暗牌。既有十域可沿用，但不能只通过 metadata 或条目数验收；适用状态的真实最终 prompt 必须表达实质取舍，不适用时不强行命中。保持 final candidate `<=80`、推荐 ID 闭环、原始 action ID/source 保真和 fail-closed 降级。
4. 把开局公式整理成来源条件表：何时可快速本地直选、何时只给 DeepSeek 模型前定式、何时不适用。可扩充公开条件明确且跨关系 fixture 稳定的 B 级定式，不要把所有经验缩成空泛 RAG；但本地直出必须排除拆组、协同、阻断、回手和资源歧义，且不能由新 C 级材料单独驱动。不要新增神秘分数、现场 seed/点数特判或成功模型后的策略覆盖；有条件冲突时展示替代路线和反例，交给 DeepSeek 裁决。
5. 修改范围限于与上述整合直接相关的 `agents/`、`rag/` 和 `tests/`；必要时可改 `evaluation/` 的现有离线 fixture，不改 `engine/` 规则真值、Botzone 协议/证据、配置、`.env` 或规划 docs。先补关系型与多 seed 引擎测试，覆盖开局/自由领牌、低/中单张与自然对子冲突、拆组与清孤张、控制/回手、跟牌、队友协同、危险对手、同点四/五炸与通配、残局和记牌不确定性。测试要穿过实际检索及最终禁网客户端 Request 组装，不只检查 registry 或中间对象；fake transport 验证模型成功动作仍是最终候选中的原始 ID、source=`model`。

## 整合后验收，旧问题最后检查

1. 完成整合实现、直接相关测试、主规则回归和全量测试后，再只读核对 `D:\VsCodeProject\BotzoneWorkspace` 已审计的 seed `47004` 六份 evidence 路径、大小、SHA-256 与 `docs/PROJECT_STATUS.md` 旧 inventory 一致。若不符，不读正文、不找替代；仍交付已通过的通用整合结果，并报告旧局复核 `inconclusive`。若一致，只在内存中读取 ACK trace 的原始公开 observation/canonical actions，禁网重放三个历史观察：四/五炸残余关系、较高普通单张开局、自然对子/单张清理。只检查当前本地公式会直出还是让给模型、关键候选是否可见、来源原则/具体比较/反例是否进入最终请求；历史所选动作不等于当前模型结果。若整合后仍有可复现输入缺口，只报告层级与反例，交给下一独立修复任务；不要在本轮再追加现场点数特判。
2. 本任务不调用真实 DeepSeek、不运行 Botzone/live/connector/browser/preflight、不清理 evidence、不读旧 H3 ledger、系统 Temp 或 `.env`。任何历史手牌、逐动作牌面、原始 ID、prompt、模型文本、URL、token、凭据、match/binding 标识及异常正文不得输出或持久化。旧局只是后验覆盖检查，不能证明新版模型将选什么或胜率提高。H3-A7–A11 的 RuleBased 续局代理标签不作为整合验收门槛，也不再新增此类代理阶段。

## 交付

提交仅本轮自有业务/知识/测试文件，按明确路径暂存；运行相关、主规则与 `python -m unittest discover -q`，检查完整 diff 与 `git diff --check`。报告新百条与网站主张的覆盖矩阵（含合并/排除及具体理由）、实际激活的独立来源条目、三类旧问题的整合后低敏检查、候选/prompt/source 守恒、测试数、commit、最终 Git status 和保留的外部修改。规划 Codex 先独立复审实现，再安排一次集中真实模型/现场验证；只有该后验验证仍有具体问题，才另立针对性修复，不再按 H3-A 字母后缀无限拆任务。
