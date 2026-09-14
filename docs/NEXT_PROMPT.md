# 给 Coding Codex 的下一任务 Prompt

退役DeepSeek成功模型路径中的`danger_opponent_block`主动动作改写。已有prompt-first证据满足删除门槛：canonical fixture中对手以单张8领牌且剩余1张，本家原始合法候选为pass/9/J；现有factory生成`ready / block_opponent / urgent_opponent_controls_table`，一次零重试真实DeepSeek请求在守卫前自行返回候选集内的`ordinary`动作，判定`danger_opponent_prompt_raw_model_ready`。本任务只实现退役与兼容，不再调用真实模型。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务没有适用的Botzone live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，以及`agents/deepseek_ai.py`、`agents/conditional_pressure_pass_policy.py`、`integrations/botzone/play_adapter.py`、`integrations/botzone/agent_observability.py`、`evaluation/botzone_policy_benchmark.py`和对应测试。
3. 检查Git工作树，确认HEAD包含规划检查点和`3ee6e0e`。若存在外部修改，保持不动且不得混入提交。

## 【目标】

- 从`DeepSeekAIAgent`成功模型分支移除`_block_dangerous_opponent_pass()`调用，使模型返回任一合法pass或普通动作时都保持原始action ID与`model` source。
- 若源码搜索确认没有其他生产消费者，删除`_block_dangerous_opponent_pass()`和`dangerous_opponent_pass_id()`及其仅验证已退役动作覆盖的测试/import；不要保留不可达策略改写代码。
- 模型合法结果之后仍按现有条件调用`_plan_short_free_lead()`；`short_endgame_plan`的适用范围、selector、source和行为不得改变。
- 保留strategy router与prompt中的`block_opponent / urgent_opponent_controls_table`，使模型继续收到危险对手公开策略依据。不得削弱或改写其intent、reason、RAG场景或Botzone factory接线。
- 将`danger_opponent_block`明确转为legacy read-compatible source：旧audit/session/decision trace继续可读取和满足成功模型outcome守恒，但新DeepSeek/adapter运行路径不得产生或主动接受该source。优先沿用`teammate_control_block`现有退役模式，不复制第二套分类逻辑。

## 【边界与不变量】

- 不把RuleBased选择新增为成功模型动作的后置覆盖，不新增shadow source或替代守卫。
- 不修改engine、RAG语料、公开observation/canonical legal action契约、fallback、Botzone协议、audit schema/version或conditional模式。
- 不借机退役或调整`short_endgame_plan`；它是下一项独立prompt-first技术债。
- 不访问网络、真实DeepSeek、Botzone、Edge、`.env`或`D:\VsCodeProject\BotzoneWorkspace`，不新增依赖。

## 【测试要求】

至少覆盖：

- fake client在对手剩1张和2张的危险fixture中返回pass时，均保持原始pass action ID，source=`model`，模型调用精确1次；返回9或J时也保持原始合法ID与`model` source。
- 现有`urgent_opponent_controls_table` router/prompt和Botzone factory回归继续通过。
- `short_endgame_plan`仍在原有严格自由出牌条件下触发，范围外保持模型动作；退役危险守卫后不改变其行为。
- legacy v7/v8 `danger_opponent_block` audit/session/decision trace仍可读取，source/model outcome/count不守恒继续fail closed；当前adapter不再把新决策归类为该source。
- 源码扫描确认新生产DeepSeek/adapter路径无`danger_opponent_block`赋值或主动分支，也无`_block_dangerous_opponent_pass()`或`dangerous_opponent_pass_id()`调用；legacy常量、兼容注释和测试fixture中的字符串允许保留。

至少运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_deepseek_step_e tests.test_conditional_pressure_pass tests.test_strategy_router tests.test_strategy_intent_prompt tests.test_strategy_intent_prompt_wiring tests.test_botzone_deepseek_agent_runtime tests.test_botzone_agent_observability tests.test_botzone_decision_trace tests.test_botzone_policy_benchmark -q
.\.venv\Scripts\python.exe -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

## 【完成标准与提交】

完成标准：危险对手主动动作覆盖从生产DeepSeek路径完全退役；fake pass/9/J均保持原始合法ID与`model` source；专用router/prompt和`short_endgame_plan`无行为漂移；旧`danger_opponent_block`证据仍可读取但新生产路径不能产生；全量测试通过。

只暂存并提交本任务产生的最小业务代码和测试修改，不提交规划docs、AGENTS或外部变化。最终报告列出删除路径、legacy兼容设计、保留的不变量、修改文件、验证命令与结果、commit hash、最终Git状态及当前范围内剩余风险。
