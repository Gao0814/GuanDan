# 给 Coding Codex 的修正任务 Prompt

你负责修正当前未提交的“队友控桌高价值资源守卫”实现、补充测试并报告结果。不要回退该实现，不创建 Git commit，不运行 Botzone、网络、真实模型或容量评测。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/LIVE_GAME_REVIEW.md` 与相关代码和测试。

保持 engine/AI 边界：Agent 只能读取公开 `observation` 与原始 `legal_actions`，并返回其中已有的合法 `action_id`。当前固定级牌2、四人、无需进贡、单局是既定验收范围，不是风险。

Coding Codex 负责修改和验证，不创建 Git commit。完成后由项目规划 Codex 独立复核并提交。

## 【当前项目状态】

已提交基线为 `f0644d2`，其中最新算法检查点 `dc9638c` 的全量684项测试已通过。

当前工作区有7个未提交实现/测试文件，增加窄守卫 `teammate_big_joker_pass_id()`：队友单张小王领牌、模型选择单张大王、pass合法、不能立即出完且无危险对手时改选原始pass。目标策略范围和三个成功动作守卫的优先级合理，全量688项测试也通过，但规划复核发现共享 `_pressure_pass_context()` 的fail-closed校验不足，因此当前实现尚未验收。

独立最小复现最初观察到以下输入都返回pass ID `1`：

```text
constraint_none 1
constraint_empty 1
table_action_id_none 1  # 经代码复核确认这是合法canonical sentinel，应保持1
table_action_id_bool 1
```

原因有两处：

1. 当前只判断 `current_round.constraint != "free"`，导致缺失、`None`、空字符串、bool等非法值被当成跟牌；
2. `_full_action_signature()` 对table action只检查存在 `action_id` 键，没有验证它必须精确为canonical sentinel `None`。

后续代码复核已经确认公开契约：

- `engine/game.py::observe()` 调用 `_action_to_public_dict(leading_action)`，默认 `action_id=None`；
- `integrations/botzone/play_adapter.py` 调用 `_public_action(leading_action, None)`；
- `tests/test_botzone_adapter_observation.py` 明确断言跟牌桌面动作的 `action_id is None`；
- engine和Botzone投影都保证跟牌时 `current_round.constraint == table_action.display_text`。

因此不得把table action ID改成严格整数，也不得修改公开schema或伪造历史action ID。规划决定是：`None` 为table action唯一合法canonical sentinel；缺键以及任何非 `None` 值（包括bool、字符串和整数）均应fail closed。原始 `legal_actions` 的action ID仍保持严格整数，两类schema必须区分。

这两个问题位于既有共享校验器，也可能影响 `conditional_pressure_pass_id()`、`teammate_pressure_pass_id()` 和 `dangerous_opponent_pass_id()`；不要只在新helper外层打补丁。

## 【本次任务目标】

在共享公开payload校验层修复上述fail-closed缺口，使合法engine/Botzone跟牌payload保持原行为，而缺失或畸形的constraint/table action身份不再触发任何pressure-pass或teammate-control判定。

先核对当前 `observe()`、Botzone projection及现有测试中的canonical跟牌契约，再实现最小修正。至少要求：

- `constraint` 必须是项目实际支持的非空字符串跟牌值，不能是缺失、`None`、空字符串、bool或其他类型；
- table action必须包含 `action_id` 键且值精确为 `None`；不得把合法桌面sentinel与原始legal action的严格整数ID混为一谈；
- `constraint` 必须严格等于非空字符串 `table_action.display_text`，并且不能是 `"free"`；
- 新旧四个公开策略helper在同类畸形输入上都应fail closed；
- 合法“小王→大王”目标场景仍返回原始pass ID，DeepSeek成功路径和source守恒保持不变。

## 【需要检查的范围】

优先检查：

- `agents/conditional_pressure_pass_policy.py`
- `agents/deepseek_ai.py`
- `engine/game.py`、`engine/actions.py` 中公开observation/action序列化契约
- `integrations/botzone/play_adapter.py` 的observation/table action投影
- `tests/test_game_flow.py`
- `tests/test_botzone_adapter_observation.py`
- `tests/test_conditional_pressure_pass.py`
- `tests/test_deepseek_step_e.py`
- `tests/test_botzone_agent_observability.py`

修复应优先落在共享validator及对应测试。除非验证暴露直接必要性，不要继续扩大策略范围或修改其他模块。

## 【本次任务约束】

- 保留当前7个文件中的目标守卫实现，不回退或另写第二套校验。
- 不改变“小王→大王”的冻结资源范围，不扩展到普通牌、全部炸弹或“队友领牌一律pass”。
- 不改变守卫顺序：`danger_opponent_block` → `teammate_control_block` → `short_endgame_plan`。
- 所有helper只读取公开payload和原始legal actions；所有返回值仍来自原始action ID。
- 畸形数据必须保留模型/基线原动作，不能转成异常fallback。
- 不改变RuleBased既有两项保牌、冻结selector、DeepSeek失败fallback、显式conditional mode、audit schema/version或history格式。
- 不新增依赖，不运行容量、Botzone、Edge、connector、网络或真实模型。
- 显式设置 `PYTHON_DOTENV_DISABLED=1`；不读取`.env`，不触碰 `D:\VsCodeProject\BotzoneWorkspace`。
- 不创建Git commit。

## 【验证要求】

测试至少新增以下反例，并确认四个共享策略入口适用时均fail closed：

1. `constraint` 缺失、`None`、空字符串、bool、列表；
2. table action `action_id` 缺失、bool、字符串、整数时拒绝；精确 `None` 时接受；
3. constraint与table display不一致时拒绝；
4. 合法跟牌payload继续通过；合法队友小王/模型大王仍返回原始pass；
5. DeepSeek目标fixture仍输出 `teammate_control_block`，模型调用一次；
6. `danger_opponent_block`、`short_endgame_plan`、RuleBased两项pass和Botzone observability守恒继续通过。

先运行直接相关测试，再显式禁用dotenv运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

另外用最小只读脚本重新运行上述输入：`constraint=None`、`constraint=""`、table `action_id=True` 必须从 `1` 变为 `None`；合法table `action_id=None` 必须继续返回 `1`。再增加table ID缺失、字符串、整数及constraint/display不一致反例。

## 【完成标准】

- 三个真实畸形反例返回 `None`，合法table `action_id=None` sentinel继续返回 `1`；
- 共享校验器对constraint和table action身份严格fail closed；
- 合法目标守卫、三个成功动作source优先级和原始action ID不回归；
- 定向、主回归、全量测试和补丁检查通过；
- 未扩大策略范围，未运行live/容量/网络/模型，未触碰`.env`或真实workspace，未创建Git commit。

## 【执行后的报告要求】

最终报告必须包含：

1. 两个共享校验缺口的根因；
2. 实际修正的不变量；
3. constraint与table display的canonical相等契约及代码依据；
4. 三个畸形反例和一个合法sentinel修正前后的结果；
5. 修改文件；
6. 新增/调整测试；
7. 实际验证命令、测试数量与结果；
8. 是否运行live、容量、网络或模型（预期均为否）；
9. 当前范围内剩余风险；固定级牌2、无贡、单局不得列为风险。
