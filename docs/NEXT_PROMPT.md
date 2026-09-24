# Coding Codex 执行 Prompt

任务：修正 `9d89595cdbe07ca8945d57cd393e05f0fab5cf54` 来源策略整合的复审缺口，并在通用实现通过后完成旧局三处观察的只读后验验收；不要另开一串 H3-A 微阶段。开始先核对 Git status、diff、HEAD/最近提交并保留外部修改；阅读适用 `AGENTS.md`、检查 `.agents/skills/`，阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md` 当前顶部复审结论、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，以及相关生产代码、来源 registry/corpus 和测试。只改本任务直接相关的 `agents/`、`rag/`、`tests/`，必要时改 `evaluation/` 离线辅助；不改 `engine/`、Botzone 协议、配置、规划 docs 或 `.env`。

## 必须纠正的通用问题

1. 独立复现并修复开局公式失活。规划复审在同一批 seed `0..199`、完整 108 张发牌/本家 27 张、级牌 2 的初始公开状态中测得：提交前本地公式直出 9/200，`9d89595` 后 0/200；200/200 状态都产生至少一个候选关系。当前 `OpeningFormulaStrategy.select_action()` 只要 `representative_candidate_contrasts()` 非空就退出，把普遍存在、未必与目标小单竞争的对子等关系等同于实际冲突。改为只由目标动作相关且公开可证明会影响该定式的冲突阻断；保留强牌、结构安全、唯一自然小单、独立回手资源、公开紧急性及 B 级支持等边界，不能为恢复命中率而无条件本地出牌。新增完整引擎多 seed 正向与反向回归：相关关系应退出，不相关关系下若严格定式成立，应保留非零可达的本地直出；不锁定某一现场 seed/点数，不凭单次数量宣称策略收益。公式不命中时仍进入现有 RAG + DeepSeek，不恢复模型后覆盖。
2. 对 `docs/STRATEGY_SOURCE_AUDIT.md` 第 6 节的 28 项“新增条件化软假设候选”给出实际运行时覆盖矩阵，不能直接重复规划分类数字。逐项映射到具体可观察触发、合法候选关系、反例、激活的经验条目及实际最终 Request；若只是已有语义，应说明合并；若依赖暗牌、规则冲突或无可用候选，应降级/排除并说明。当前提交仅新增 1 个 corpus 条目和 10 类关系；至少百条 #55 的小/大钢板保留关系与 #73 的三带二携带对子梯度没有关系级证据。对仍可由公开 canonical actions 判断且有实际比较价值的主张，在同一任务中补齐适当的关系/知识/prompt 投影及引擎多局面测试；不要为凑 28 个条目发明权重、造暗牌事实或硬编码固定动作。可核对 C 级材料仍只作可撤回软假设，作者/URL/等级/状态只在 provenance registry；规则真值来自引擎。
3. 为新增和修正的关系运行实际检索与禁网 `DeepSeekClient` Request 组装测试，确认关系两侧原始 ID 都在最终 `<=80` 候选中，推荐 ID/候选签名守恒，不适用时不投影，模型成功返回展示候选的原始 ID 且 source=`model`。检查不重新引入 `teammate_control_block`、`danger_opponent_block`、`short_endgame_plan` 主动生产覆盖；旧持久记录只读兼容保持。不要把 RuleBased 续局代理的历史标签当策略优劣门槛。

## 通用实现后再做旧局后验检查

先完成上述实现、相关测试、主规则和全量回归，再按 `docs/PROJECT_STATUS.md` 已登记的 seed `47004` 六份精确 evidence 路径、大小和 SHA-256 重新只读核对固定 workspace。规划复审在当前环境已确认六项均存在且匹配；执行报告此前的“tombstone 不存在”不可直接沿用。若本次有任何精确路径或 hash 不匹配，立即停止 evidence 读取，不搜索替代文件，报告具体失败阶段。若全部匹配，只在内存中读取 ACK trace 的原始公开 observation/canonical actions，禁网重放四/五炸残余、较高普通单张开局、自然对子/单张清理三个历史观察；只检查新版本地公式是否直出、关键候选是否可见、来源原则/具体比较/反例是否进入最终 Request。历史动作与新模型结果不同，不从重放推断新模型会如何选牌或胜率变化；若仍有输入缺口，报告责任层，不按现场点数追加补丁。

真实 DeepSeek 请求、重试、Botzone/live/connector/browser/preflight 均为 0；不清理 workspace、不读取旧 H3 ledger/系统 Temp/`.env`，不输出或持久化历史手牌、逐动作牌面、原始 ID、prompt、模型文本、凭据或 match/binding 标识。只提交本轮自有业务/知识/测试文件，按明确路径暂存；运行直接相关、主规则与 `python -m unittest discover -q`，执行 `git diff --check` 并检查完整 diff。交付实际 28 项覆盖矩阵的已落实/合并/降级及证据、开局公式正反例与多 seed 命中、三个旧观察的低敏结论、测试数、commit、最终 Git status 和保留外部修改，交规划 Codex 独立复审。
