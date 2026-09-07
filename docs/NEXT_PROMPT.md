# 给 Coding Codex 的契约恢复任务 Prompt

你负责修正当前未提交的队友控桌守卫实现。当前代码错误修改了table-action公开action-ID契约；必须撤销这部分范围扩张，同时保留队友小王→大王守卫和正确的constraint校验。不要创建Git commit，不运行Botzone、网络、真实模型或容量评测。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md` 与相关代码和测试。

AI只读取公开observation与原始legal actions，并返回原始合法action ID。不要伪造历史动作ID，不要为了策略validator改变engine或Botzone公开schema。固定级牌2、四人、无需进贡、单局是既定范围，不是风险。

Coding Codex负责修改和验证，不创建Git commit；完成后由项目规划Codex独立复核和提交。

## 【当前项目状态】

已提交基线为 `45332eb`；最新已验收算法检查点为 `dc9638c`，全量684项通过。

当前工作区包含尚未提交的队友控桌守卫及一次错误修正。队友守卫本身的目标范围合理：严格公开证据证明队友单张小王领牌、模型成功选择单张大王、pass合法、不能立即出完且无危险对手时，改选原始pass，并记录 `teammate_control_block`。

错误修正把table action的 `action_id=None` 改成了整数：

- `engine/state.py` 新增 `TableConstraint.leading_action_id`；
- `engine/game.py` 保存上一动作当时的legal action ID，preset场景人为填 `0`；
- `integrations/botzone/play_adapter.py` 把公开history step编号当成table action ID；
- 原本明确断言 `action_id is None` 的Botzone测试被改成断言整数；
- `_full_action_signature()` 被改成要求table action ID为严格整数。

这些整数不是同一种可靠身份：engine值属于上一玩家当时的legal-action空间，Botzone值只是history step，preset值是人为sentinel `0`。它们不能统一表示table action的原始合法ID，也与当前玩家的legal action ID无关。

已确认的canonical公开契约是：

- engine跟牌table action由 `_action_to_public_dict(leading_action)` 生成，`action_id=None`；
- Botzone跟牌table action由 `_public_action(leading_action, None)` 生成，`action_id=None`；
- `tests/test_botzone_adapter_observation.py` 在已提交基线明确锁定 `action_id is None`；
- engine和Botzone都保证跟牌时 `current_round.constraint == table_action.display_text`。

## 【本次任务目标】

恢复并锁定原公开契约：table action必须包含 `action_id` 键且值精确为 `None`；原始legal actions的action ID仍为严格整数。两种schema不得混用。

在不改变table-action schema的前提下修正共享 `_pressure_pass_context()`：

1. `constraint` 必须是非空字符串、不能是 `"free"`，并严格等于 `table_action.display_text`；
2. table action必须包含 `action_id` 且值精确为 `None`；缺键或任何非None值均fail closed；
3. legal actions继续由现有 `_valid_actions()` 单独验证严格整数ID；
4. 合法队友小王→大王守卫仍返回原始pass ID；其他三个共享pressure helper保持合法行为。

## 【必须撤销的未提交改动】

只撤销当前工作区中擅自改变公开schema的部分，不得用破坏性Git命令覆盖其他未提交守卫代码：

- 删除 `engine/state.py` 新增的 `leading_action_id` 字段；
- 撤销 `engine/game.py` 对该字段的写入、传递及preset `0`；恢复table action序列化时不传历史action ID；
- 删除Botzone `_table_history_action_id()` 及 `missing_table_action_identity` 新门槛；恢复 `_public_action(leading_action, None)`；
- 恢复Botzone测试对 `table_action["action_id"] is None` 的断言；
- 不保留任何history-step-as-action-ID逻辑。

保留并完善：

- 队友小王→大王守卫；
- DeepSeek三个成功动作守卫的优先级；
- `teammate_control_block` observability；
- constraint类型、非空及constraint/display一致性校验；
- 对所有共享helper的畸形输入回归。

## 【需要检查的范围】

优先检查：

- `agents/conditional_pressure_pass_policy.py`
- `agents/deepseek_ai.py`
- `engine/state.py`
- `engine/game.py`
- `integrations/botzone/play_adapter.py`
- `tests/test_conditional_pressure_pass.py`
- `tests/test_game_flow.py`
- `tests/test_botzone_adapter_observation.py`
- DeepSeek与Botzone observability相关测试

不要修改audit schema/version、session、transport、history格式、evaluation或真实workspace。

## 【验证要求】

测试必须证明：

1. 合法engine跟牌observation的table action ID为 `None`，constraint等于display；
2. 合法Botzone跟牌projection的table action ID为 `None`，constraint等于display；
3. 所有共享pressure helper在合法fixture中保持预期行为，fixture的table action ID使用 `None`；
4. `constraint`缺失、None、空字符串、bool、列表及constraint/display不一致全部fail closed；
5. table action ID缺键、bool、字符串、整数全部fail closed；精确None合法；
6. 队友小王→大王目标场景返回原始pass，立即出完、危险对手、普通动作和非目标场景不触发；
7. `danger_opponent_block`、`short_endgame_plan`、`teammate_control_block`顺序与Botzone守恒不回归；
8. 仓库中不再存在 `leading_action_id`、`_table_history_action_id` 或 `missing_table_action_identity`。

先运行相关测试，再显式禁用dotenv运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

另做只读搜索确认三个错误标识已完全移除，并用最小脚本验证：

```text
constraint_none -> None
constraint_empty -> None
table_action_id_none -> 原合法结果（目标fixture为pass ID 1）
table_action_id_bool -> None
table_action_id_integer -> None
constraint_display_mismatch -> None
```

## 【完成标准】

- table-action `action_id=None` 公开契约已恢复且有engine/Botzone测试锁定；
- history step、上一玩家legal ID和preset 0均不再冒充table action ID；
- constraint/display及table sentinel严格fail closed；
- 队友控桌守卫、原始action ID、三个成功动作source和fallback语义无回归；
- 相关、主回归、全量测试及补丁检查通过；
- 未运行live、容量、网络或模型，未触碰`.env`或真实workspace，未创建Git commit。

## 【执行后的报告要求】

最终报告必须包含：

1. 为什么三类整数身份不能作为统一table action ID；
2. 实际撤销的schema/state改动；
3. 共享validator最终的legal-action ID与table-action sentinel双契约；
4. 六类最小反例/合法sentinel结果；
5. 修改文件；
6. 新增或恢复的测试；
7. 实际验证命令、测试数量和结果；
8. 是否运行live、容量、网络或模型（预期均为否）；
9. 当前范围内剩余风险；固定级牌2、无贡、单局不得列为风险。
