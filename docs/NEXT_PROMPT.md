# 给 Coding Codex 的下一任务 Prompt

你负责本次代码实现、测试与结果报告。本任务修复默认 `RuleBasedAIAgent` 在队友已经控桌时仍可能用炸弹压队友、造成同队资源互耗的问题。直接完成一个保守、窄幅的策略改进；不运行 Botzone，不建立新的 evaluation harness，不做百局或千局容量。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`、`docs/SPEC.md`、`docs/INVARIANTS.md`、`docs/LIVE_GAME_REVIEW.md` 与相关代码和测试。

保持 engine/AI 边界：Agent 只能读取公开 `observation` 与原始 `legal_actions`，并返回其中已有的合法 `action_id`；不得访问 engine 私有状态，不得自行构造动作或把策略判断移入 engine。

当前算法优化和 Botzone profile 固定级牌 `2`、四人、无需进贡的单局。不得扩展为跨级牌泛化、多局升级、进贡、还贡或抗贡。

Coding Codex 负责修改和验证，不创建 Git commit。完成后保留工作区并报告，由项目规划 Codex 独立复核和提交。

## 【当前项目状态】

实现检查点 `150006a` 已完成第一项默认RuleBased改进：

- `FrozenRuleBasedAIAgent` 保存修改前的静态选择行为；
- 默认 `RuleBasedAIAgent` 已在对手领牌、只有炸弹类压制且无明确残局压力时条件化pass；
- 共享条件判定位于 `agents/conditional_pressure_pass_policy.py`；
- DeepSeek fallback和历史evaluation继续显式使用冻结旧基线；
- 显式 `conditional_pressure_pass` Botzone mode保持兼容；
- 规划Codex独立复跑全量668项通过。

既有 `record.txt` / `docs/LIVE_GAME_REVIEW.md` 提供了另一项明确策略样本：第2个已观测牌权段中，玩家3作为玩家1的队友已经以Q-K钢板控桌，玩家1又用4炸压队友，随后玩家3再用5炸压回。同队连续消耗两枚炸弹，只为在队内转移牌权。

当前默认RuleBased虽然已经会在特定对手压力场景保炸弹，但仍没有独立处理“队友领牌”这一合作场景；冻结旧静态selector会优先排除pass并选择非pass动作。

## 【本次任务目标】

当公开observation能够严格证明当前桌面最后一个非pass领牌者是本家队友，并且本家除pass外的所有合法压制都属于炸弹类资源时，默认 `RuleBasedAIAgent` 应在非紧急场景选择engine提供的原始pass `action_id`，避免仅为队内转移牌权消耗炸弹。

炸弹类沿用现有项目语义：`bomb`、`straight_flush`、`joker_bomb`。

至少保留以下不触发例外：

- 任一合法非pass动作可以让本家一手出完；
- 任一对手已经出完或剩余手牌不超过2张，存在明确残局压力；
- 当前领牌者不是队友，或公开history不能严格证明领牌关系；
- 存在普通非炸弹压制；
- 自由出牌、没有pass、只有pass或公开payload畸形。

除这一窄场景外，默认RuleBased必须保持当前 `150006a` 行为，包括已实现的对手压力条件化pass。

## 【需要检查的范围】

优先检查：

- `agents/rule_based_ai.py`
- `agents/conditional_pressure_pass_policy.py`
- `agents/conditional_pressure_pass_ai.py`
- `tests/test_conditional_pressure_pass.py`
- `record.txt`
- `docs/LIVE_GAME_REVIEW.md`
- Botzone RuleBased/DeepSeek runtime与observability相关测试

先确认当前共享判定、冻结基线、公开history schema和默认RuleBased调用顺序，再选择最小组织方式。新的队友保牌判定必须有唯一实现；可以复用或提取现有严格payload校验，但不要复制一整套近似校验逻辑。

不要强行只修改上述文件；可在 `agents/` 和对应测试内做合理的最小调整。不得修改engine、Botzone协议、session、history、audit schema/version或真实workspace。

## 【本次任务约束】

- 不修改 `FrozenRuleBasedAIAgent` 的旧静态行为。
- 不改变DeepSeek内部或Botzone adapter的冻结fallback语义。
- 不改变显式 `conditional_pressure_pass` mode的既有策略含义或source计数。
- 默认 `rule` 仍使用既有 `rule_primary` observability语义，不为本次规则修改audit schema。
- 不新增依赖。
- 不使用隐藏手牌、engine私有状态或未来信息。
- 不把“队友领牌就永远pass”作为粗暴规则；仅在严格、保守条件满足时触发。
- 不根据单局输赢调整规则，不新建benchmark/evaluation模块，不运行新容量。
- 不运行Botzone、Edge、connector、网络或模型；不读取、写入或清理 `D:\VsCodeProject\BotzoneWorkspace`。
- 不提交Git；由规划Codex复核后提交。

## 【重要不变量】

- 所有返回值必须是当前原始 `legal_actions` 中存在的 `action_id`。
- history与table action必须按现有公开schema严格一致，不能只凭team字段猜测当前领牌者。
- 自由出牌时不得伪造pass；没有pass时不得制造pass。
- 一手出完优先级不得被队友保牌规则阻断。
- 对手残局压力例外必须保留。
- 现有对手领牌条件化pass行为及其测试不得回归。
- 冻结旧基线与历史evaluation语义不得漂移。

## 【验证要求】

新增或调整确定性测试，至少覆盖：

1. 队友领牌，pass与单个/多个bomb、straight flush或joker bomb并存，满足安全条件时默认RuleBased选择原始pass ID；
2. 用脱敏、最小公开fixture复现 `LIVE_GAME_REVIEW` 的“队友钢板控桌、本家只有炸弹类压制”语义；
3. 可一手出完时选择当前合法非pass，不被保牌规则阻断；
4. 对手已经出完或剩余不超过2张时不触发队友保牌；
5. 存在普通压制、对手领牌、自由出牌、history/table不一致、没有pass、只有pass或字段畸形时保持当前行为；
6. 当前对手压力条件化pass测试继续通过；
7. 冻结基线、DeepSeek fallback、显式conditional mode和Botzone source守恒保持不变。

先运行直接相关测试，再运行：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_game_flow tests.test_rules tests.test_patterns tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

不要运行已有200/400局报告，也不要新跑任何百局/千局容量。

## 【完成标准】

- 默认RuleBased在严格队友控桌/仅炸弹类压制/非紧急场景选择原始pass；
- 所有例外与非触发场景保持当前行为；
- 新判定只有一个共享真值实现，不复制策略逻辑；
- 冻结基线、DeepSeek fallback、显式conditional mode、Botzone audit/source和engine契约均未改变；
- 定向、主回归、全量测试和补丁检查通过；
- 未运行Botzone、网络、模型或新容量，未触碰真实workspace，未创建Git commit。

## 【执行后的报告要求】

最终报告必须包含：

1. 原因与现有实战样本如何对应；
2. 队友领牌判定和紧急例外的实际实现；
3. 修改文件列表；
4. 为什么没有破坏既有对手压力pass、冻结基线和DeepSeek fallback；
5. 新增/调整的关键测试；
6. 实际执行的全部验证命令、测试数量和结果；
7. 是否运行新容量、live、网络或模型（预期均为否）；
8. 剩余风险或未解决问题。
