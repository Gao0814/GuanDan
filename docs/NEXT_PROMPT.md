# 给 Coding Codex 的下一任务 Prompt

你负责本次只读策略诊断与结果报告。本任务审计固定workspace中已保留的seed `47002` connector-observed牌谱，寻找当前RuleBased/冻结基线仍存在的下一个可公开复现的高置信度策略缺陷。不要修改代码或仓库文件，不运行新对局、容量评测、网络或模型。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`、`docs/LIVE_GAME_REVIEW.md`、`docs/INVARIANTS.md` 与相关Agent代码。

保持事实、诊断与规划分离。牌谱中的一次动作只能作为线索；只有能从公开状态、原始合法动作和当前代码独立复现的机制，才能列为高置信度缺陷。不得从单局推断胜率，不得为了得到“下一项优化”而强行定性。

当前固定级牌2、四人、无需进贡、单局是既定验收范围，不是风险或未完成项。

## 【当前项目状态】

最新算法检查点为 `295b9b5`：

- 默认RuleBased已具备对手非紧急保炸弹与队友控桌保炸弹；
- DeepSeek成功动作已有危险对手pass阻断、自由出牌1–4张短序列分组守卫、队友小王后保留大王三项窄守卫；
- table action公开契约保持 `action_id=None`，原始legal actions保持严格整数ID；
- 三项成功动作source计为模型成功，不计fallback，audit版本不变；
- 规划Codex独立复跑相关65项、主规则39项和全量689项通过。

`record.txt` 中已识别的高置信度问题已经处理：开局残余结构、队友炸弹互耗、危险对手pass、小手牌分组拆解及队友小王后用大王压制。不要把这些已修复问题重新包装成新任务。

固定workspace `D:\VsCodeProject\BotzoneWorkspace` 仍保留seed `47002` 的只读evidence。已知低敏事实：该局17/17/17闭环、qualified finish、16次决策均为 `conditional_rule_based`、条件化pass未激活、history可读但terminal tail可能不完整，并出现2次未阻止完成的 `http_error`。本任务只分析策略，不诊断transport。

## 【本次任务目标】

只读核对seed `47002` 的completion audit、history、state tombstone和streams归属，然后分析本家16次决策，判断是否存在一个满足以下条件的下一策略缺陷：

1. 公开history与本家手牌足以重建该决策当时的桌面约束和本家原始合法动作；
2. 当前对应Agent机制可从代码明确解释实际选择；
3. 至少能构造一个不含真实match/token/完整手牌的最小合成fixture，稳定复现同一机制；
4. 缺陷不是已在 `150006a`、`5daf326`、`fb3d791`、`dc9638c`、`295b9b5` 修复的场景；
5. 建议规则能描述清楚适用边界，不需要“所有情况一律如此”的宽泛假设。

如果牌谱不足以恢复某一步完整legal actions，必须明确标为线索，不能定为缺陷。如果没有新的高置信度候选，应报告“现有evidence不足以支持下一项算法修改”，而不是修改代码或请求新建大量对局。

## 【需要检查的范围】

优先只读检查：

- `D:\VsCodeProject\BotzoneWorkspace\history.txt`
- `D:\VsCodeProject\BotzoneWorkspace\audit\completion-audit.json`
- `D:\VsCodeProject\BotzoneWorkspace\state\` 中唯一finished tombstone
- `D:\VsCodeProject\BotzoneWorkspace\streams\stdout.txt`
- `D:\VsCodeProject\BotzoneWorkspace\streams\stderr.txt`
- `agents/rule_based_ai.py`
- `agents/conditional_pressure_pass_ai.py`
- `agents/conditional_pressure_pass_policy.py`
- `agents/opening_strategy.py`
- `agents/short_endgame_planner.py`
- `engine/rules.py`、`engine/patterns.py` 和公开action序列化，仅用于重建合法动作真值

允许在系统临时目录运行一次性只读分析代码；不得把脚本、报告、解析结果或牌面写入仓库或workspace。优先复用现有解析/engine API，不要用脆弱的文本猜测代替可验证重建。

## 【本次任务约束】

- 不修改任何仓库文件，包括代码、测试和Markdown。
- 不写入、重命名、清理或更新时间戳到固定workspace；开始前后记录五份evidence的bytes、SHA-256和mtime，必须完全一致。
- 不输出完整本家手牌、match ID、run token、连接URL或其他敏感正文；报告只给动作类别、轮/步编号、剩余张数和必要的脱敏牌型。
- terminal tail不完整的部分不得声称为裁判完整历史。
- `conditional_rule_based` 表示当时显式conditional mode的冻结基线路径；分析时必须区分“该局当时实际策略”和“当前默认RuleBased已经新增的规则”。
- 不运行Botzone、Edge、connector、preflight、DeepSeek、网络或新本地容量。
- 不读取`.env`，不创建Git commit。
- 不清理seed `47002` evidence；清理必须在规划Codex记录本次结论后的独立任务进行。

## 【诊断方法】

1. 先验证workspace inventory、evidence归属和文件不变性。
2. 从牌谱逐项列出16次本家决策的低敏分类：自由/跟随队友/跟随对手、pass/普通/炸弹类、动作前后手数。
3. 对可疑动作，只在能恢复当时本家手牌、table action和legal actions时运行当前冻结基线与当前默认RuleBased，比较两者选择与现有守卫是否已覆盖。
4. 对最高优先候选构造最小内存fixture，证明当前代码稳定选择该动作；不要把fixture写入仓库测试。
5. 给出根因位置、建议修改边界、必须保持的不变量和未来测试清单；本任务不实施修改。

## 【完成标准】

- workspace evidence前后bytes/hash/mtime不变，仓库Git状态前后只包含任务开始时已有内容；
- 16次决策有低敏分类，无法重建的步骤明确标注证据不足；
- 最多提出一个高置信度下一缺陷，并有当前代码与最小fixture双重证据；或者明确判定现有evidence不足；
- 不重复已完成问题，不把单局结果上升为胜率结论；
- 未修改文件、未运行live/网络/模型/容量、未创建Git commit。

## 【执行后的报告要求】

最终报告必须包含：

1. evidence完整性与前后不变性；
2. 16次决策的低敏分类汇总；
3. 能否恢复各可疑点的完整legal actions；
4. 唯一最高优先缺陷候选，或“证据不足”的明确结论；
5. 当前代码根因与最小fixture结果；
6. 为什么它不是已修复问题的重复；
7. 建议下一实现任务的目标、边界和测试清单；
8. 实际运行的只读命令/检查；
9. 是否运行live、网络、模型或容量（预期均为否）；
10. 当前项目范围内的剩余风险；固定级牌2、无贡、单局不得列为风险。
