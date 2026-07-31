# 下一步实施提示词

## Step J-D1c3c1：最小 runtime confidence 数据契约

请在 GuanDan 项目中实现 Step J-D1c3c1。任务是把已经通过多策略正式校准的 J-D1b 精确整数边际转换为一个最小、不可变、可审计、fail-closed 的 runtime confidence 状态。

本步骤只建立数据契约和单元测试，不接入 DeepSeek、RAG、提示词、动作剪枝、策略路由或动作选择。

## 一、前置结论

J-D1c3b2 已完成：

- HEAD `b2491a810f81eb6dc20f1732efd89b6705f56458`；
- seed `8000..8119`，forced/25/50/100 四策略各 120 局；
- 双运行报告完全一致，SHA-256 为 `425bf197c7642894ebb6a0293383b94c160bdddb9dc44c180216278e200e113e`；
- 16 个策略/范围全部通过完整性、支持度、certainty、ECE、Brier skill 和 supported MCE 护栏；
- 唯一判定 `policy_diverse_calibration_verified`。

该结论只授权建立 runtime 数据契约，不授权影响动作决策，也不证明胜率提升。

## 二、修改范围

只允许新增：

- `agents/card_confidence.py`
- `tests/test_card_confidence.py`

不要修改：

- `engine/`
- 现有 J-A、J-B1、J-B2/J-D1b 数据结构或搜索逻辑
- `evaluation/`
- `agents/deepseek_ai.py`
- `agents/deepseek_client.py`
- `agents/rag_advisor.py`
- opening strategy、动作剪枝、CLI、RAG corpus
- docs

不得新增第三方依赖。

## 三、输入边界

提供纯函数：

```python
build_card_confidence(
    card_belief: CardBeliefState,
    constraints: CardConstraintState,
    allocation: CardAllocationResult,
) -> CardConfidenceState
```

函数只能消费传入的三个不可变公开推断对象：

- J-A `CardBeliefState`
- J-B1 `CardConstraintState`
- 完整 J-D1b `CardAllocationResult`

禁止：

- 读取 observation 或 history；
- 读取 `game._state` 或任何隐藏手牌；
- 导入 `evaluation/`；
- 调用游戏引擎；
- 重新枚举分配；
- 使用 pass、牌型或其他行为信号修正边际。

## 四、输出契约

在 `agents/card_confidence.py` 新增 frozen、slots dataclass：

### `RankMarginalConfidence`

至少包含：

- `rank: str`
- `presence_numerator: int`
- `expected_copy_numerator: int`
- `denominator: int`

提供只读派生语义：

- `is_certain` 仅在 `presence_numerator == denominator` 时为真；
- `is_impossible` 仅在 `presence_numerator == 0` 时为真。

不要输出 float、百分比、四舍五入值或 high/medium/low 标签。

### `PlayerCardConfidence`

至少包含：

- `player_id`
- `remaining_capacity: int`
- `ranks: tuple[RankMarginalConfidence, ...]`

### `CardConfidenceState`

至少包含：

- `phase: str`
- `status: str`，只能是 `available` 或 `unavailable`
- `source: str`，available 时固定为 `physical_assignment_marginal_v1`
- `calibration_scope: str`，available 时固定为 `critical_endgame_policy_diverse_v1`
- `external_unknown_count: int`
- `physical_assignment_count: int`
- `players: tuple[PlayerCardConfidence, ...]`
- `diagnostics: tuple[str, ...]`

三个 dataclass 都提供 JSON 友好的 `to_dict()`。

available 状态中的概率解释为：

```text
rank presence = presence_numerator / physical_assignment_count
expected rank copies = expected_copy_numerator / physical_assignment_count
```

这只是公开硬约束下等权物理分配模型的组合边际，不是独立牌概率，也不是整手牌概率。

## 五、available 的必要条件

只有以下条件全部满足时才能输出 `status=available`：

1. 三个输入的 phase 完全一致且为 `critical_endgame`；
2. `card_belief.token_pool_exact=True`；
3. `card_belief.diagnostics` 为空；
4. `constraints.token_constraints_exact=True`；
5. `constraints.is_consistent=True`；
6. `constraints.diagnostics` 为空；
7. `allocation.status == "complete"`；
8. `allocation.search_complete=True`；
9. `allocation.diagnostics` 为空；
10. `physical_assignment_count` 为非 `bool` 正整数；
11. `external_unknown_count` 为 1 至 12 的非 `bool` 整数；
12. `allocation.total_unseen_cards == external_unknown_count`；
13. 候选玩家集合、玩家 ID、剩余容量和容量总和一致；
14. 每位 allocation 玩家都对应未完赛、剩余容量大于 0 的公开玩家；
15. 每位玩家的 rank mapping key 与所有正数 `unseen_cards_by_rank` 完全一致；
16. 所有 rank count、presence 分子和 copy 分子均为合法非 `bool` 整数；
17. 对每个玩家/rank，`0 <= presence_numerator <= denominator`；
18. 对每个玩家/rank，copy 分子不为负，且不超过该玩家容量和该 rank 总副本数允许的上界；
19. 对每个 rank，跨玩家 copy 分子之和严格等于 `rank_count * denominator`。

不要假设手工构造的 dataclass 一定合法；所有运行时边界都必须显式校验。

## 六、fail-closed 行为

任一必要条件失败时：

- 返回 `status=unavailable`；
- `physical_assignment_count=0`；
- `players=()`；
- 不保留任何部分 rank 边际；
- diagnostics 使用稳定、去重、可审计的类别；
- 不抛出由 malformed mapping、玩家 ID 或整数值导致的意外异常。

diagnostics 至少覆盖：

- `unsupported_phase`
- `phase_mismatch`
- `token_pool_inexact`
- `belief_diagnostics_present`
- `constraints_inexact`
- `constraints_inconsistent`
- `constraint_diagnostics_present`
- `allocation_not_complete`
- `allocation_diagnostics_present`
- `invalid_external_unknown_count`
- `external_count_mismatch`
- `invalid_physical_assignment_count`
- `player_set_mismatch`
- `capacity_mismatch`
- `rank_key_mismatch`
- `invalid_rank_count`
- `invalid_presence_numerator`
- `invalid_copy_numerator`
- `copy_conservation_mismatch`

可以增加必要诊断，但不要把异常原始对象、手牌或隐藏信息写入诊断。

## 七、稳定性与顺序

- 玩家顺序沿用 `allocation.players`；
- rank 使用项目 canonical 顺序：`3..10,J,Q,K,A,2,SJ,BJ`，只输出公开未见数量为正的 rank；
- 输出只含不可变 tuple 或 frozen dataclass；
- `to_dict()` 每次调用结果稳定；
- 输入 mapping 的插入顺序不同不得改变语义输出；
- `bool` 不得被当成整数接受。

## 八、测试要求

`tests/test_card_confidence.py` 至少覆盖：

1. 一个小型完整分配的 presence 与 expected-copy 精确分子/分母；
2. 同 rank 多 token 的 presence 使用 J-D1b 已聚合并集分子，不重新相加 token presence；
3. `is_certain` 与 `is_impossible` 边界；
4. 多玩家 copy 分子守恒；
5. canonical rank 顺序与稳定玩家顺序；
6. frozen/slots、不可变输出和 JSON 序列化；
7. near-open、普通 endgame、opening、midgame 全部 unavailable；
8. token pool 不精确、constraints 不精确或不一致；
9. allocation truncated、invalid、skipped、无解或 search 不完整；
10. phase、外部牌数、玩家集合、容量和 rank key 不一致；
11. 分母为 0、负数、`bool` 或非法类型；
12. presence/copy 分子越界、`bool`、非法类型或守恒失败；
13. 任一失败时零分母、空 players，且不泄露部分结果；
14. `agents/card_confidence.py` 不导入 `evaluation`、engine、DeepSeek 或 RAG；
15. 现有 decision path 不导入或调用新模块。

不要使用 ground truth 测试 runtime 输出；真值校准已经在 J-D1c3b2 完成。

## 九、验证命令

先运行定向测试：

```bash
python -m unittest tests.test_card_confidence tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_game_phase -q
```

再运行全量测试：

```bash
python -m unittest discover -q
git diff --check
```

边界扫描：

```bash
rg -n "evaluation|ground_truth|game\._state|observation|history|deepseek|rag" agents/card_confidence.py
rg -n "card_confidence" agents/deepseek_ai.py agents/deepseek_client.py agents/rag_advisor.py cli engine
```

第一条只允许 docstring 或注释中对禁止边界的说明，不允许实际导入或读取；第二条必须无匹配。

## 十、验收标准

完成后必须同时满足：

- 只新增两个约定文件；
- available 仅覆盖已正式验证的 critical、<=12 外部未知牌范围；
- 所有概率量保持精确整数分子/分母；
- malformed 或不完整输入整体 unavailable；
- 不读取真值或引擎内部状态；
- 不修改现有动作选择和合法动作集合；
- 定向和全量测试通过；
- `git diff --check` 通过。

## 十一、输出要求

最终报告必须包含：

1. 修改文件；
2. 输出 dataclass 与 builder 的实际字段；
3. available 的完整前置条件；
4. fail-closed diagnostics；
5. 定向与全量测试结果；
6. 边界扫描结果；
7. 明确说明未接入 DeepSeek、RAG、提示词、剪枝或动作决策；
8. 明确说明这不是策略收益或胜率结论。

完成后停止，不扩展到 J-D1c3c2，不修改 docs。
