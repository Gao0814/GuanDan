# 给 Coding Codex 的下一任务 Prompt

修复 DeepSeek 成功模型动作绕过既有“队友控桌时保留特殊牌资源”策略的路径。本任务只做离线代码与测试修改，不运行 Botzone、connector、网络、真实模型或容量评测，不读取或清理 `D:\VsCodeProject\BotzoneWorkspace`。

## 【开始前】

1. 阅读并遵守 `AGENTS.md`，检查现有项目 Skills；本任务没有需要执行的 live/cleanup Skill。
2. 阅读 `docs/CLEAN_HANDOFF.md`、相关 Agent/observability/adapter 代码和测试。
3. 检查 Git 状态；只修改并提交本任务的业务代码和测试，不纳入其他来源的改动。

## 【已验证的问题】

seed `47003` 的平台终局为 `platform_error`，所以不能作为正常胜负结果；但其 decision trace 的 ACK 序列、selected-action 映射、binding、audit 计数和 provenance 均已独立验证。第 9 个已确认决策提供了完整公开复现：

- 当前领牌者是队友；pass 合法；全部非 pass 都是特殊牌；本家不能立即出完；没有对手已结束或只剩 1/2 张。
- 现有共享 `teammate_pressure_pass_id()` 返回原始 pass ID，当前默认 `RuleBasedAIAgent` 也选择该 pass。
- 模型选择了原始合法特殊牌 ID；当前 `DeepSeekAIAgent` 原样返回它，`last_decision_source == "model"`。
- `FrozenRuleBasedAIAgent` 仍选择该特殊牌。这说明绕过点在模型成功动作的后置守卫，而不是 engine、合法动作或 fallback。

不要读取真实 trace 或把其牌面、手牌、标识符复制进测试；使用脱敏合成 fixture 重现上述公开结构。

## 【任务目标】

当 DeepSeek 成功返回合法非 pass，并且既有共享队友资源保留策略严格证明应 pass 时，返回原始合法 pass ID。其他局面保持现有行为。

## 【范围与约束】

- 优先检查 `agents/deepseek_ai.py`、`agents/conditional_pressure_pass_policy.py`、`integrations/botzone/agent_observability.py`、`integrations/botzone/play_adapter.py` 及对应测试。
- 复用现有严格公开 payload 校验和 `teammate_pressure_pass_id()`；不要复制策略条件，不访问 engine 内部状态，不构造新动作。
- 仅拦截实际会改变模型非 pass 的目标场景；模型本已选 pass 时仍保持普通 `model` source。
- 复用现有低基数 `teammate_control_block` source，仍计为一次成功模型尝试且不计 fallback；不要修改 audit schema/version。
- 保持现有守卫语义和优先级：危险对手阻断不能退化；小王→大王守卫继续有效；短自由出牌规划只处理自由出牌。
- 不扩大为“队友领牌一律 pass”，不顺带实现未经真实 evidence 证明的其他策略，不修改 `engine/`、默认固定 profile 或历史 evaluation 基线。
- 始终返回原始 `legal_actions` 中的合法 `action_id`，证据缺失或字段畸形时 fail closed，保留模型选择。

## 【验证与完成标准】

至少覆盖：真实问题的脱敏合成复现；模型已选 pass；普通非 pass 可选；可立即出完；危险对手；对手残局压力；history/table 不一致；畸形字段；无 pass；only-pass shortcut；小王→大王；自由出牌短序列；observability/model-success/fallback 守恒。

使用项目虚拟环境并显式禁用 dotenv，先运行相关定向测试，再运行主规则回归、全量测试和 `git diff --check`。完成后检查 diff，并创建只包含本任务业务代码和测试的 Git commit。

最终报告：根因、修改和文件、守卫顺序与 source 记账、验证命令及结果、commit hash、最终 Git 状态，以及当前范围内是否仍有已知风险。
