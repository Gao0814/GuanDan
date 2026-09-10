# 给 Coding Codex 的下一任务 Prompt

修复 Botzone DeepSeek 提示中缺失“当前领牌者与本家的队伍关系”的上下文，使模型能够基于完整公开信息自主判断是否保留特殊牌。本任务不新增模型输出后的策略强制覆盖。

## 【开始前】

1. 阅读并遵守 `AGENTS.md`，检查适用项目 Skills；本任务不执行 live 或 workspace cleanup。
2. 阅读 `docs/CLEAN_HANDOFF.md`，检查 Git 状态，并复核相关 prompt、strategy-intent、RAG 与 Botzone Agent factory 代码和测试。
3. 只修改并提交本任务的业务代码和测试，不纳入其他来源的工作区变化。

## 【已验证的问题模型】

seed `47003` 的第9条ACK decision trace证明：模型在队友领牌、pass合法且可压动作全为特殊牌时选择了特殊牌。平台终局为`platform_error`，不能用于胜负判断，但该决策的公开observation、canonical legal actions、selected action、binding、ACK和audit provenance均有效。

当前代码的关键事实：

- `DeepSeekClient._build_structured_prompt()` 显示桌面牌型和各玩家队伍关系，却不显示桌面动作的领牌者是谁；传入的`history`没有被渲染为领牌关系。
- 当前RAG scene tags没有table-leader relation；该真实决策被归为endgame，并命中一般残局材料，而不是队友控桌材料。
- 同一公开fixture经过现有`route_strategy_intent()`会得到`support_teammate / teammate_controls_table`，`build_strategy_intent_prompt_payload()`返回`ready`；加入后prompt会明确出现“队友当前控桌”。
- Botzone `build_agent_factory("deepseek")` 当前显式关闭`strategy_router_shadow_enabled`和`strategy_intent_prompt_enabled`，所以这段已验证上下文未进入真实模型请求。

不得读取真实workspace或把真实手牌、牌面、标识符复制进测试；使用脱敏合成fixture复现这些结构事实。

## 【任务目标】

让Botzone DeepSeek在每次适用决策中收到经过现有严格公开校验的strategy-intent prompt，尤其能明确知道“队友当前控桌”；模型仍从原始合法动作中自主选择，合法的模型结果不得因为与RuleBased不同而被改写。

## 【约束与验证】

- 优先复用现有`strategy_router`和`strategy_intent_prompt`契约，不复制第二份领牌者识别逻辑。
- 先复现并解释为何该路径在Botzone factory关闭，再做最小接线；不要借本任务修改RAG corpus、engine、audit schema、decision trace schema或历史evaluation基线。
- router/prompt遇到畸形或不完整公开payload时保持现有fail-closed/omitted语义，不得影响模型合法动作校验与既有fallback。
- 不新增`teammate_pressure_pass_id()`后置调用，不新增自动pass，不改变现有危险对手、小王→大王及短自由出牌守卫。
- 测试至少证明：目标fixture向client传入ready的`support_teammate / teammate_controls_table` payload；对手领牌和自由出牌不会被错标；畸形证据会省略；fake client返回原始合法pass或特殊牌时均保持其选择；Botzone factory默认DeepSeek路径实际启用该提示，而RuleBased/conditional模式不受影响。
- 显式禁用dotenv，运行相关prompt/router/DeepSeek/Botzone定向测试、主规则回归、全量测试和`git diff --check`。
- 不运行Botzone、connector、网络、真实DeepSeek或容量评测。真实模型是否因此改正必须留给后续单决策、少量请求的独立复放验证，不能由mock测试宣称。

完成后检查diff并创建仅含本任务业务代码和测试的commit。最终报告根因、接线位置、模型自主权边界、验证命令与结果、commit、Git状态，以及后续真实单决策复放需要验证什么。
