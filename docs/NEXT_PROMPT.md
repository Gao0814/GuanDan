# 给 Coding Codex 的下一任务 Prompt

你负责本次代码实现、测试与结果报告。本任务修复“危险对手出牌后只剩不超过2张，本家有合法压制却仍选择pass”的高置信度策略缺陷。先确认实际决策路径，再做一个公开信息驱动、确定性的最小阻断守卫；不运行 Botzone，不建立新评测容量。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`、`docs/SPEC.md`、`docs/INVARIANTS.md`、`docs/LIVE_GAME_REVIEW.md` 与相关代码和测试。

保持 engine/AI 边界：Agent只能读取公开 `observation` 与原始 `legal_actions`，并返回其中已有的合法 `action_id`；不得访问engine私有状态、其他玩家真实手牌或未来信息，不得自行构造动作。

当前算法优化和Botzone profile固定级牌 `2`、四人、无需进贡的单局。这是项目既定验收范围，不是风险或未完成项；不得扩展为跨级牌、贡还或多局升级任务。

Coding Codex负责修改和验证，不创建Git commit。完成后保留工作区并报告，由项目规划Codex独立复核和提交。

## 【当前项目状态】

最新算法检查点为 `5daf326`：

- 默认RuleBased已能在非紧急对手领牌场景保留炸弹，并能在队友控桌、只有炸弹类压制时保守pass；
- 两类判定共用严格的公开history/table/action schema校验；
- `FrozenRuleBasedAIAgent` 保持修改前静态行为；
- DeepSeek内部与Botzone adapter的失败fallback继续使用冻结旧基线；
- 显式 `conditional_pressure_pass` mode保持原有对手领牌语义；
- 全量671项测试通过。

`record.txt` / `docs/LIVE_GAME_REVIEW.md` 的第16轮记录了另一项明确问题：玩家4出单张8后只剩对9，玩家3有9和J可以合法压制，却选择pass，让玩家4随后以对9头游。复盘将其列为最接近终局结果的高置信度策略错误。

当前默认RuleBased在对手剩余不超过2张时本来不会触发保牌pass，冻结静态选择也会选非pass；因此真正需要先确认的是该错误在DeepSeek、本地shortcut、adapter或其他决策层的哪一层被允许发生。不要未经检查假定根因一定是模型。

## 【本次任务目标】

使用脱敏的最小公开fixture复现当前决策链允许危险对手场景选择pass的具体路径，然后实现以下不变量：

> 当公开history与table action严格证明当前最后一个非pass领牌者是对手，并且该对手出牌后仍在局但剩余手牌不超过2张时，只要本家存在至少一个合法非pass压制，最终决策不得选择pass。

所选动作必须来自原始 `legal_actions`。如果多个非pass动作可用，应复用现有确定性合法选择能力，不在本任务中发明新的整套动作评分器。

守卫应作用于真正可能返回pass的决策路径。默认RuleBased当前正确行为不得回归；DeepSeek正常非紧急决策、失败fallback和Botzone adapter边界不得被无关改写。

## 【需要检查的范围】

优先检查：

- `record.txt`
- `docs/LIVE_GAME_REVIEW.md`
- `agents/deepseek_ai.py`
- `agents/rule_based_ai.py`
- `agents/conditional_pressure_pass_policy.py`
- `agents/strategy_router.py`
- `integrations/botzone/play_adapter.py`
- `integrations/botzone/agent_observability.py`
- 相关DeepSeek、RuleBased、adapter与observability测试

先画清当前动作来源：本地shortcut、模型成功、Agent内部fallback、adapter fallback分别在哪里选择和验证action ID。用可注入的假模型/假client或现有测试接口证明哪条路径会接受pass，再决定最小实现位置。

严格leader/history/table校验已有实现时应复用或安全提取，不能再复制一套近似schema解析。不要强迫只修改上述文件，但修改范围应限于 `agents/`、必要的Botzone低基数observability接线和对应测试；不得修改engine、session、transport、history文件格式或真实workspace。

## 【本次任务约束】

- 不修改engine规则、合法动作生成、动作比较或公开payload契约。
- 不新增依赖。
- 不修改 `FrozenRuleBasedAIAgent` 的旧静态选择语义。
- 不把所有残局都强制出牌；只有严格证明危险对手当前控桌、剩余不超过2张且本家确有合法非pass时触发。
- 当前领牌者是队友、本家自己、已结束玩家，或history/table无法一致证明时不得触发。
- 只有pass可用时必须正常pass；自由出牌时不得套用跟牌阻断规则。
- 如果阻断作为新的本地确定性来源进入DeepSeek/Botzone observability，可以增加一个明确的低基数source，但不得记录牌、prompt、模型文本或改变audit schema版本；所有decision/model/fallback计数必须继续守恒。
- 不通过把pass从engine合法动作中删除来伪造规则真值；策略层只能选择或向现有决策器提供受控候选视图。
- 不运行Botzone、Edge、connector、网络或真实模型；不读取、写入或清理 `D:\VsCodeProject\BotzoneWorkspace`。
- 不建立新evaluation模块，不运行已有200/400局报告，不做任何百局/千局容量。
- 不创建Git commit。

## 【重要不变量】

- 最终返回值始终是当前原始 `legal_actions` 中的合法 `action_id`。
- 危险对手身份必须由严格公开history/table关系证明，不能仅凭座位或hand count猜测。
- 非危险场景的DeepSeek模型调用、成功动作、fallback与source语义保持不变。
- 既有对手保炸弹、队友控桌保炸弹规则继续通过。
- 显式 `conditional_pressure_pass` mode、冻结历史baseline和evaluation语义不得漂移。
- 固定级牌2、无贡是完成范围，不得在最终报告中列为剩余风险。

## 【验证要求】

新增或调整确定性测试，至少覆盖：

1. 脱敏复现第16轮语义：对手领单张后剩2张，本家有普通单张压制，注入的模型/当前问题路径选择pass时，最终返回原始非pass ID；
2. 对手剩1张和2张均触发，剩3张不触发；
3. 对手已结束、队友领牌、本家领牌、自由出牌、history/table不一致、只有pass、无pass及畸形公开payload均不误触发；
4. 多个非pass动作时结果确定且属于原始合法集合；
5. 默认RuleBased已有两类保牌规则继续通过；
6. DeepSeek成功、timeout、exception、invalid action与adapter fallback原有测试继续通过；
7. 若新增observability source，覆盖Agent直连和Botzone adapter下的decision/source/model计数守恒，且不改变audit版本。

先运行直接相关测试，再运行：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_game_flow tests.test_rules tests.test_patterns tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

## 【完成标准】

- 已用最小公开fixture确认原问题实际经过的决策路径；
- 危险对手控桌且剩余不超过2张时，只要存在合法非pass，最终不再pass；
- 非目标场景、既有保牌策略、DeepSeek fallback、显式conditional模式和Botzone守恒均无回归；
- 定向、主回归、全量测试和补丁检查通过；
- 未运行live、网络、模型或新容量，未触碰真实workspace，未创建Git commit。

## 【执行后的报告要求】

最终报告必须包含：

1. 实际根因和允许pass的具体决策路径；
2. 阻断守卫放置位置及选择非pass的方法；
3. 修改文件列表；
4. observability/source是否变化及守恒方式；
5. 新增/调整的关键测试；
6. 实际执行的全部验证命令、测试数量和结果；
7. 是否运行新容量、live、网络或模型（预期均为否）；
8. 当前项目范围内的剩余风险或未解决问题；如无，应明确写“当前范围内无已知剩余风险”。固定级牌2、无贡、单局及不做跨级牌/贡还/多局升级不得列为风险。
