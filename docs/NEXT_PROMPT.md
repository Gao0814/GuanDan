# 给执行 Codex 的下一任务 Prompt

对seed `47003` decision trace中的第9个已确认决策执行一次极小规模、无Botzone的真实DeepSeek strategy-intent off/on复放。项目所有者发送本Prompt即授权：使用项目现有DeepSeek配置，把该决策中已在原live发送过的公开observation、原始legal actions和必要RAG上下文再次发送给同一配置的模型；总计最多两次模型决策调用。不得扩大授权范围。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务不使用live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`及相关DeepSeek prompt/strategy-intent代码，检查Git状态必须clean，确认HEAD包含`454a422`。
3. 对`D:\VsCodeProject\BotzoneWorkspace\decision-trace.json`只读核对既有bytes/SHA-256及schema；只在内存中读取第9条decision，不修改任何workspace artifact。

## 【目标与固定对照】

在相同observation、相同原始legal actions、相同RAG、相同模型、相同temperature和其他配置下，各执行一次：

- off：`strategy_router_shadow_enabled=False`、`strategy_intent_prompt_enabled=False`；
- on：`strategy_router_shadow_enabled=True`、`strategy_intent_prompt_enabled=True`。

两侧都必须让真实DeepSeek自主返回action ID；不得用RuleBased替换结果，不得新增或临时启用自动pass。使用独立的新Agent实例，避免跨侧状态污染。将client重试数固定为0，使外部模型请求上限严格为两次；任一侧请求失败则如实判为inconclusive，不追加第三次请求。

## 【证据与隐私边界】

- 调用前确认on侧生成`ready / support_teammate / teammate_controls_table`，off侧没有该payload；否则停止且不调用模型。
- 两侧返回都必须是各自原始legal actions中的严格整数ID；按实际模型结果比较，不预设pass一定胜出。
- 不输出或持久化本家手牌、完整observation/legal actions、action ID、牌面、prompt、模型response/reasoning、API key、URL、Header、Cookie、run token、match/binding/state文件名。
- 只允许报告每侧动作类别：`pass`、`ordinary`或`special`，以及合法性、模型调用结果和strategy-intent状态。
- 不修改代码、tests、docs、配置或workspace；不运行Botzone、connector、preflight、live、容量评测或全量测试；不创建报告文件或Git commit。

## 【判定】

- off=`special`、on=`pass`：`strategy_intent_target_decision_improved`。
- off=`pass`、on=`pass`：`strategy_intent_target_decision_consistent_pass`，不能单次归因改进。
- off=`special`、on=`special`：`strategy_intent_target_decision_not_improved`，下一步应优化模型提示/RAG，不加后置覆盖。
- off=`pass`、on=`special`：`strategy_intent_target_decision_regressed`。
- 任一侧非success、非法动作或前置不满足：`strategy_intent_target_decision_replay_inconclusive`。

最终报告：唯一判定、两侧低敏动作类别、两次模型调用状态、on侧intent状态、动作合法性、artifact前后bytes/SHA-256、Git HEAD/status、实际外部请求数。不得输出敏感正文。
