# 给 Coding Codex 的下一任务 Prompt

你负责本次代码实现、测试与结果报告。本任务处理 DeepSeek 成功动作绕过队友控桌资源保留的问题：先复现模型用高价值控制牌压住队友的路径，再实现严格、保守、可证明的成功动作守卫。不运行 Botzone，不建立或运行容量评测。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`、`docs/SPEC.md`、`docs/INVARIANTS.md`、`docs/LIVE_GAME_REVIEW.md` 与相关代码和测试。

保持 engine/AI 边界：Agent 只能读取公开 `observation` 与原始 `legal_actions`，并返回其中已有的合法 `action_id`；不得访问 engine 私有状态、读取其他玩家暗牌、自行构造动作或复制规则引擎的合法性判断。

当前算法优化和 Botzone profile 固定级牌 `2`、四人、无需进贡的单局。这是项目既定验收范围，不是风险或未完成项；不得扩展为跨级牌、贡还或多局升级任务。

Coding Codex 负责修改和验证，不创建 Git commit。完成后保留工作区并报告，由项目规划 Codex 独立复核和提交。

## 【当前项目状态】

最新算法检查点为 `dc9638c`：

- 默认 RuleBased 已具备对手非紧急保炸弹和队友控桌保炸弹两项规则；
- DeepSeek 成功返回危险 pass 时，`danger_opponent_block` 会在领牌对手只剩 1/2 张时改选原始非 pass；
- DeepSeek 自由出牌且本家只剩 1–4 张时，`short_endgame_plan` 会阻止严格增加本家最少出牌分组数的模型动作；
- 上述两个 source 都计为成功模型尝试，不计 fallback；冻结旧 RuleBased、DeepSeek 失败 fallback、显式 conditional mode 和 audit 版本保持稳定；
- 规划 Codex 已在显式禁用 dotenv 的环境中独立复跑全量 684 项通过。

`record.txt` / `docs/LIVE_GAME_REVIEW.md` 第 6 轮还有一条未处理的公开线索：玩家 2（玩家 4 的队友）以小王领牌并已控桌，玩家 4 随后用大王压队友。现有默认 RuleBased 的队友保牌只覆盖“全部非 pass 都是炸弹类”的规则路径；DeepSeek 成功返回的合法非 pass 仍会直接采用，因此高价值资源压队友的模型动作仍可能绕过保留策略。

这条单局记录只能作为 fixture 线索，不能证明所有压队友动作都错误。本任务不得实现“队友领牌一律 pass”的宽泛规则。

## 【本次任务目标】

先用注入假 client 的脱敏测试确认：当公开 history/table 严格证明队友以小王领牌、pass 合法、本家有大王压制且模型成功返回大王 action ID 时，当前 DeepSeek 路径会接受该动作。

然后实现一个窄、fail-closed 的 DeepSeek 成功动作守卫：

> 仅在公开 history/table 严格一致地证明由队友领牌、模型选择用明确的高价值控制资源继续压制、原始 pass 合法、本家不能借该动作立即出完、且没有已结束或只剩 1/2 张的对手压力时，才把模型动作改为原始 pass ID。

最低必须覆盖“小王由队友领牌、模型用大王压制”的可证明场景。是否安全复用现有 teammate-pressure 公共校验、以及是否把同一守卫扩展到已有明确分类的炸弹/同花顺/天王炸，由你在检查当前代码后决定；不得凭直觉把所有普通非 pass 都纳入。

如果无法从现有公开字段严格证明队友关系、最后有效领牌、table/history 一致、pass 身份、资源类型、立即出完或对手压力，必须保留模型原动作。

## 【需要检查的范围】

优先检查：

- `record.txt` 第 6 轮及 `docs/LIVE_GAME_REVIEW.md`
- `agents/conditional_pressure_pass_policy.py`
- `agents/deepseek_ai.py`
- `agents/rule_based_ai.py`
- `agents/short_endgame_planner.py`
- `integrations/botzone/play_adapter.py`
- `integrations/botzone/agent_observability.py`
- 对应 conditional、DeepSeek、adapter 与 observability 测试

先定位真实绕过点和现有共享校验能力，再选择最小实现位置。优先复用或小幅扩展现有严格公开 payload 校验；不要在 adapter 或 engine 中另建策略逻辑。

不要强制只修改上述文件。允许在 `agents/` 内新增职责单一的纯公开数据 helper，并修改必要的低基数 observability 和测试；不得修改 engine、session、transport、history 文件格式、audit schema/version 或真实 workspace。

## 【本次任务约束】

- 只处理跟牌场景；自由出牌不得触发。
- 必须严格证明当前桌面动作来自本家队友，且 history 最后有效非 pass 与 table action 的共同语义一致。
- 必须从原始 legal actions 取得 pass ID；最终返回值仍须是原始合法 action ID。
- 模型动作能立即出完时不得覆盖。
- 任一对手已结束或公开剩余 1/2 张时，保守地不触发本守卫，避免削弱已有危险对手处理。
- 不得把所有“压队友”的普通动作一律改成 pass；资源范围必须由现有牌型/声明语义严格识别并有测试锁定。
- `danger_opponent_block` 优先级不得降低；自由出牌的 `short_endgame_plan` 不应与本守卫同时命中。
- 若新增低基数 source，应计为一次成功模型尝试，不计 rule fallback；不改变 audit 版本，不保存逐步牌面。
- 不改变默认 RuleBased 的两项保牌规则、冻结旧 selector、DeepSeek 失败 fallback、显式 `conditional_pressure_pass` mode 或历史 evaluation 语义。
- 不新增依赖，不建立 evaluation 模块，不运行 200/400 局报告或任何百局/千局容量。
- 不运行 Botzone、Edge、connector、网络或真实模型；显式禁用 dotenv 运行测试，不读取 `.env`，不触碰 `D:\VsCodeProject\BotzoneWorkspace`。
- 不创建 Git commit。

## 【重要不变量】

- 规则只消费公开 observation 和调用时原始 legal actions。
- 不自行制造 pass、牌型或 Botzone carrier/claim。
- payload 畸形、证据不足或语义不一致时保留合法模型动作，不能转成失败 fallback。
- 玩家编号、轮次和“小王/大王” action ID 不得硬编码；测试可使用脱敏 fixture，业务逻辑只能依据公开团队关系与动作语义。
- 固定级牌 2、无贡、单局以及不做跨级牌/贡还/升级赛属于完成范围，不得列为剩余风险。

## 【验证要求】

新增或调整确定性测试，至少覆盖：

1. 队友小王领牌、模型成功选择大王、pass 合法、不能立即出完、无危险对手时，改选原始 pass ID；
2. 相同场景在真实 `DeepSeekAIAgent.select_action()` 成功路径生效，模型调用仍只计一次；
3. 自由出牌、对手领牌、history/table 不一致、队伍字段畸形、没有 pass、模型本来选 pass 时均不触发；
4. 模型动作可立即出完时不触发；任一对手已结束或余 1/2 张时不触发；
5. 普通低价值非 pass 不因“队友领牌”被宽泛拦截；若扩展到炸弹类，逐类覆盖允许范围和非允许反例；
6. `danger_opponent_block` 与 `short_endgame_plan` 的既有优先级、source 和行为不回归；
7. DeepSeek success/timeout/exception/invalid action、冻结 fallback、默认 RuleBased 两项保牌、显式 conditional mode继续通过；
8. 若新增 source，Botzone decision/model/outcome/fallback 守恒与 audit 版本保持不变。

先运行直接相关测试，再显式禁用 dotenv 运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_game_flow tests.test_rules tests.test_patterns tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

## 【完成标准】

- 当前 DeepSeek 成功动作接受队友控桌高价值压制的路径已被 fixture 复现；
- 窄守卫能修正队友小王后用大王压制的目标场景，同时不扩大为普遍禁止压队友；
- 立即出完、危险对手、证据不足和非目标动作保持原模型选择；
- 原始 action ID、现有三项策略守卫、observability 守恒与 fallback 语义无回归；
- 定向、主回归、全量测试和补丁检查通过；
- 未运行 live、网络、模型或新容量，未读取 `.env` 或触碰真实 workspace，未创建 Git commit。

## 【执行后的报告要求】

最终报告必须包含：

1. 当前绕过路径与复现结果；
2. 新守卫的精确触发条件、资源范围与 fail-closed 边界；
3. 为什么没有实现“队友领牌一律 pass”；
4. 修改文件列表；
5. observability/source 是否变化及守恒方式；
6. 新增/调整的关键测试；
7. 实际执行的全部验证命令、测试数量和结果；
8. 是否运行新容量、live、网络或模型（预期均为否）；
9. 当前项目范围内的剩余风险或未解决问题；如无，应明确写“当前范围内无已知剩余风险”。既定范围不得列为风险。
