# Coding Codex 执行 Prompt

这是一个新的 Coding Codex 任务。不要依赖其他对话的隐含上下文，请从当前仓库重新建立事实。

你的职责是实现和测试业务代码；项目规划文档由规划 Codex 维护。开始前依次：

1. 阅读并遵守根目录及适用范围内的 `AGENTS.md`。
2. 检查 `.agents/skills/`；本任务不是 live 或 workspace 清理，不得执行这两个 Skill 的现场动作。
3. 阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/RAG_KB.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`。
4. 检查 Git status、HEAD 和最近提交；起点必须包含 `5dbdd2ce866c753fee95b5302293522d1370d5e2` 且工作树 clean，不能把外部修改混入提交。
5. 只读核对 `agents/deepseek_client.py` 的 free-lead 剪枝、最终 prompt action limit、`agents/action_structure.py` 及相关测试。不得联网、不得读取 `.env`，也不得清理、读取或改写 `D:\VsCodeProject\BotzoneWorkspace` 的 seed `47004` evidence。

## 已复审结论

`5dbdd2c` 的 H3-A0 主体已通过独立复审：知识平面与 provenance 治理平面物理分离；治理字段不参与 tagged 检索、冲突扫描或模型 prompt；candidate/registry-only 不激活；开局公式不再针对现场点数使用旧通用打分；同点数四张/五张炸弹的公开残余结构提示存在；fake model 返回任一合法 ID 时保持原始 ID 和 `model` source；三个 legacy source 仍只有读取兼容。

但 H3-A0 尚不能封板。当前存在确定、可复现的两层剪枝契约冲突：

- `_select_transition_actions()` 已在 singles 存在时加入最小自然 pair；
- `_lead_pruned_actions()` 把大量 run 动作排在 transition 动作之前；
- `_limit_prompt_actions()` 在 critical 数量达到 `PROMPT_MAX_CANDIDATE_ACTIONS` 时直接返回全部 critical 动作；
- 因此最终 prompt 既可能超过声明的 80 项预算，又会重新丢掉所有自然 pair。

规划 Codex 使用当前真实引擎的多个独立初始局面复现：原始合法集合和第一层 pruned 集合均含自然 pair，但最终 prompt 集合不含任何自然 pair；已知 seed `47004` 也满足同一低敏结论。不要把该 seed、现场手牌或动作详情写入测试或源码。

## 目标：H3-A0a 最终候选预算与 pair 召回修复

只修复从原始 canonical legal actions 到最终模型候选集的选择契约，使 pair 召回在真正发送给模型的最后一层仍成立。

必须满足：

1. 最终发送给模型的候选动作数始终不超过 `PROMPT_MAX_CANDIDATE_ACTIONS`；prompt 中的数量说明必须与实际展示集合一致。
2. free lead 同时存在 single 与 natural pair 时，最终集合必须保留一个按既有稳定排序选出的最小自然 pair，而不只是第一层 pruned 集合保留。
3. 保持必要的代表性自然 single；不得通过删除全部 single 来换取 pair。
4. finishing、pressure、wildcard 与普通 transition 候选发生预算冲突时，必须建立一个集中、确定、可测试的优先级与代表性压缩规则。不得继续使用“critical 超过上限则全部放行”的无上限分支；也不得让同签名重复动作浪费预算。
5. 同点数四张/五张炸弹合成场景必须继续同时保留两个原始 ID，并继续展示清空点数组、残余孤张点数和估计剩余点数组差异。
6. stable order、去重、原始 action ID、公开 payload、only-pass、一次出完、follow/pass、phase 与 fallback 契约不得漂移。
7. fake model 返回最终候选中的任一合法 ID 时必须原样返回并记录 `model`；不得新增 post-model selector、guard、override 或 decision source。
8. 不修改 `engine/`、opening/RAG/provenance 语义、Botzone 协议/session/audit schema、三个 legacy source 兼容或固定项目范围。若集中最终选择所需，可最小修改 `agents/deepseek_client.py` 及直接相关测试；不要借机重构 H3-A0 其他已通过部分。

不要简单提高常量掩盖冲突。若现有“所有 wildcard/pressure/finishing 永远全部保留”与硬预算在真实动作空间中不可同时满足，应在代码和测试中明确采用有界的代表性保留规则，并说明每类动作的优先级及理由。RAG/DeepSeek 仍是候选内策略选择者，候选压缩只负责公开动作空间的有界高召回。

## 必须新增或强化的回归

- 构造独立于现场 evidence 的真实引擎或 synthetic free-lead 大候选 fixture，使第一层 pruned 数量和 critical 数量足以触发原缺陷；断言最终数量 `<= 80`，自然 single 与最小自然 pair 均存在。
- 断言相同输入重复运行得到逐项相同的 action ID 顺序，所有 ID 均来自原始 legal actions，且无重复签名。
- 覆盖 wildcard 数量超过普通预算的 overflow 场景，证明不会因全部 wildcard 无上限放行而突破上限或挤掉 pair。
- 覆盖 pressure 与 finishing 优先级；若同类过多，验证明确的有界代表规则，而不是依赖输入偶然顺序。
- 保持四/五张同点数炸弹均在最终 prompt，残余结构文案不变，fake model 返回任一 ID 均保持 `model`。
- 保持 small-list singles+pairs、follow、only-pass、一次出完、malformed fail-closed、opening formula、RAG provenance 隔离和 legacy read compatibility 回归。

## 禁止事项

- 不得运行 live、connector、浏览器、真实 DeepSeek 请求或 workspace 清理。
- 不得读取或复制 seed `47004` 的手牌、observation、action 列表、binding、token、prompt 或其他私密 evidence。
- 不得针对 seed、Q、4、10、某个 action ID 或某个测试列表写死。
- 不得修改规划 docs、`.env`、日志或仓库外文件。

## 验证

1. 先运行新增的大候选 overflow、pruning、prompt、action structure 和 DeepSeek fake-client 定向测试。
2. 运行 H3-A0 相关的 opening、RAG/provenance、strategy-intent、Botzone observability/trace/benchmark 回归。
3. 运行主规则回归：

   `python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q`

4. 运行全量：

   `python -m unittest discover -q`

5. 运行 `git diff --check`，并扫描生产路径确认没有现场硬编码、新 post-model override 或旧 source 主动分支。

## 提交与报告

只提交本任务的业务代码和 tests；不要修改规划 docs。提交前后检查 status/diff，只显式暂存自有文件。

报告必须包含：

- 原缺陷在第一层 pruned 与最终 prompt 两层的复现数据，以及修复后的最终硬上限和 pair 召回结果；
- overflow 时各动作类别的明确优先级/代表性规则；
- 修改文件、定向/主规则/全量测试数量、`git diff --check` 与生产扫描结果；
- commit hash、最终 Git status、保留的外部修改/evidence；
- 当前范围内尚未解决的真实风险。固定级牌 `2`、四人、无贡、单局是既定范围，不列为风险。
