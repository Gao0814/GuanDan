# 给 Coding Codex 的下一任务 Prompt

你负责本次代码实现、测试与结果报告。本任务为自由出牌的小手牌残局增加一个严格、确定性的短序列规划守卫，避免模型选择可证明会增加本家出完所需手数的拆组动作。不运行 Botzone，不建立或运行新的容量评测。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`、`docs/SPEC.md`、`docs/INVARIANTS.md`、`docs/LIVE_GAME_REVIEW.md` 与相关代码和测试。

保持engine/AI边界：Agent只能读取公开 `observation` 与原始 `legal_actions`，并返回其中已有的合法 `action_id`；不得访问engine私有状态、克隆游戏真值、读取其他玩家暗牌或自行构造动作。

当前算法优化和Botzone profile固定级牌 `2`、四人、无需进贡的单局。这是项目既定验收范围，不是风险或未完成项；不得扩展为跨级牌、贡还或多局升级任务。

Coding Codex负责修改和验证，不创建Git commit。完成后保留工作区并报告，由项目规划Codex独立复核和提交。

## 【当前项目状态】

最新算法检查点为 `fb3d791`：

- 默认RuleBased已具备对手非紧急保炸弹和队友控桌保炸弹两项规则；
- DeepSeek成功返回合法pass时，危险对手1/2张阻断守卫会确定性改选原始非pass；
- `danger_opponent_block`计为成功模型尝试，不计fallback；
- `FrozenRuleBasedAIAgent`、DeepSeek失败fallback、显式conditional mode和历史evaluation语义保持稳定；
- 显式禁用dotenv的全量674项测试通过。

`record.txt` / `docs/LIVE_GAME_REVIEW.md` 第20–22轮暴露了下一项结构缺口：玩家2只剩 `6,7,J,J` 时按单步连续选择单J，最后留下6、7并失去控制。复盘没有断言“首出单J必错”，但明确确认当前决策不比较完整小手牌的2–3手残余结构。

本任务不对这一局硬编码动作。要解决的是可独立证明的窄问题：自由出牌、手牌很少时，如果模型所选首手比另一合法首手需要更多的最少剩余出牌组数，则模型选择缺少短序列一致性。

## 【本次任务目标】

先确认当前DeepSeek成功动作路径会接受上述“严格更差的残余分组”动作，然后实现以下规则：

> 当本家自由出牌、公开本家手牌不超过4张、原始legal actions足以按实体牌多重集精确覆盖手牌时，计算每个合法非pass首手之后的最少残余合法分组数。仅当模型所选动作的“当前1手 + 最少残余分组数”严格大于最佳合法首手时，改选一个最佳原始action ID；相等时保留模型选择。

计算必须基于当前公开手牌与当前自由出牌的原始canonical legal actions。两副牌中相同token可能重复，必须按多重集而非普通set处理。只允许使用合法动作的 `carrier_cards` 做实体扣除；`declared_cards` 只用于语义/展示，不能代替实体牌。

如果公开字段、手牌守恒、动作覆盖或最小分组结果不完整/不唯一可信，应fail closed并保留原模型选择。不得猜测未来对手动作或把“最少分组”声称为完整博弈最优。

## 【需要检查的范围】

优先检查：

- `record.txt`
- `docs/LIVE_GAME_REVIEW.md`
- `agents/deepseek_ai.py`
- `agents/rule_based_ai.py`
- `agents/opening_strategy.py` 中已有残余结构思想，确认能否安全复用但不要强行耦合开局规则
- `agents/hand_evaluator.py`
- `integrations/botzone/play_adapter.py`
- `integrations/botzone/agent_observability.py`
- 对应DeepSeek、RuleBased、adapter与observability测试

先用注入假client的脱敏fixture证明当前成功模型路径会接受“单J”类严格更差动作，再决定最小实现位置。优先建立独立、纯公开数据的短序列helper，由DeepSeek成功动作返回点调用；不要把搜索逻辑塞入adapter或engine。

不要强制只修改上述文件。允许在 `agents/` 新增一个职责单一的小模块，并修改必要的低基数observability和测试；不得修改engine、session、transport、history文件格式、audit schema版本或真实workspace。

## 【本次任务约束】

- 只处理 `constraint == "free"` 或项目当前等价的严格自由出牌语义。
- 只处理本家公开 `hand_count <= 4` 且手牌实体多重集完整可验证的场景；其他场景保持现状。
- pass不得参与自由出牌规划；若payload异常出现pass，fail closed。
- 最少分组只能由当前原始自由出牌legal actions的carrier多重集精确覆盖计算；不能调用engine私有接口生成未来动作。
- 只有模型动作严格劣于最佳分组数时才覆盖；并列不得覆盖模型。
- 最佳动作不唯一时使用已有确定性合法选择方式打破平局，不发明新的大规模评分体系。
- 新动作必须是原始legal actions中的action ID。
- 若新增低基数source，建议使用清楚表达语义的固定值并继续计为一次成功模型尝试；不计rule fallback，不改变audit版本或保存逐步牌面。
- 不改变危险对手阻断优先级、两项RuleBased保牌、冻结旧selector、DeepSeek失败fallback或显式conditional mode。
- 不新增依赖，不建立evaluation模块，不运行200/400局报告或任何百局/千局容量。
- 不运行Botzone、Edge、connector、网络或真实模型；显式禁用dotenv运行测试，不读取 `.env`，不触碰 `D:\VsCodeProject\BotzoneWorkspace`。
- 不创建Git commit。

## 【重要不变量】

- 所有返回值始终来自当前原始legal actions。
- 牌实体守恒按多重集验证，不能因两副牌重复token误删或误计。
- helper异常或证据不足必须保留合法模型动作，不能转成失败fallback。
- `6,7,J,J` 只作为脱敏回归fixture，不得在业务代码中硬编码牌点或action ID。
- 最少自有分组是局部确定性指标，不得在代码、测试或报告中称为全局最优或胜率证明。
- 固定级牌2、无贡、单局以及不做跨级牌/贡还/升级赛属于完成范围，不得列为剩余风险。

## 【验证要求】

新增或调整确定性测试，至少覆盖：

1. 自由出牌、手牌 `6,7,J,J` 的脱敏fixture中，模型选择单J需要4个总分组，而对子J路线需要3个；最终选择原始对子action ID；
2. 模型已经选择最少分组动作时不覆盖；两个首手总分组数并列时保留模型；
3. 多个最佳动作时选择确定且属于原始legal actions；
4. 重复实体token按多重集正确处理；不完整手牌、carrier不守恒、重复/非法action ID、缺字段或无法覆盖时fail closed；
5. hand count大于4、跟牌场景、仅一个非pass动作等非目标场景保持模型选择；
6. 危险对手1/2张阻断及 `danger_opponent_block` source继续通过；
7. DeepSeek success/timeout/exception/invalid action、冻结fallback、两项RuleBased保牌、显式conditional mode继续通过；
8. 若新增source，Botzone decision/model/outcome/fallback守恒与audit版本保持不变。

先运行直接相关测试，再显式禁用dotenv运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_game_flow tests.test_rules tests.test_patterns tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

## 【完成标准】

- 已用最小公开fixture复现当前成功模型路径接受严格更差残余分组动作；
- 自由出牌且手牌不超过4张时，严格可证明的更少分组首手能够覆盖模型的较差选择；
- 并列、证据不足和非目标场景保持原模型动作；
- 实体多重集、原始action ID、observability守恒和现有策略均无回归；
- 定向、主回归、全量测试和补丁检查通过；
- 未运行live、网络、模型或新容量，未读取`.env`或触碰真实workspace，未创建Git commit。

## 【执行后的报告要求】

最终报告必须包含：

1. 当前单步路径如何接受严格更差动作；
2. 最少残余分组的精确定义、边界和fail-closed条件；
3. 覆盖模型动作的严格条件与确定性tie-break；
4. 修改文件列表；
5. observability/source是否变化及守恒方式；
6. 新增/调整的关键测试；
7. 实际执行的全部验证命令、测试数量和结果；
8. 是否运行新容量、live、网络或模型（预期均为否）；
9. 当前项目范围内的剩余风险或未解决问题；如无，应明确写“当前范围内无已知剩余风险”。既定范围不得列为风险。
