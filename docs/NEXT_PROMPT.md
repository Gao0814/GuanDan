# 给执行 Codex 的下一任务 Prompt

对现有`danger_opponent_block`做一次prompt-first的守卫前真实DeepSeek原始动作检查。本任务只取得下一项策略修改的证据，不修改或提交代码、tests或docs。

## 【授权门槛】

本任务需要一次真实DeepSeek API外部请求。只有项目所有者在启动本任务的当前对话中明确授权后才可执行；没有当前授权就停在请求前，不读取`.env`。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务没有适用的Botzone live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`agents/deepseek_ai.py`、`agents/strategy_router.py`、`agents/strategy_intent_prompt.py`、`integrations/botzone/agent_runtime.py`和`tests/test_deepseek_step_e.py`中危险对手fixture/回归。
3. 检查Git工作树必须clean，HEAD必须包含`3ee6e0e`。不触碰`D:\VsCodeProject\BotzoneWorkspace`。

## 【固定输入与请求边界】

- 只使用`tests/test_deepseek_step_e.py::_danger_observation(opponent_count=1)`与`_danger_legal_actions()`：对手2以单张8领牌且剩1张，本家手持9和J，canonical候选精确为原始pass、单张9和单张J。不替换、增删或改写fixture。
- 在请求前用当前engine证明9/J都可压单张8，并用Botzone DeepSeek factory的现行接线证明strategy intent/prompt为`ready / block_opponent / urgent_opponent_controls_table`。任一前提不符就零请求停止。
- 外部模型请求上限精确为1，`max_retries=0`，温度和其他生产prompt参数保持现状。不运行Botzone、connector、Edge、整局或第二个模型请求。
- 必须在`_block_dangerous_opponent_pass()`之前取得模型原始action ID。可在单一进程内用临时mock使该守卫返回原始选择；不得改写工作树或用后置最终动作伪装模型原始选择。该fixture是跟牌场景，`short_endgame_plan`不应触发。

## 【隐私与证据】

- 不输出、写入或提交API key、base URL、完整prompt、模型response、reasoning或异常正文。不新建artifact或日志。
- 最终只报告固定低敏字段：前提是否通过、候选数3、intent status/intent/reason、RAG scene低基数标签（如有）、请求数、重试数、模型结果类别、原始动作类别`pass|ordinary|special`、原始action ID是否属于候选，以及Git前后是否clean。

## 【判定】

- 唯一请求成功且原始选择为单张9或单张J：判定`danger_opponent_prompt_raw_model_ready`。这只支持下一任务规划退役`danger_opponent_block`，本任务不删除它。
- 唯一请求成功但原始选择pass：判定`danger_opponent_prompt_raw_model_not_ready`。下一步只能规划对`urgent_opponent_controls_table`的专用prompt补强，不扩大后置覆盖。
- timeout、exception、invalid suggestion、前提失败或请求计数不是1：判定`danger_opponent_prompt_raw_model_inconclusive`，不授权任何代码修改或自动重试。

## 【完成报告】

报告上述唯一判定、低敏证据、实际网络/模型请求与重试数、代码/文件修改数、Git HEAD和最终状态。当前任务不创建commit。
