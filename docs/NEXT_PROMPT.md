# Coding Codex 执行 Prompt

这是一个新的 Coding Codex 任务。不要依赖其他对话的隐含上下文，请从当前仓库重新建立事实。

你的职责是实现和测试业务代码；项目规划文档由规划 Codex 维护。开始前依次：

1. 阅读并遵守根目录及适用范围内的 `AGENTS.md`。
2. 检查 `.agents/skills/`；本任务不是 live 或 workspace 清理，不得执行这两个 Skill 的现场动作。
3. 阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/RAG_KB.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`。
4. 检查 Git status、HEAD 和最近提交；起点必须能解释，不能把外部修改混入提交。
5. 只读核对现有经验 corpus、loader/retriever、`OpeningFormulaStrategy`、DeepSeek free-lead 剪枝、structured prompt 与相关测试。不得联网、不得读取 `.env`，也不得清理或改写 `D:\VsCodeProject\BotzoneWorkspace` 的 seed `47004` evidence。

## 已复审根因

以下是规划 Codex 的结论，必须由你从当前代码再次确认：

- `rag/experience_corpus/basic_human_experience.md` 的策略条目没有作者、出版物、链接、规则版本、定位、适用范围或证据等级；它们目前是项目自拟启发式，不是已经验证的“人类经验”。
- `agents/opening_strategy.py` 的点数阈值及固定加减分没有来源或校准。seed `47004` 的强控制开局因此由 local shortcut 选择 Q：若目标是清理低价值孤张，结构安全的小牌更合理；若目标是低成本试探，也不应无理由先消耗更高普通单张。
- free-lead transition 剪枝在存在 single 时完全不保留 pair；原始合法对 3 因而对模型不可见。这是候选召回缺陷，不应等待某条打法口诀证明。
- 四/五张同点数炸弹都对模型可见，但 prompt 只给一般炸弹时机，没有把可计算的剩余手数与残余孤张事实送给模型。

## 目标：H3-A0 策略来源与开局公式重建

### 1. 知识平面与治理平面分离

为经验 corpus 建立最小、严格、可测试的 provenance 与激活状态契约，但不得把作者、标题、出版社、URL、来源等级或审核状态塞进会参与检索和 prompt 的知识 metadata。当前 `RAGAdvisor._keyword_score()` 会扫描全部 `metadata.values()`，`_tag_score_document()` 会把 metadata 纳入冲突检查，`_pack()` 会把 metadata 发给模型；直接扩充 front matter 会真实污染检索和 prompt。

实现必须明确分成：

- **知识平面**：经验正文和运行时真正需要的语义路由标签，例如 scene、phase、hand strength、action context、topic、priority、keywords。内容保持纯策略知识。
- **治理平面**：独立、不会进入 RAG 文本的 provenance registry，通过现有稳定条目 `id` 映射来源等级、claim 类型、作者/机构、公开定位、URL/书目、locator、适用范围和 evidence status。

具体文件格式可以根据现有标准库与 loader 风格设计，但必须满足：

- 只有 registry 判定为 `active` 的经验条目才可检索；`candidate` 与 `registry_only` 只登记，不进入模型。
- 项目内部的合法动作边界可在 registry 标为 `project_boundary`，不能冒充外部专家经验。
- 缺映射、缺字段、未知枚举、矛盾范围或不受支持来源应使对应经验 fail closed；不得阻断无 RAG 的合法决策 fallback。
- 作者、标题、出版社、URL、locator、来源等级与审核状态不得参与正文/metadata token 评分、冲突词扫描或 prompt packing。
- 修改 registry 的作者、标题或 URL，但不改变条目激活状态时，检索顺序与最终模型 prompt 必须逐字节不变。
- opaque 条目 ID 可用于内部关联和审计，但不得被当作策略特征；不得复制大段受版权保护正文。

按 `docs/STRATEGY_SOURCE_AUDIT.md` 处理现有条目：只有已核对公开正文实际支持的有限原则可改写为短量转述并激活；正规出版物只有目录/商品介绍时只能登记，不能推导具体打法；旧转载“宝典”只能是 candidate。删除或停用无来源的“弱牌只出较高单张”等确定性偏好。

### 2. 公式化开局边界

把 `OpeningFormulaStrategy` 从通用神秘打分器收敛为少数有依据、边界清楚的开局定式：

- 继续只读取公开 observation 与原始 canonical legal actions，只返回原始 ID。
- 强牌/高控制且具有回手资源时，若存在不拆对子/三张/炸弹/顺子等结构的自然小单，可把它作为强牌小单首攻定式；不得针对 Q、4、10、花色或 seed 写死。
- 王、级牌、炸弹、逢人配和成组结构仍应受保护。
- 来源不一致、payload malformed、无法判断定式或多个目标冲突时返回 `None`，让现有 RAG + DeepSeek 路径选择；不要用更多固定分数假装确定。
- 保持 only-pass、一次出完、phase、fallback、原始 action ID 和 decision source 契约。

不要把整本“宝典”硬编码成一个选择器，也不要把 opening formula 放到成功模型之后。

### 3. 剪枝与公开结构输入

- free-lead transition 候选必须在 singles 存在时仍保留代表性自然 pair，至少保留最小自然对子；遵守候选预算、稳定顺序、去重、wildcard/pressure/finishing 保留和原始 ID 追溯。
- 用公开 hand 与 canonical carrier 计算最小、共享、fail-closed 的残余结构摘要。它可以告诉模型某动作是否清空点数组、留下孤张及估计剩余分组/手数，但不能直接选动作。
- 同点数四张/五张炸弹均合法时，最终 prompt 必须保留两个原始 ID并呈现上述可计算差异；fake client 返回任一合法 ID时都原样保留并记录 `model`。

## 禁止事项

- 不得修改 `engine/` 规则真值、Botzone 协议/session/audit schema、固定项目范围或现有 evidence。
- 不得新增或恢复成功模型后的 action override、selector、guard 或 legacy decision source。
- 不得把未经核对的网络口诀写成 `active`，不得声称某本书内容已经读取，除非仓库中存在合法提供且可定位的正文；不得把 provenance 治理字段混入知识文本、检索特征或模型 prompt。
- 不得运行 live、connector、浏览器、真实 DeepSeek 请求或 workspace 清理。
- 不得把 seed `47004` 的完整手牌、完整 observation/action 列表、binding、token 或其他私密 evidence 复制进仓库或报告；测试使用独立构造的最小 synthetic fixtures。

## 必须新增的回归

至少覆盖：

- registry 完整且 active 的条目可检索；缺映射/字段、未知等级/状态、candidate、registry-only 和矛盾范围均不进入模型，输入不变且异常降级。
- author/title/URL/locator/tier/status 不出现在检索语料或模型 prompt；仅改这些审计值且不改 active 状态时，排名、snippet 和 prompt 逐字节不变。
- 强控制、存在回手资源且有结构安全小单的合成开局命中新定式；较高普通单张、王/级牌、部分拆对/三张/四张以上、wildcard 候选不因新定式被误选。
- 模糊或来源未覆盖的 opening fixture 返回 `None` 并实际进入现有 RAG + fake DeepSeek；模型合法 ID/source 原样保留。
- free-lead singles+pairs 的剪枝和最终 prompt 均保留代表性自然 pair，预算和原始 ID 不漂移。
- 四/五张同点数炸弹 prompt 显示清空点数组与残余孤张的差异，fake model 可自由返回任一 ID。
- malformed hand/card/carrier/source metadata fail closed；三个 legacy source 仍只读兼容，生产路径不产生它们。

## 验证

1. 运行新增及直接相关的 RAG、opening、pruning、prompt、DeepSeek 测试。
2. 运行主规则回归：

   `python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q`

3. 运行全量：

   `python -m unittest discover -q`

4. 运行 `git diff --check`，扫描生产路径确认没有旧 source 主动分支、新 post-model override、现场点数/seed 硬编码或未经来源激活的经验。

## 提交与报告

只提交本任务的业务代码、RAG corpus 和 tests；不要修改规划 docs。提交前后检查 status/diff，只显式暂存自有文件。

报告必须包含：

- 对无来源经验、开局打分、pair 剪枝和炸弹结构输入的独立根因结论；
- 实际激活/降级/仅登记的来源条目及理由；
- 修改文件、设计边界与每组测试通过数量；
- commit hash、最终 Git status、保留的外部修改/evidence；
- 当前范围内尚未解决的真实风险。固定级牌 `2`、四人、无贡、单局是既定范围，不列为风险。
