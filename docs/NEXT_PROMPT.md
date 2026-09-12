# 给执行 Codex 的下一任务 Prompt

修复`e30362f feat: retire teammate control action override`留下的离线读取兼容缺口。动作自主性修改本身已经通过复审：生产DeepSeek成功路径不再执行`teammate_control_block`改写，fake client选pass或大王都保留原始合法ID并记为`model`。不得恢复该覆盖。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务没有适用的Botzone live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，以及`integrations/botzone/agent_observability.py`、`integrations/botzone/session.py`、`evaluation/botzone_policy_benchmark.py`和对应测试。
3. 检查Git状态，确认HEAD包含`e30362f`。先独立复现：一份source为`teammate_control_block`、model outcome为`success`且计数守恒的legacy v7或v8 DeepSeek audit，当前会被policy benchmark以`invalid_pairs`拒绝。

## 【目标】

- 让正式policy benchmark能读取历史v7/v8 `teammate_control_block` audit，并把它按“一次成功模型尝试后的legacy策略改写”纳入模型计数守恒。
- 同步让同一离线消费器识别当前活跃的`danger_opponent_block`和`short_endgame_plan`，二者也应按成功模型尝试计数。不改它们的生产调用顺序或动作行为。
- 保持session/decision trace、`AgentObservabilitySnapshot`、runner audit与benchmark对同一source分类的读取语义一致。可以最小共享常量或显式同步allowlist，但不要做无关重构。
- 机械修正`teammate_big_joker_opportunity()`仍声称“供post-model guard使用”的过时docstring；它现在只是strategy router/专用prompt的公开机会真值。若相关测试名仍把已删除行为称为guard，可同步做无行为变化的更名。

## 【兼容性与不变量】

- 不恢复`teammate_big_joker_pass_id()`、`_preserve_teammate_big_joker()`或任何等价后置动作改写。
- 新生产DeepSeek/adapter路径不得产生`teammate_control_block`；该source只是legacy read-compatible值。fake client返回pass或大王时仍必须原样返回并记为`model`。
- 保持`teammate_big_joker_opportunity()`、`teammate_big_joker_preservation` reason/prompt和Botzone factory接线；不修改RAG、engine、fallback、Botzone协议、audit schema/version或报告脱敏边界。
- policy benchmark仍必须拒绝未知source、非守恒计数、source与model outcome不匹配、RuleBased混入DeepSeek source及conditional mode混入正式RuleBased/DeepSeek对比。
- 不新增依赖，不访问网络、真实模型、Botzone、Edge或`.env`，不触碰`D:\VsCodeProject\BotzoneWorkspace`。

## 【验证要求】

测试至少覆盖：

- legacy v7和v8 `teammate_control_block` DeepSeek audit在source/model outcome/count守恒时能被读取并正常聚合；
- 同类 audit 的模型计数缺失、多计或outcome不守恒时继续fail closed；
- `danger_opponent_block`与`short_endgame_plan`各至少一份有效DeepSeek audit能正常聚合；
- 未知source和其他现有policy benchmark反例继续拒绝；
- session/decision trace legacy source仍可读；fake pass/大王、专用prompt、危险对手阻断、短残局规划回归不漂移；
- 源码扫描确认新生产DeepSeek路径仍无`teammate_control_block`赋值或调用链。

至少运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_botzone_policy_benchmark tests.test_botzone_agent_observability tests.test_botzone_decision_trace tests.test_botzone_deepseek_agent_runtime tests.test_deepseek_step_e tests.test_strategy_router tests.test_strategy_intent_prompt -q
.\.venv\Scripts\python.exe -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

## 【完成标准与报告】

完成标准：legacy `teammate_control_block` v7/v8 audit可读，当前两个活跃成功模型改写source可读，所有计数反例仍fail closed，新生产路径仍不产生`teammate_control_block`，且全量测试通过。

只暂存并提交本任务产生的最小代码/测试修改，不提交无关变化。最终报告需列出根因、legacy/活跃source读取设计、反例、修改文件、验证命令与结果、commit hash、Git状态及剩余风险。
