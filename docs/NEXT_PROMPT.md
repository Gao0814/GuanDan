# 给执行 Codex 的下一任务 Prompt

退役DeepSeek成功动作路径中的`teammate_control_block`主动覆盖：新版专用strategy-intent已在canonical真实模型复放中使模型原始选择pass，因此该场景应恢复为“模型从原始合法动作中自主选择”，不再由后置规则把合法大王强制改成pass。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务没有适用的Botzone live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，以及DeepSeek成功动作路径、strategy router/prompt、共享`teammate_big_joker_opportunity()`、Botzone observability/session/trace和相关测试。
3. 检查Git状态必须clean，确认HEAD包含`24fb362`。复现专用intent为`ready / support_teammate / teammate_big_joker_preservation`；把受约束真实模型判定`teammate_big_joker_prompt_raw_model_improved`视为本任务的执行依据，不重新调用模型。

## 【目标】

- 从`DeepSeekAIAgent`成功建议处理链移除小王→大王的强制pass改写。模型返回原始合法pass时继续返回pass；模型返回原始合法大王时也必须原样返回该大王ID，`last_decision_source`为普通`model`。
- 删除只服务于主动覆盖且已无生产调用者的私有函数/后置选择辅助；保留`teammate_big_joker_opportunity()`作为strategy router与专用prompt的公开机会真值。
- 保持`teammate_big_joker_preservation` reason、prompt文本和Botzone factory接线不变。
- 不新增shadow执行分支或新的audit/source类别。现有decision trace已足以在未来从公开observation与legal actions离线重建该机会。

## 【兼容性与不变量】

- DeepSeek仍只返回原始`legal_actions`中的合法整数ID；不得用RuleBased替换成功模型动作。
- `danger_opponent_block`与`short_endgame_plan`不属于本次范围，调用顺序和行为保持不变。
- 不修改RAG、engine、Botzone协议、strategy-intent字段/序列化、fallback或audit schema/version。
- 历史v8 audit、session或decision trace可能含`teammate_control_block`。若移除该类别会破坏现有持久证据解析，则把它保留为legacy read-compatible allowlist值，但新的生产DeepSeek路径不得再产生它。不得为了表面清理破坏历史兼容。
- 不新增依赖，不访问网络、真实模型、Botzone、Edge或`.env`，不触碰`D:\VsCodeProject\BotzoneWorkspace`。

## 【验证要求】

测试至少覆盖：

- canonical小王→大王fixture继续生成专用ready intent/prompt；
- fake client返回pass时最终仍为原始pass、source=`model`；
- fake client返回大王时最终保留原始大王、source=`model`，不能再变成pass或`teammate_control_block`；
- Botzone factory、adapter、model success计数及decision trace记录的selected action与最终模型动作一致；
- 历史`teammate_control_block`聚合/trace兼容性按上述边界保留，或在有明确迁移设计和测试时安全处理；
- 危险对手阻断、短残局规划、模型失败fallback及普通strategy-intent回归不漂移；
- 仓库中不存在仍可从新生产DeepSeek路径触发`teammate_control_block`的调用链。

至少运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_deepseek_step_e tests.test_conditional_pressure_pass tests.test_strategy_router tests.test_strategy_intent_prompt tests.test_strategy_intent_prompt_wiring tests.test_botzone_deepseek_agent_runtime tests.test_botzone_agent_observability tests.test_botzone_decision_trace -q
.\.venv\Scripts\python.exe -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

## 【完成标准与报告】

完成标准：专用prompt保持有效；生产DeepSeek不再改写合法大王为pass；canonical pass与大王选择均按模型原始ID返回并记为`model`；历史持久证据兼容、其他守卫和全部测试通过。

只暂存并提交本任务产生的代码和测试修改，不提交无关变化。最终报告：主动覆盖的原调用链、删除/保留的组件、历史source兼容处理、实际修改文件、验证命令与结果、commit hash、Git状态及剩余风险。不得运行真实模型或live。
