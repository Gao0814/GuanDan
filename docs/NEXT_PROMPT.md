# 给执行 Codex 的下一任务 Prompt

对现有固定短残局fixture执行一次新版`short_endgame_minimum_groups`专用prompt下的守卫前真实DeepSeek原始动作复放。本任务只取得是否可退役`short_endgame_plan`的证据，不修改或提交代码、tests或docs。

项目所有者已在`AGENTS.md`长期授权单个明确任务中严格少于10次的预注册真实DeepSeek请求；本任务请求上限精确为1，无需另行申请。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务没有适用的Botzone live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`agents/short_endgame_planner.py`、`agents/deepseek_ai.py`、`agents/strategy_router.py`、`agents/strategy_intent_prompt.py`、`agents/deepseek_client.py`、`integrations/botzone/agent_runtime.py`和`tests/test_deepseek_step_e.py`中短残局fixture/回归。
3. 检查Git工作树必须clean，HEAD必须包含`c32259d`与`7499ccc`。不触碰`D:\VsCodeProject\BotzoneWorkspace`。

## 【固定输入与离线前提】

- 只使用`tests/test_deepseek_step_e.py::_short_endgame_observation()`与`_short_endgame_legal_actions()`：本家自由出牌，手牌精确为`6S,7S,JH,JD`，canonical候选精确为单6、单7、两张实体J各自的单J及J对，共5个原始action ID。不得替换、增删或改写fixture。
- 请求前确认`minimum_group_free_lead_action_ids()`精确返回`(1,2,5)`；`strictly_better_free_lead_action_ids()`对selected 1/2/5返回`None`，对3/4返回`(1,2,5)`。任一前提不符就零请求停止。
- 用Botzone DeepSeek factory的现行接线做零网络fake检查，确认strategy intent为`available / run_out / short_endgame_minimum_groups`且布尔机会为true，prompt为`ready / run_out`并包含“最少剩余分组”和“避免无谓拆散已有组合”；RAG低基数scene/phase/action_context仍为`endgame / near_open_endgame / endgame`。
- fake模型返回单J时，现有守卫仍改为原始最优ID并记录`short_endgame_plan`；fake返回1/2/5时仍保持原始ID与`model` source。任一接线或行为不符就零请求停止。

## 【请求边界】

- 外部模型请求上限精确为1，`max_retries=0`，温度及其他生产prompt参数保持现状。不运行Botzone、connector、Edge、整局或第二个模型请求。
- 必须在`_plan_short_free_lead()`之前取得模型原始action ID。可在单一进程内临时mock该函数使其返回原始选择与`False`；不得改写工作树或用后置最终动作伪装模型原始选择。
- 不输出、写入或提交API key、base URL、完整prompt、模型response、reasoning或异常正文。不新建artifact或日志。

## 【判定】

- 唯一请求成功，原始action ID属于`{1,2,5}`：判定`short_endgame_dedicated_prompt_raw_model_ready`。这只支持下一任务规划退役`short_endgame_plan`，本任务不删除它。
- 唯一请求成功，原始action ID属于`{3,4}`：判定`short_endgame_dedicated_prompt_raw_model_not_ready`。保持现有守卫；下一步只分析专用prompt消费与候选动作摘要，不新增或扩大后置覆盖，也不自动重试。
- timeout、exception、invalid suggestion、前提失败、原始ID不属于5个候选或请求计数不是1：判定`short_endgame_dedicated_prompt_raw_model_inconclusive`，不授权代码修改或自动重试。

## 【完成报告】

最终只报告固定低敏字段：全部前提是否通过、候选数5、最少分组ID集合是否为`{1,2,5}`、intent status/intent/reason/机会布尔值、prompt status/intent/关键语义是否存在、RAG scene/phase/action_context、请求数、重试数、模型结果类别、原始动作类别`minimum_group|strictly_worse_single_jack`、原始action ID是否属于固定候选集，以及代码/文件修改数、Git HEAD和请求前后是否clean。

当前任务不创建commit；不把一次模型结果外推为整局或胜率结论。
