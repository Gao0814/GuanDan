# Coding Codex 执行 Prompt

这是一个新的 Coding Codex 任务。不要依赖其他对话的隐含上下文，请从当前仓库重新建立事实。

你的职责是实现和测试业务代码；项目规划文档由规划 Codex 维护。开始前依次：

1. 阅读并遵守根目录及适用范围内的 `AGENTS.md`。
2. 检查 `.agents/skills/`；本任务不是 live 或 workspace 清理，不得执行这两个 Skill 的现场动作。
3. 阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/RAG_KB.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`。
4. 检查 Git status、HEAD 和最近提交；起点必须包含 `66009fcddf1d795293de419309f8459bb002908e` 且工作树 clean，不能把外部修改混入提交。
5. 完整阅读现有 experience corpus/provenance、loader/retriever、`opening_strategy.py`、`strategy_router.py`、`strategy_intent_prompt.py`、`rag_advisor.py`、`action_structure.py`、`deepseek_client.py`、`deepseek_ai.py`、Botzone DeepSeek factory 接线和相关测试，再确定最小一致实现。

## 已封板基础

- `5dbdd2c` 已建立知识/治理双平面、窄开局快速路径、第一层 pair 召回和公开残余结构。
- `66009fc` 已将真正发送给模型的最终候选硬限制为 80，稳定保留自然 single/pair 并对 overflow 做有界代表压缩。规划 Codex 独立通过230项相关、39项主规则、720项全量和500个真实引擎初始局面性质检查。
- 三个旧策略覆盖 source 仅作 legacy read compatibility；当前成功模型动作保持原始合法 ID 和 `model` source。

不要重新实现 H3-A0/H3-A0a，也不要恢复任何成功模型后的策略动作覆盖。

## 目标：H3-A1 来源策略的 DeepSeek 模型前投影

用一个连贯实现批次，把已审计公开材料中具有实际打法意义的定性内容较完整地接入策略知识、公开特征、decision chain/router、RAG、开局模型前推荐和 structured prompt。项目目标是减少 DeepSeek 的无效搜索并提高其原始策略选择质量，不是扩张本地规则 AI。

目标链路为：

`公开局面特征 -> 场景与目标 -> 条件化人类经验 -> 候选结构比较 -> 定式推荐及反例 -> DeepSeek 原始选择`

### 一、建立十个策略域

经验知识和运行时语义应能覆盖以下目录；可以由多条短知识共同覆盖，不得为凑数量编造策略：

1. 总体目标与冲突优先级；
2. 开局与自由领牌；
3. 手牌结构和拆牌成本；
4. 控制牌与回手资源；
5. 跟牌与牌权争夺；
6. 队友协同；
7. 危险对手阻断；
8. 炸弹和通配牌管理；
9. 残局规划；
10. 不确定信息与试探成本。

每条知识正文采用紧凑的“适用条件 / 策略目标 / 建议倾向 / 反例与调整”表达。允许增加经过严格枚举验证的 `strategy_domain`、`guidance_mode` 等运行时语义标签；作者、标题、出版物、URL、来源等级、locator 和激活状态只能放在 `experience_provenance.json`，不得进入正文、检索评分、冲突扫描、query 或模型 prompt。

### 二、允许采用的来源内容

只使用 `docs/STRATEGY_SOURCE_AUDIT.md` 已核对的公开正文及以下明确边界；不需要联网，不得从商品目录或未读书籍扩写具体打法。

具名 B 级王春国系列可直接形成条件化 `source_principle`：

- 按主攻、助攻、中性定位组牌；减少总手数、改善牌型、减少单牌并形成可控内循环，局势变化时调整，不能机械套用。
- 强牌的小单首攻、对子/三张的中性表达、连续牌型或顺子可能表达的意图；这些是沟通和计划依据，不是每局固定动作。
- 前半程需要在进攻、让牌、低成本试探、观察牌势和搭档协同之间权衡。
- 记牌优先关注王、级牌、A、10、5和公开断张；10/5是组合节点、断张可能关联炸弹，但只能作为软推断，不能提升为暗牌事实。
- 根据本家定位调整记牌重点；优势时先设计自己的走牌，同时兼顾搭档。
- 自己难以走完时，应考虑限制对手、给搭档传递合适牌型并避免无意义盖住搭档。
- 公开剩余张数与回手资源可用于残局牌型规划；原文的剩余张数口诀只作为信息不足时的软参考，必须允许公开历史、牌权和具体结构推翻。
- 四张残局具有普通牌型难以一次走完的特殊性，但仍需考虑炸弹、搭档送牌和对手威胁。

C 级旧转载只允许把以下定性内容作为 `soft_hypothesis`：对子可用于侦察/控制；小对子可借三带二处理；不要为组顺而无谓增加孤张或破坏其他结构；通常保护炸弹；识别并限制强势对手、协助更可能走完的搭档；从多条后续路线而不是单步得失看局面。

不得采用该转载的百分比、平均手数、样本统计、贡还内容或“必然/不二/真理级”等绝对化表述。`soft_hypothesis` 可以进入 RAG/prompt 和离线 fixture，但不得驱动本地直接动作；与 B 级正文、规则真值或当前公开局面冲突时必须让位。三个只有书目/商品介绍的出版物继续 `registry_only`。

### 三、公开候选结构比较

在现有残余结构摘要基础上，为最终候选提供紧凑、确定、可测试的策略差异；只计算能从 observation、手牌和 canonical actions 复现的事实。至少覆盖：

- 是否一次出完、carrier 张数、牌型和是否使用通配；
- 所出点数组是否清空、动作后残余孤张点数、估计剩余点数组；
- 是否只打出某对子/三张/炸弹点数的一部分而留下更碎的同点数牌；
- 自然单张的相对点数成本，以及是否消耗王、当前级牌、A等明确控制资源；
- 自然对子相对单张能否一次处理两张并减少残余点数组；
- 炸弹长度和动作后是否留下同点数孤张；
- 可由公开信息确认的队友/对手剩余张数、当前领牌关系和紧急程度。

这些字段是非指令性的候选比较，不得自行裁决合法性或删除动作。证据不完整时省略对应字段，不能猜测。最终动作仍不超过80、保持原始ID、稳定顺序和签名去重；新增文本必须有固定长度/条数预算。

### 四、decision chain、router 与模型前建议

- opening 不能继续只返回 `opening_not_routed`。合法公开输入应得到可解释的开局场景、粗粒度 intent 和有界理由。
- 在保持现有 `run_out/control/support_teammate/block_opponent/finish_now` 兼容的基础上，提供有界的有序目标、策略域和反例检查；不要把所有知识压成一个含义过载的 reason。
- 优先级必须能表达：立即走完；队友/对手公开紧急性；减少残余分组；低成本清理弱牌；保护组合与控制资源；信息不足时降低试探成本。动态局面下这些目标可以覆盖普通开局建议。
- 允许新增一个共享、fail-closed 的 opening/strategy recommendation 结构，返回推荐原始 action ID 或短名单、公开理由和反例条件。它只能从 canonical actions 选择 ID，不能过滤合法候选。
- 现有强牌、回手资源、结构安全自然小单的开局本地快速路径可以保留并复用共享分析；不得把 C 级口诀或中性场景新增为本地直接动作。
- 其他开局定式，包括对子/三张的中性表达、低成本试探和顺子/连续牌意图，只作为 recommendation 给 DeepSeek 验证。存在搭档协同、危险对手、控制资源、结构或信息歧义时必须调用 DeepSeek。
- 若本地快速路径命中，保持现有 local shortcut 及 source 守恒；若调用模型，recommendation、RAG 和 router 都只能出现在模型之前。模型成功返回最终候选中的合法 ID 后原样返回并记录 `model`。

### 五、RAG 与 prompt 投影

- RAG 检索由统一 phase、scene、intent、strategy domain 和公开特征驱动；不能由来源作者、URL或 opaque ID 提升命中。
- B 级 `source_principle` 与 C 级 `soft_hypothesis` 在运行时必须可区分；soft 内容用非绝对措辞，并始终带允许局面推翻的反例语义。
- structured prompt 应清晰分离：公开事实、策略目标、命中经验、候选结构差异、推荐方案及反例检查。不要把治理 metadata 暴露给模型。
- 推荐表达应类似“基于公开结构首先考虑 X；请检查队友/对手紧急性、牌权计划或组合损失是否推翻”，让 DeepSeek验证聚焦方案，而不是要求机械执行。
- RAG 无命中、recommendation 不适用或任一派生器异常时 fail closed：保留原始公开输入和最终合法候选继续调用模型。
- 不复制整篇来源正文，不在 prompt 中加入长引文；知识条目使用短量转述。

## 必须覆盖的关系型 fixture

不得针对 seed、具体 action ID、Q/4/10 或现场手牌写死；使用多组等价变体证明关系：

1. 自由首出同时有结构安全低自然单张和更高普通单张：候选事实与建议能表达较低试探/清理成本，同时保留控制资源；模型仍可返回任一最终合法 ID 且 source 为 `model`。
2. 同点数四张/五张炸弹同时存在：两者原始 ID 均可见，长度、清空点数组、残余孤张和估计分组差异准确；不得本地强制选五张。
3. 最小自然对子与单张同时存在：最终模型候选继续保留二者；结构比较能表达对子一次清理两张和拆对留下孤张的差异。加入队友接近走完的公开变体，验证协同目标进入模型前输入但不直接选牌。
4. 强牌且满足现有严格条件时，本地小单快速路径稳定；去掉回手、使小单参与组合或增加紧急公开条件后快速路径退出，模型收到建议/反例。
5. 中性开局对子/三张、低成本试探、强组顺子风险均只能形成软建议，不能成为 local shortcut。
6. 队友控桌、危险对手、短残局最少分组三个既有专用输入继续生效；三个 legacy source 仍只读兼容。
7. RAG 对十个策略域有可审计覆盖；改变 registry 中作者、标题、URL或 locator 后，检索结果、query、排序和最终 prompt 逐字节不变。
8. C 级 soft 条目可命中模型输入，但改为 candidate/registry-only、缺字段、scope冲突或畸形记录后不激活；其统计数字和贡还内容从不进入 prompt。
9. 大候选、wildcard overflow、follow/pass、only-pass、一次出完、malformed payload、RAG空结果和派生异常均保持预算与降级契约。

## 禁止事项

- 不得修改 `engine/` 规则真值、Botzone 协议/session/audit/trace schema、`.env`、日志或仓库外文件。
- 不得运行 live、connector、浏览器或真实 DeepSeek 请求；本任务全部使用离线/fake-client测试。
- 不得读取、复制或针对 seed `47004` 的私密 evidence 编码。
- 不得新增成功模型后的 selector、guard、override、decision source 或 RuleBased 选择复制。
- 不得用新的神秘总分、牌点奖励或无来源阈值代替条件化策略；现有 hand evaluator 的固定权重不扩大为策略真值。
- 不得把经验写入规则引擎，不得让 RAG/recommendation 改变合法性或生成 action。
- 不得修改规划 docs；只提交业务代码、RAG corpus/registry 和 tests。

## 验证

1. 运行新增的 provenance、RAG、strategy domain、opening recommendation、router/prompt、candidate structure 和三个核心反例定向测试。
2. 运行 H3-A0/H3-A0a 的 opening、pruning、action structure、DeepSeek fake-client、legacy source、Botzone observability/trace/benchmark 回归。
3. 运行主规则回归：

   `python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q`

4. 运行全量：

   `python -m unittest discover -q`

5. 运行 `git diff --check`，扫描生产路径确认没有 seed/点数特判、新 post-model override/source、治理字段 prompt 泄漏或 registry-only 内容激活。

## 提交与报告

只提交本任务的业务代码、RAG corpus/registry 和 tests；不要修改规划 docs。提交前后检查 status/diff，只显式暂存自有文件。

报告必须包含：

- 十个策略域分别由哪些知识条目、公开特征和路由/prompt输入覆盖；
- B级原则与C级soft hypothesis的运行时边界，以及未采用的统计/书目内容；
- opening本地快速路径与model-before recommendation的精确边界；
- 三个核心反例及多变体测试结果，模型原始ID/source保真结果；
- 修改文件、定向/主规则/全量测试数量、`git diff --check`和生产扫描结果；
- commit hash、最终Git status、保留的外部修改/evidence；
- 当前范围内尚未解决的真实风险。固定级牌2、四人、无贡、单局是既定范围，不列为风险。
