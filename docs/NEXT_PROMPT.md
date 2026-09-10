# 给执行 Codex 的下一任务 Prompt

修复队友“小王控桌、本家持有大王”DeepSeek守卫测试中的canonical legal-action缺口。当前测试helper把单张9列为可压单张小王的合法动作，但引擎真值明确判定9不能压小王；这使上一轮真实模型检查的输入前提无效。本任务只修复测试证据，不修改生产策略。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务没有适用的Botzone live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，以及`engine/rules.py`、`agents/conditional_pressure_pass_policy.py`、`agents/deepseek_ai.py`和相关测试。
3. 检查Git状态必须clean，确认HEAD包含`1df757a`。先用当前引擎稳定复现：大王可压单张小王，普通单张9不可压单张小王。

## 【目标】

- 使`teammate_control_block`目标测试fixture只包含与该公开局面一致、由引擎规则真值支持的canonical legal actions；目标局面应至少保留原始pass和大王压制候选。
- 修正或拆分当前依赖伪合法单张9的“普通低价值动作不拦截”测试。若保留该行为测试，必须使用另一个规则上真正合法、且不满足“小王→大王”守卫语义的公开局面；不得继续把不可能的动作伪装成legal action。
- 增加最小回归，明确锁定目标fixture中每个非pass动作都能压过table action，且9不能压小王。

## 【约束】

- 只修改相关测试文件；除非发现独立、可复现的生产缺陷并先停止报告，否则不得修改`agents/`、`engine/`、`integrations/`、RAG或配置。
- 不改变`teammate_control_block`、strategy router/intent、prompt文案、RAG、DeepSeek fallback、observability或动作优先级。
- 不通过放宽引擎规则让9能够压小王；engine仍是合法性唯一真值。
- 不访问网络、DeepSeek、Botzone、Edge或`.env`；不触碰`D:\VsCodeProject\BotzoneWorkspace`。
- 不运行容量评测或live。

## 【验证与完成标准】

至少运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_deepseek_step_e tests.test_conditional_pressure_pass tests.test_strategy_intent_prompt_wiring -q
.\.venv\Scripts\python.exe -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

完成标准：目标fixture不再含任何不能压table action的伪合法非pass；相关守卫与非触发测试仍表达真实可达语义；生产文件零修改；全部验证通过。

提交时只暂存本任务测试修改并创建一个清晰的Git commit，不得提交无关变化。最终报告：根因、测试语义如何修正、修改文件、验证命令/结果、commit hash、最终Git状态，以及当前范围内是否仍有风险。不得运行上一轮真实模型检查；canonical模型复放由规划Codex复审后另行安排。
