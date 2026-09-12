# 给执行 Codex 的下一任务 Prompt

对提交`24fb362`新增的队友小王→大王专用strategy-intent执行一次真实DeepSeek原始动作复放。必须直接取得任何确定性后置守卫之前的模型建议；本任务只做一次受控模型调用，不修改代码，不运行Botzone。

项目所有者发送本Prompt即授权：通过项目现有配置向当前配置的DeepSeek模型发送一份合成的公开observation、两个canonical legal actions、当前RAG和新版strategy-intent prompt，外部模型请求总上限为1，client重试固定为0。不得扩大授权范围。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务不使用Botzone live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`、`agents/conditional_pressure_pass_policy.py`、`agents/strategy_router.py`、`agents/strategy_intent_prompt.py`、`agents/deepseek_ai.py`、`agents/deepseek_client.py`及相关canonical fixture测试。
3. 检查Git状态必须clean，确认HEAD包含`24fb362`。若不满足，停止且不调用模型。

## 【调用前硬门槛】

- 使用`8db3154`修正后的canonical fixture，并由当前引擎再次确认：原始合法候选精确为pass与单张大王两个，大王可以压队友领出的单张小王。
- `teammate_big_joker_opportunity()`必须返回该fixture中的原始pass与大王候选身份。
- 当前strategy intent必须为`ready / support_teammate / teammate_big_joker_preservation`，提示必须含新版高价值资源保留语义；若仍是泛化`teammate_controls_table`则停止。
- RAG保持当前生产结果，预计低敏scene/action-context为`endgame / endgame`；不得修改或替换RAG以追求结果。
- 使用当前生产模型、temperature和其余请求参数；client重试必须显式为0。

任一门槛不满足时，不得发送模型请求，判为inconclusive。

## 【执行要求】

- 直接调用客户端取得模型原始action ID，并验证它是两个原始canonical legal action ID之一。
- 必须在`teammate_control_block`、`danger_opponent_block`、`short_endgame_plan`或任何RuleBased替代之前捕获结果。
- 不允许以现有后置守卫最终返回pass冒充模型选择pass。
- 外部模型请求最多1次；请求失败、响应非法或前置不满足时不得重试。

## 【隐私与禁止事项】

- 只报告原始动作类别`pass`或`target_special`，不得输出action ID、牌面、完整observation/legal actions、prompt、模型响应/reasoning、API key、URL、Header、Cookie或配置正文。
- 不读取或输出`.env`正文；若当前进程无法取得必要配置，直接判inconclusive。
- 不修改代码、tests、docs、配置或`D:\VsCodeProject\BotzoneWorkspace`；不创建报告文件或Git commit。
- 不运行Botzone、Edge、connector、preflight、live、容量评测或额外模型调用。

## 【唯一判定】

- 原始模型选择`pass`：`teammate_big_joker_prompt_raw_model_improved`。这支持下一步把`teammate_control_block`规划为shadow/退役候选，但本任务不修改守卫。
- 原始模型选择`target_special`：`teammate_big_joker_prompt_raw_model_still_not_ready`。下一步应独立检查当前`endgame / endgame` RAG是否稀释或冲突，不得扩大后置覆盖。
- 任一前置、请求或合法性验证失败：`teammate_big_joker_prompt_raw_model_inconclusive`。

最终报告：唯一判定、canonical候选数、共享机会判定、intent状态/reason、RAG低敏scene/action-context、模型调用状态、原始动作类别与合法性、实际外部请求数、重试数、Git HEAD/status；同时确认仓库与workspace未修改。不得输出敏感正文。
