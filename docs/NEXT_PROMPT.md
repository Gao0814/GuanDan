# 给 Coding Codex 的下一任务 Prompt

退役 DeepSeek 成功模型路径中的 `short_endgame_plan` 主动动作改写，同时保留短残局最少分组的专用公开策略输入，并把旧 source 转为只读兼容。完成实现、测试和一个独立业务 commit。

## 【事实与目标】

- 起始 HEAD 必须包含 `c32259d`、`7499ccc`、`3ee6e0e` 和 `e30362f`；开始前确认工作树 clean，并阅读 `AGENTS.md`、适用项目 Skill、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 以及相关生产代码和测试。
- 固定 5 候选短残局 fixture 已两次执行守卫前真实模型检查：通用 prompt 曾选严格更差的单 J；`c32259d` 加入 `run_out / short_endgame_minimum_groups` 专用公开提示后，唯一零重试请求成功且原始动作进入最少分组集合 `{1,2,5}`，判定 `short_endgame_dedicated_prompt_raw_model_ready`。该单点证据只授权退役既有覆盖，不代表整局或胜率优势。
- 本任务不调用真实 DeepSeek，不运行 Botzone/connector，不触碰 `D:\VsCodeProject\BotzoneWorkspace`，不修改 engine、RAG 语料、Botzone 协议或 audit schema/version。

## 【实现范围】

1. 从 `agents/deepseek_ai.py` 的成功模型路径移除 `_plan_short_free_lead()` 调用、`short_endgame_plan` source 赋值以及无剩余用途的该函数和 import。合法模型 suggestion 经原始 `legal_actions` 校验后必须直接返回同一 action ID，source 为 `model`；不要改变非法 suggestion/异常 fallback、local shortcut、verbose 输出或合法性校验。
2. 保留 `agents/short_endgame_planner.py` 的 `minimum_group_free_lead_action_ids()` 及其 fail-closed 公开 payload/分组求解，继续供 strategy router 和专用 prompt 使用。先用 `rg` 确认消费者；若 `strictly_better_free_lead_action_ids()` 已无生产消费者，则删除该 selected-action 后置规划 API 及只服务它的测试，不做无关重构。
3. 完整保留 `short_endgame_minimum_groups` 布尔机会、`run_out / short_endgame_minimum_groups` router reason、专用 prompt 文案、DeepSeek 最终 prompt 白名单验证及 Botzone factory 接线。保持既有 router 优先级、RAG scene/phase/action_context 和其他策略 intent 行为。
4. 将 `short_endgame_plan` 从当前主动 source 转入与 `teammate_control_block`、`danger_opponent_block`相同的 `LEGACY_DECISION_SOURCES`。旧 v7/v8 audit、session/acknowledged decision trace 和 policy benchmark 必须仍可读取，并继续要求它与成功模型 outcome、model-attempt/decision 计数精确守恒；错误 outcome/count、conditional 和未知 source 仍 fail closed。
5. 删除 `integrations/botzone/play_adapter.py` 对 `short_endgame_plan` 的主动识别分支。若旧或自定义 agent 残留该 source，当前 adapter 在模型 outcome 为 `success` 时应像另外两个退役 source 一样归一为 `model`，不得继续产生新的 `short_endgame_plan` 聚合记录。
6. 不恢复或改变 `teammate_control_block`、`danger_opponent_block` 的任何生产路径；不改变对应专用 router/prompt，也不新增 shadow/替代后置 source。

## 【测试要求】

- 更新 fake-client 回归，使固定短残局模型返回 action 1、2、3、4、5 时都保持原始合法 ID，source 均为 `model`；尤其单 J 3/4 不再被替换。
- 锁定 `minimum_group_free_lead_action_ids()` 对固定 fixture 仍为 `(1,2,5)`，畸形、不完整、非自由出牌、超过 4 张或无严格差异时继续 fail closed；router、prompt、最终输入验证和 Botzone factory 的专用输入不削弱。
- 把 `short_endgame_plan` 纳入 legacy audit/session/decision-trace 正反例，与另外两个 retired source 一并验证：合法历史 evidence 可读，非 success outcome 或计数不守恒仍被拒绝；adapter 的残留 source 回归期望为 `model`。
- 加入生产路径扫描/回归，确保 `agents/deepseek_ai.py` 与 `integrations/botzone/play_adapter.py` 不再包含 `short_endgame_plan` 主动分支、`_plan_short_free_lead` 或 selected-action helper 调用；允许该字符串只存在于集中 legacy 常量、历史兼容测试和文档。
- 至少运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_short_endgame_planner tests.test_deepseek_step_e tests.test_strategy_router tests.test_strategy_router_benchmark tests.test_strategy_intent_prompt tests.test_strategy_intent_prompt_wiring tests.test_botzone_deepseek_agent_runtime tests.test_botzone_agent_observability tests.test_botzone_decision_trace tests.test_botzone_policy_benchmark -q
.\.venv\Scripts\python.exe -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

## 【提交与报告】

- 修改前后检查 Git status/diff，只提交本任务业务代码和 tests；不得混入 docs、日志、环境文件或外部修改。提交信息可用 `feat: retire short endgame action override`。
- 最终报告：精确 commit SHA、修改文件、各测试命令/数量/结果、生产 source 扫描结果、专用公开输入保留情况、legacy v7/v8/session/trace 兼容与 fail-closed 结果、最终 Git status，以及任何保留的外部修改。
