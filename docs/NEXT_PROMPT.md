# 下一步实施提示词

## Step K-A1：公开策略意图上下文与确定性路由契约

请在 GuanDan 项目中实现 Step K-A1。任务是新增一个 agent-side、只读公开信息的策略路由模块，在不修改合法动作、不调用模型或 RAG 的情况下，确定性输出当前策略意图：`run_out`、`block_opponent`、`support_teammate` 或 `control`。

本步骤只建立数据契约和路由优先级，不接入 DeepSeek、RAG、剪枝或动作选择，不形成策略质量或胜率结论。

## 一、前置结论

Step J-D1c3c2c3c2b 的独立只读恢复审计判定：

```text
no_observed_action_quality_gain
```

关键事实：

- c3c2a 原 `quality_recovery_invalid` 保持不变；
- 24 pair 中 same/changed=15/9；
- on/off better=0/0，tie=24；
- off/on team win=10/10；
- 33 个 rollout branch 全部完成；
- confidence prompt 不进入完整对局评估，默认继续关闭。

K-A1 不得消费 `CardConfidenceState` 或 confidence prompt。Step J 的公开事实和硬约束能力继续保留，但未证明收益的 confidence 不作为策略路由输入。

## 二、允许修改范围

只允许新增：

- `agents/strategy_router.py`
- `tests/test_strategy_router.py`

不得修改：

- `engine/`
- 其他 `agents/` 文件
- `evaluation/`
- `cli/`
- `rag/` 及知识库内容
- `config.py`
- `.env` / `.env.example`
- `docs/`

不得新增依赖。

## 三、公开 API

在 `agents/strategy_router.py` 中提供：

- `RUN_OUT = "run_out"`
- `BLOCK_OPPONENT = "block_opponent"`
- `SUPPORT_TEAMMATE = "support_teammate"`
- `CONTROL = "control"`
- `StrategyIntentContext`
- `route_strategy_intent(...)`

建议签名：

```python
route_strategy_intent(
    observation: dict[str, object],
    legal_actions: list[dict[str, object]],
    *,
    phase_context: GamePhaseContext,
    hand_evaluation: dict[str, object],
) -> StrategyIntentContext
```

必须由调用方传入统一 `GamePhaseContext`。模块不得调用 `classify_game_phase()`，不得重复判断阶段。

## 四、输出契约

`StrategyIntentContext` 使用 `@dataclass(frozen=True, slots=True)`，至少包含：

- `status`：`available` / `unavailable`
- `source`：固定 `public_strategy_router_v1`
- `phase`
- `intent`：四种意图之一；unavailable 时为 `None`
- `reason_codes`：稳定、可审计的 tuple
- `my_player_id`
- `my_team`
- `my_hand_count`
- `teammate_player_id`
- `teammate_hand_count`
- `minimum_opponent_hand_count`
- `urgent_opponent_ids`
- `can_finish_now`
- `is_free_lead`
- `hand_strength`
- `hand_total_score`
- `hand_control_score`
- `diagnostics`

提供 JSON 友好的 `to_dict()`；tuple 输出为 list。不得包含 observation、legal action、手牌 token、history、隐藏状态或 engine 对象。

available 时 diagnostics 必须为空。任一基础输入无效时整体 fail-closed：

- `status="unavailable"`
- `intent=None`
- 不保留部分策略结论
- diagnostics 使用稳定类别

## 五、唯一数据来源

只允许消费调用参数中的：

- `phase_context`
- `observation.my_info.player_id/team/hand_count`
- `observation.other_players[].player_id/team/hand_count/finished`
- `observation.current_round.constraint/table_action`
- `legal_actions[].declared_pattern/carrier_cards`
- `hand_evaluation.total_score/control_score/label`

不得读取：

- observation 中未列出的扩展字段；
- history 行为作为软推断；
- CardBelief/CardConstraint/CardAllocation/CardConfidence；
- RAG 文档或命中；
- DeepSeek 输出；
- `game._state`、ground truth 或其他玩家真实手牌；
- 环境变量或配置。

## 六、基础校验

严格校验，不接受 bool 冒充 int：

1. observation 必须为 dict，legal_actions 必须为非空 list；
2. phase_context 必须为 `GamePhaseContext`；
3. phase 必须是现有五种阶段之一；
4. self player ID 必须为 1..4，team 必须与座位固定团队一致：1/3=`1&3`，2/4=`2&4`；
5. other_players 必须恰好包含另外三个唯一玩家 ID；
6. 每个玩家 team 必须与 player ID 一致；
7. hand_count 必须为非 bool 非负整数；
8. finished 必须严格为 bool；
9. 恰好识别一位队友和两位对手；
10. phase_context 的 my/other hand counts 必须与 observation 一致；
11. phase_context external unknown count 必须等于未完赛其他玩家 hand_count 之和；
12. hand evaluation 的 total_score 为 0..100、control_score 为 0..30 的严格整数；
13. label 必须为 `极弱/偏弱/中等/较强/极强`，并与 total_score 现有阈值一致；
14. 每个 legal action 必须为 dict，declared_pattern 为非空字符串，carrier_cards 为 list；
15. current round 的 constraint/table_action 组合必须能稳定判断 free lead 或 follow。

建议 diagnostics：

- `invalid_observation`
- `invalid_legal_actions`
- `invalid_phase_context`
- `phase_mismatch`
- `opening_not_routed`
- `invalid_player_id`
- `invalid_team`
- `player_set_mismatch`
- `duplicate_player`
- `invalid_hand_count`
- `invalid_finished_flag`
- `relationship_mismatch`
- `external_count_mismatch`
- `invalid_hand_evaluation`
- `hand_label_mismatch`
- `malformed_action`
- `invalid_round_context`

同一输入多项异常时 diagnostics 去重并保持固定顺序。

## 七、阶段边界

- `opening` 不进入 K 路由，返回 unavailable + `opening_not_routed`；
- `midgame`、`endgame`、`near_open_endgame`、`critical_endgame` 可路由；
- critical 路由不得自动读取 confidence；
- finished 玩家不参与紧急手数比较；
- hand_count=0 且 finished=false 视为输入不一致并 fail-closed。

## 八、派生事实

### 立即出完

`can_finish_now=True` 当且仅当至少一个合法动作：

- `declared_pattern != "pass"`；
- `len(carrier_cards) == my_hand_count`；
- my_hand_count > 0。

不得自行构造动作或依赖 action ID。

### 自由首出

`is_free_lead=True` 当且仅当：

- `constraint == "free"`；
- `table_action is None`。

其他合法组合为 follow；互相矛盾或无法识别的组合 fail-closed。

### 紧急玩家

- 只看未完赛玩家；
- hand_count <= 2 定义为紧急；
- teammate hand count 单独记录；
- opponents 记录最小 hand count 和达到该最小值的稳定升序 ID；
- finished 玩家即使 hand_count=0 也不触发紧急策略。

### 手牌强弱

沿用 `evaluate_hand()` 的现有 label 阈值：

- `极弱` / `偏弱` 为 weak；
- `中等` / `较强` / `极强` 为 non-weak。

K-A1 不新增或校准新的分数阈值。

## 九、固定路由优先级

严格按以下顺序，命中后停止：

1. **立即出完**：`can_finish_now` -> `run_out`，reason `can_finish_now`；
2. **双方都有紧急玩家**：比较队友与最危险对手的 hand count；较少者优先；相等时防守优先 -> `block_opponent`；
3. **仅对手紧急**：-> `block_opponent`；
4. **仅队友紧急**：-> `support_teammate`；
5. **无紧急玩家且 weak**：-> `run_out`，reason `weak_hand`；
6. **其余合法局面**：-> `control`，reason `stable_control`。

双方紧急时 reason 分别固定为：

- `teammate_more_urgent`
- `opponent_more_urgent`
- `urgency_tie_block_opponent`

不得根据 pass 历史、牌面猜测、RAG 命中或 action 数量改变优先级。

## 十、明确非目标

K-A1 不得：

- 给 legal actions 打分、排序、过滤或选择 action ID；
- 修改 `DeepSeekAIAgent`；
- 修改 prompt 或 client kwargs；
- 修改 RAG scene tags/query/topics；
- 新增 config 开关；
- 读取或展示 confidence；
- 运行 API 或完整对局 A/B；
- 声明策略质量提升。

## 十一、测试要求

`tests/test_strategy_router.py` 至少覆盖：

1. dataclass frozen/slots、`to_dict()` 和稳定快照；
2. 五阶段边界，opening unavailable；
3. phase_context 只由调用方传入，路由器不调用 classifier；
4. 四个座位的 team/teammate/opponent 关系；
5. player 缺失、额外、重复、不可哈希/非法 ID；
6. bool、字符串、float、负 hand count；
7. finished 玩家从紧急比较排除；
8. phase hand counts/external count 一致性；
9. hand evaluation 分数、label 和阈值边界 0/19/20/39/40/59/60/79/80/100；
10. immediate finish 高于所有其他意图；
11. opponent-only urgent；
12. teammate-only urgent；
13. 双方紧急时队友更少、对手更少、同数防守；
14. weak -> run_out；
15. non-weak -> control；
16. free lead/follow 与矛盾 round context；
17. malformed legal action 和 pass 不算 finish；
18. diagnostics 去重、固定顺序和整体 unavailable；
19. 输入 observation/legal actions/phase/hand evaluation 不被修改；
20. 源码扫描不引用 DeepSeek、RAG、confidence、evaluation、engine state、ground truth、config 或环境变量；
21. 现有 runtime 模块不反向导入新 router。

测试使用公开 fixture，不得读取引擎内部状态。

## 十二、验证命令

至少运行：

```bash
python -m unittest tests.test_strategy_router -q
python -m unittest tests.test_strategy_router tests.test_game_phase tests.test_hand_evaluator tests.test_opening_strategy tests.test_deepseek_prompt_step_h -q
python -m unittest discover -q
git diff --check
```

并运行边界扫描，确认只新增两个允许文件，没有 runtime 集成或反向依赖。

## 十三、唯一开发判定

严格只输出一个：

1. 输入、关系、阶段、路由优先级、不可变性、JSON、边界或回归任一失败：`strategy_router_contract_invalid`；
2. 全部通过：`strategy_router_contract_verified`。

通过只授权 Step K-A2 shadow 装配与离线路由分布评测，不授权动作排序、RAG 定向、prompt 消费或默认策略改变。

## 十四、最终报告

完成后报告：

1. 修改文件；
2. 公开输入与禁止依赖边界；
3. dataclass 和 fail-closed 契约；
4. team/urgency/finish/hand-strength 派生规则；
5. 六级路由优先级；
6. 主要 malformed 诊断；
7. 定向、相关、全量测试与 `git diff --check`；
8. 边界扫描；
9. 唯一开发判定；
10. 明确说明未接 DeepSeek/RAG/confidence/动作选择，未形成策略收益或胜率结论。

完成后停止，不修改 docs，不扩展到 K-A2。
