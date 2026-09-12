# 给执行 Codex 的下一任务 Prompt

为队友“小王控桌、本家只有pass或大王压制”的严格公开场景增加一个专用strategy-intent reason，使DeepSeek在决策前明确获得高价值资源保留依据。该信息只进入模型prompt，不选择、过滤或改写动作；本任务不调用真实模型。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务没有适用的Botzone live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，以及strategy router/prompt、`teammate_big_joker_pass_id()`、DeepSeek接线和相关测试。
3. 检查Git状态必须clean，确认HEAD包含`8db3154`。复现当前canonical fixture得到泛化`support_teammate / teammate_controls_table`，并确认守卫前模型检查的既有低敏判定为`teammate_control_canonical_prompt_raw_model_not_ready`。

## 【目标】

- 从现有小王→大王守卫条件中提取或复用一个不依赖模型已选动作的严格公开机会判定，供strategy router与现有后置守卫共享，避免两份条件逻辑漂移。
- 当且仅当公开证据严格证明以下条件时，router在既有优先级中产生一个新的固定reason code，intent仍为`support_teammate`：
  - 跟牌且history/table一致，领牌者是队友；
  - 队友以单张小王控桌；
  - 原始canonical legal actions包含pass和单张大王压制；
  - 使用大王不能立即出完；
  - 对手均未结束且余牌大于2。
- 专用prompt需明确表达：队友已用小王控桌、pass合法、此时用大王不能直接出完且没有紧急阻断对手的公开需要；应优先考虑让队友保持牌权并保留大王这一高价值控制资源。措辞必须保持“策略建议、由模型在合法候选中决定”，不得写成强制动作或合法性结论。
- 普通队友领牌继续使用`teammate_controls_table`；任一字段畸形、history/table不一致、无pass、无大王、可立即出完、对手余1/2张或已结束时不得产生专用reason。

## 【重要约束】

- DeepSeek仍是合法动作空间内的主要策略决策者。不得新增、扩大或提前任何后置动作覆盖，不得用RuleBased替换成功模型动作。
- 现有`teammate_control_block`本轮暂时保留且行为不变，等待新prompt完成后独立真实模型复放；不要在本任务把它转shadow或删除。
- 不修改RAG scene/action-context、语料或检索。本轮只改变strategy-intent这一单一变量。
- 不改变engine、Botzone协议、public observation/legal-actions契约、fallback、observability source或audit schema/version。
- 只使用公开observation与原始canonical legal actions；始终返回/保留原始action ID。
- 不访问网络、DeepSeek、Botzone、Edge或`.env`；不触碰`D:\VsCodeProject\BotzoneWorkspace`，不运行live或容量评测。

## 【验证要求】

测试至少覆盖：

- `8db3154`后的canonical小王→大王fixture产生新的ready reason、`support_teammate`和专用策略文本；
- 普通队友控桌仍走原reason；
- 对手领牌、自由出牌、history/table不一致、无pass、无大王、立即出完、危险对手、已结束对手及畸形action/player/team字段均不误触发；
- prompt formatter对新增上下文字段、reason与预算继续fail closed；序列化稳定、固定长度/包络测试同步更新；
- fake client无论返回pass还是大王，请求结果仍按既有模型success语义计数；大王分支只允许继续触发现有`teammate_control_block`，不得增加其他覆盖；Botzone factory确实把新ready payload传入client。

至少运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_strategy_router tests.test_strategy_intent_prompt tests.test_strategy_intent_prompt_wiring tests.test_deepseek_step_e tests.test_botzone_deepseek_agent_runtime tests.test_botzone_agent_observability -q
.\.venv\Scripts\python.exe -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

## 【完成标准与报告】

完成标准：canonical目标fixture稳定获得专用ready reason及策略建议；所有近似场景保持原行为或fail closed；生产动作选择、后置守卫、RAG、engine和Botzone契约无额外变化；全部测试通过。

只暂存并提交本任务产生的代码和测试修改，不提交无关变化。最终报告：根因、共享判定设计、prompt新增语义、实际修改文件、为何不改RAG/后置守卫、测试命令与结果、commit hash、Git状态及剩余风险。不得运行真实模型；后续canonical复放由规划Codex复审后单独安排。
