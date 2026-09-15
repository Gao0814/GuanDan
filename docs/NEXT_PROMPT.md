# Coding Codex 执行 Prompt

这是 H3-A1 的纠错续作。不要依赖其他对话的隐含上下文，请从当前 worktree 重新建立事实。

你的职责是修改业务代码、RAG 与 tests；项目规划文档由规划 Codex 维护。开始前依次：

1. 阅读并遵守根目录及适用范围内的 `AGENTS.md`。
2. 检查 `.agents/skills/`；本任务不是 Botzone live 或 workspace 清理，不执行这两个 Skill。
3. 阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/RAG_KB.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`。
4. 检查 Git status、HEAD、最近提交及 `d20dba3^..d20dba3` 的完整 diff。起点必须精确包含且优先直接位于 `d20dba36c697ac068b40b9f99c1be29715ee00f5`，工作树必须 clean；不要重写、丢弃或拆散该提交。
5. 完整阅读 H3-A1 涉及的生产文件、experience corpus/provenance、loader/retriever、Botzone DeepSeek factory 接线及相关测试，再修改。

## 当前判定

`d20dba3 feat: project sourced strategy guidance before DeepSeek` 未通过规划复审，暂未并入 `cao`。已有 194 项相关、39 项主规则和 724 项全量测试通过，说明旧回归未漂移，但不能替代以下已独立复现的反例：

1. `exp_card_memory_001` 的正文含“不能升级为炸弹”，被 `_OUT_OF_SCOPE_KEYWORDS` 中的“升级”按子串误判；在 30 个真实引擎固定初始局、2677 个后续公开状态中命中次数为 0。该条目虽被 loader 激活，运行时却始终被冲突扫描拒绝。
2. `StrategyRecommendation.strategy_domains` 会被计算，但没有传给 `RAGAdvisor`、没有参与匹配/排序，也没有进入最终 prompt。当前十域测试只检查 corpus metadata 的集合相等，不证明运行时语义投影。
3. 推荐实现在非 finishing 的跟牌场景和仅含四/五张炸弹的自由领牌场景均返回 `unavailable`；不能据此声称十域已由 recommendation/decision chain 覆盖。
4. `summarize_candidate_structures()` 可接受缺少 `declared_cards`、`wildcard_info`、`display_text` 的非 canonical 动作并生成 `ready` 推荐。
5. `_validated_strategy_recommendation()` 接受任意非空 reason/countercheck/domain 字符串且没有字符预算；构造 5000 字符字段会原样进入最终 prompt。未知 domain 同样被接受，而合法的 `strategy_domains` 又不会显示。
6. 新增测试净增只有 4 项，没有覆盖原任务预注册的四/五炸、协同变体、开局反例、follow/pass、溢出、RAG 派生异常等关系型 fixture。
7. `exp_bomb_wildcard_001` 以 B 级 `source_principle` 绑定到“局势变化时调整组牌”的宽泛段落，但炸弹保留的具体定性依据实际来自已批准的 C 级转载。不能把公开特征设计或 C 级内容提升成 B 级打法结论。

本续作只修复并完成 H3-A1，不运行真实模型或 live，不新增另一个策略方向。

## 必须完成

### 1. 让已激活知识真正可检索

- 修复 `exp_card_memory_001` 的误拒绝。可以采用不触发越界 token 的等义短量转述，或对冲突扫描做严格、可测试的最小改进；不得因此放松对多局升级、贡还、比赛制等当前范围外内容的拒绝。
- 新增从 loader → tagged retrieval → packed RAG context → final prompt 的端到端测试，证明记牌原则能在适用公开场景命中，并且“王、级牌、A、10、5、公开断张是关注对象但不是暗牌事实”的边界仍在。
- 对每个 active 条目测试至少一个可达适用场景，或明确合并/删除永远被同层条目遮蔽的冗余条目。不能再以“loader 能加载”代替“runtime 能命中”。

### 2. 建立真实的十域模型前投影

- 从公开 observation、canonical actions、统一 phase 和现有 strategy intent 派生有界、稳定的 `strategy_domains`、有序目标与反例检查；不得把十个域无条件全部塞进每个局面。
- `strategy_domains` 必须真正驱动 RAG 的候选匹配或排序，并以固定顺序、固定枚举进入最终模型前输入。知识条目的 `strategy_domain` 要参与这个语义过程；作者、URL、tier、locator、status 和 opaque ID 仍不得参与。
- 推荐 action ID 可以只在公开关系足够清楚时给出；没有可靠 shortlist 时允许只提供目标、候选比较和反例，不要为了“ready”发明本地 selector。
- 至少让下列运行时路径可区分并投影相关域：开局/自由领牌，结构/拆分，控制资源，跟牌争权，队友协同，危险对手，炸弹/通配，残局，不确定性/试探；总体冲突优先级必须在所有路径保持一致。
- 修正来源映射：B 级 `source_principle` 只能表达 `docs/STRATEGY_SOURCE_AUDIT.md` 与原 H3-A1 Prompt 已列明的具名正文原则。炸弹通常保留等仅由 C 级材料支持的内容必须保持 `soft_hypothesis`；公开结构字段本身可作为项目事实，但不能伪装成 B 级打法来源。

### 3. 完成 canonical 与预算 fail-closed

- `summarize_candidate_structures()` 必须对它消费的 observation、玩家关系和 action 字段执行与 canonical 公共契约一致的保守验证，至少覆盖 action ID、pattern、declared/carrier、pass 形状、wildcard_count/info、display、手牌多重集及 free/follow/table 一致性。任一证据不完整或矛盾时整段派生不可用，原合法候选仍继续进入模型。
- recommendation/guidance 的最终验证必须拒绝未知 status/source/domain/code、重复或不在最终 prompt 候选内的 ID、派生字段不一致、任意自由文本和任何超过固定条数/字符预算的 payload。优先传递枚举 code 并在可信 formatter 中生成固定文案，不接受可注入的调用方文本。
- 候选结构展示必须采用确定性的有界代表选择，不能简单取原顺序前 12 项而静默丢掉关键比较。必须稳定覆盖推荐 ID、finisher、最小自然 single/pair、控制资源、wildcard、四/五炸或其他 fragmentation 代表；不存在某类时不虚构。
- 继续保持最终候选不超过 80、原始 action ID、稳定展示顺序与签名去重。所有派生器异常都 fail closed，不能阻止 DeepSeek 在原最终候选上选择。

### 4. 补齐关系型测试

使用多组等价变体，禁止 seed、现场 action ID 或 Q/4/10 特判。至少覆盖：

1. 结构安全低自然单张与较高普通单张同时可见；推荐可聚焦低成本候选，但 fake model 返回任一合法最终 ID 都原样保留且 source=`model`。
2. 同点数四张/五张炸弹同时可见；两 ID、长度、清空点数组、残余孤张/分组均准确进入有界比较，模型可任选，不得本地强制五炸。
3. natural pair 与 single 同时可见；两者最终候选保留，结构差异准确。加入队友接近走完变体，协同目标进入模型前输入但不直接选牌。
4. 既有严格强牌开局 fast path 稳定；去掉回手、令小单参与组合、加入公开紧急条件时退出 fast path，转入模型前建议。
5. 中性对子/三张、低成本试探和强组顺子风险只作模型前 principle/soft hypothesis，不成为 local shortcut。
6. 非 finishing 的 follow/control、队友控桌、危险对手和短残局路径分别得到正确 domain/objective/countercheck；三个专用 intent 保持生效，三个 legacy source 仍只读兼容。
7. 十域至少各有一个 loader→retrieval→prompt 可达 fixture；改变 registry 的作者、标题、publication、URL、locator 后，query、排序、RAG context 和最终 prompt 逐字节不变。
8. C 级 soft 条目可命中且有可撤回措辞；candidate/registry-only、缺字段、scope 冲突、未知枚举和畸形 metadata 均不激活；统计数字、贡还与书目内容从不进入 prompt。
9. 大候选、wildcard overflow、follow/pass、only-pass、一次出完、malformed observation/action/guidance、RAG 空结果和各派生器异常保持预算与降级契约。

## 长期不变量

- 不修改 `engine/`、Botzone 协议/session/audit/trace schema、`.env`、日志、规划 docs 或仓库外文件。
- 不运行浏览器、connector、Botzone、真实 DeepSeek 或 seed `47004` evidence。
- 不新增成功模型后的 selector、guard、override、decision source 或 RuleBased 复制。
- 既有 only-pass、一次出完和严格开局 local shortcut 可保留；其他策略只在模型前。
- DeepSeek 成功返回最终候选内合法 ID 后原样返回，source 为 `model`。
- 三个 legacy source 只读兼容，生产 DeepSeek/adapter 不得主动产生。
- 不引入神秘总分、牌点奖励、无来源阈值或外部依赖。

## 验证与提交

1. 先运行新增的端到端十域、来源、canonical、预算和关系型反例测试。
2. 运行 H3-A0/H3-A0a/H3-A1 的 opening、pruning、action structure、RAG、router/prompt、DeepSeek fake-client、legacy source、Botzone observability/trace/benchmark 回归。
3. 运行主规则 39 项：

   `python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q`

4. 运行 `python -m unittest discover -q`。
5. 运行 `git diff --check`；扫描生产路径确认无 seed/点数特判、post-model 覆盖/source、治理字段泄漏、越界内容激活。
6. 额外运行一个真实引擎多状态离线探针，证明各 active 策略条目或其合并后的等价知识在适用场景可达；报告样本数量与零异常，不持久化牌局详情。

只显式暂存并提交本续作的业务代码、RAG 和 tests。报告每个复审反例如何修复、十域运行时映射、来源边界、fixture 数量、定向/主规则/全量结果、diff/扫描、commit、最终 Git status 与任何保留外部修改。不要声称尚未经过真实模型或 live 的策略收益。
