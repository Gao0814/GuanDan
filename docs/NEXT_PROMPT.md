# 下一步实施提示词

## Step J-D1c1：单样本组合边际离线评分

请在 GuanDan 项目中实现 Step J-D1c1。目标是为 J-D1b 的逐玩家 rank 整数边际建立 evaluation-only、真值隔离、可精确聚合的单样本评分契约。

本步骤不向 runtime 输出概率或置信度，不运行正式多种子基准，不接入 RAG、DeepSeek、动作剪枝或策略主链。

## 一、开始前检查

先阅读：

- `agents/card_belief.py`
- `agents/card_allocations.py`
- `evaluation/belief_metrics.py`
- `evaluation/ranking_metrics.py`
- `tests/test_belief_metrics.py`
- `tests/test_ranking_metrics.py`
- `tests/test_card_allocations.py`
- `docs/BELIEF_STATE.md`
- `docs/PROJECT_STATUS.md`

确认 J-D1b 当前契约：

- `CardAllocationResult.physical_assignment_count` 是完整物理分配总数；
- `PlayerAllocationBounds.holding_assignment_count_by_rank` 是玩家至少持有该 rank 一张的物理分配权重和；
- `PlayerAllocationBounds.copy_assignment_count_by_rank` 是玩家持有该 rank 副本数的加权和；
- 只有 `status="complete"`、`search_complete=True` 且有可行解时输出边际；
- rank 映射已严格支持 `10S -> 10`、`SJ` 和 `BJ`。

开始前运行：

```bash
python -m unittest tests.test_card_allocations tests.test_belief_metrics tests.test_card_ranker tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q
```

当前独立复核基线为定向 139 项、全量 263 项通过。若结果不同，先报告实际状态，不要覆盖不明改动。

## 二、允许修改范围

只新增：

- `evaluation/marginal_metrics.py`
- `tests/test_marginal_metrics.py`

不要修改：

- `engine/`
- `agents/`
- J-A/J-B/J-D1a/J-D1b 契约
- 现有 evaluation 模块和 benchmark
- RAG、DeepSeek、CLI
- docs
- 依赖配置

使用标准库 `fractions.Fraction`，不要新增第三方依赖。

## 三、模型解释边界

对玩家 `p` 和 rank `r`：

```text
holding marginal =
    holding_assignment_count_by_rank[p][r]
    / physical_assignment_count

expected copy count =
    copy_assignment_count_by_rank[p][r]
    / physical_assignment_count
```

这些值只表示：

> 在满足当前公开硬约束的可行物理分配等权模型下的组合边际。

不得称为已经校准的经验置信度，不得假设不同玩家/rank 事件相互独立，不得相乘得到整手牌概率。

## 四、建议公开数据结构

在 `evaluation/marginal_metrics.py` 中定义冻结、slots dataclass。

### 1. MarginalCalibrationBin

至少包含：

```python
bin_index: int
prediction_count: int
prediction_sum_numerator: int
prediction_sum_denominator: int
truth_positive_count: int
```

语义：

- 固定 10 个桶，索引为 0..9；
- 桶 0..8 为 `[i/10, (i+1)/10)`；
- 桶 9 为 `[0.9, 1.0]`；
- `prediction_sum_*` 是桶内所有持有边际概率之和的最简有理数；
- 空桶使用 `0/1`。

### 2. MarginalEvaluationReport

至少包含：

```python
phase: str
valid_input: bool
prediction_source: str
physical_assignment_count: int
rank_pair_count: int
truth_positive_pair_count: int
certainty_error_count: int
presence_brier_sum_numerator: int
presence_brier_sum_denominator: int
copy_squared_error_sum_numerator: int
copy_squared_error_sum_denominator: int
calibration_bins: tuple[MarginalCalibrationBin, ...]
diagnostics: tuple[str, ...]
```

要求：

- valid 报告的 `prediction_source="j_d1b_physical_marginals"`；
- invalid 报告的 `prediction_source="none"`；
- 分数保存“误差和”的精确最简分数，不在本步骤计算平均值；
- 分母始终为正，零误差表示为 `0/1`；
- `to_dict()` 只输出 JSON 友好的整数、布尔值、字符串、列表和 dict；
- 报告不包含逐玩家预测、逐 rank 预测、真实 token、真实 rank 列表或真实手牌。

可以增加实现所需的少量聚合字段，但不要输出真值明细。

## 五、输入接口

建议函数：

```python
evaluate_rank_marginals(
    card_belief: CardBeliefState,
    allocation: CardAllocationResult,
    ground_truth_hands: Mapping[object, Sequence[str]],
) -> MarginalEvaluationReport
```

约束：

- ground truth 只能由离线调用方显式传入；
- 模块不得读取 observation、`game._state`、引擎对象、文件或环境变量；
- runtime `agents/`、CLI 和 RAG 不得导入 `evaluation`；
- 不修改传入对象。

## 六、fail-closed 校验

以下任一情况返回 `valid_input=False` 的零化报告，不做部分评分：

1. `card_belief.token_pool_exact=False`；
2. allocation phase 与 belief 不一致；
3. allocation 不是 complete，或 `search_complete=False`；
4. `physical_assignment_count` 不是非 bool 正整数；
5. allocation 总未见牌数与 belief 不一致；
6. 活跃外部玩家集合不一致；
7. allocation 玩家容量与公开剩余容量不一致；
8. 正数公开 rank 集合与任一玩家两个 rank mapping 的 key 不完全一致；
9. rank numerator 不是非 bool 非负整数；
10. holding numerator 大于物理分母；
11. copy numerator 大于 `rank_count * physical_assignment_count`；
12. 任一 rank 的跨玩家 copy numerator 不满足守恒；
13. ground truth 缺失或多出玩家；
14. 真实手牌数量与公开容量不一致；
15. truth token 非法；
16. truth token multiset 与公开未见 token pool 不完全一致。

诊断至少使用稳定类别：

- `token_pool_inexact`
- `allocation_phase_mismatch`
- `allocation_not_complete`
- `invalid_physical_assignment_count`
- `allocation_card_count_mismatch`
- `missing_allocation_player`
- `unexpected_allocation_player`
- `allocation_capacity_mismatch`
- `rank_marginal_key_mismatch`
- `invalid_rank_marginal`
- `rank_copy_conservation_mismatch`
- `missing_truth_player`
- `unexpected_truth_player`
- `truth_hand_count_mismatch`
- `invalid_truth_token`
- `truth_pool_mismatch`

可附加公开标识诊断，但 `to_dict()` 不得泄露真实手牌明细。

invalid 报告要求：

- 所有计数字段为 0；
- 两个误差和为 `0/1`；
- 固定输出 10 个空 calibration bin；
- 不保留任何部分评分。

## 七、样本与评分定义

正数未见 rank 集合记为 `R`，活跃外部玩家集合记为 `P`。

对每个 `(player, rank) in P × R` 建立一个持有事件，不得只评估真值为正的 pair。

真实标签：

```text
y_presence = 1  if truth copy count > 0 else 0
y_copy = truth copy count
```

预测：

```text
p_presence = holding_numerator / physical_assignment_count
e_copy = copy_numerator / physical_assignment_count
```

### Presence Brier 误差和

```text
sum((p_presence - y_presence) ** 2)
```

用 `Fraction` 精确累计，报告最简整数分子/分母。

### Copy 平方误差和

```text
sum((e_copy - y_copy) ** 2)
```

同样使用 `Fraction` 精确累计。

### 确定性错误

以下任一情况计入 `certainty_error_count`：

- `p_presence == 0` 但 `y_presence == 1`；
- `p_presence == 1` 但 `y_presence == 0`。

确定性错误是有效评分结果，不要自动把报告改为 invalid。它表示组合模型或上游硬约束在该真值上发生严重错误。

## 八、校准分桶

使用整数算术确定桶：

```python
bin_index = min(9, holding_numerator * 10 // physical_assignment_count)
```

要求：

- `p=0` 进入桶 0；
- `p=0.1` 进入桶 1；
- `p=0.9` 和 `p=1` 进入桶 9；
- 每个 pair 恰好进入一个桶；
- 所有桶的 `prediction_count` 之和等于 `rank_pair_count`；
- 所有桶的 `truth_positive_count` 之和等于报告正例数；
- 桶内预测和用 `Fraction` 精确累计，不转 float。

## 九、最低测试覆盖

在 `tests/test_marginal_metrics.py` 至少覆盖：

1. 一个可手算的多玩家、多 rank 完整分配；
2. Brier 误差和的精确分子/分母；
3. copy 平方误差和的精确分子/分母；
4. rank pair 数包含正例和负例；
5. 固定 10 个 calibration bin；
6. `p=0`、`0.1`、`0.9`、`1` 的边界归桶；
7. 桶内预测和约分正确；
8. 确定性错误计数但报告仍有效；
9. `10S`、`SJ`、`BJ` truth 映射正确；
10. belief token pool 不精确时 fail closed；
11. phase 不一致时 fail closed；
12. truncated/skipped/invalid/no-feasible allocation fail closed；
13. 物理分母为 0、bool 或负数时 fail closed；
14. allocation 玩家缺失、多余、容量不一致；
15. rank key 缺失或多余；
16. holding/copy numerator 类型、范围错误；
17. rank copy 跨玩家守恒失败；
18. truth 玩家缺失、多余；
19. truth 手牌容量错误；
20. truth token 非法或 multiset 不一致；
21. invalid 报告所有指标零化且 10 个桶为空；
22. dataclass 冻结、嵌套结构不可变；
23. `to_dict()` 可被 `json.dumps(..., allow_nan=False)` 序列化；
24. 报告 payload 不包含真实手牌、token 或 rank 明细；
25. 固定输入重复执行报告完全相等；
26. 旧式手工 J-D1a allocation 缺少 rank mapping 时 fail closed，而不是静默评分。

建议主要精确夹具：

- token 为 `3S`、`3H`、`4C`，各 1 张；
- 两位玩家容量分别为 2 和 1；
- 三个 token 均可由两位玩家持有；
- 真值可取容量 2 玩家持有 `3S, 3H`，容量 1 玩家持有 `4C`；
- 对四个玩家-rank pair 手工核算 presence 与 copy 平方误差和。

## 十、真值隔离检查

必须确认：

- 只有测试和 `evaluation/marginal_metrics.py` 接触 `ground_truth_hands`；
- `agents/`、CLI、RAG 不导入新模块；
- 报告和 diagnostics 不保留真实手牌序列；
- 不新增逐样本真值 dump 或日志。

## 十一、验证命令

先运行：

```bash
python -m unittest tests.test_marginal_metrics tests.test_card_allocations tests.test_belief_metrics tests.test_ranking_metrics tests.test_card_ranker tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
```

再运行：

```bash
python -m unittest discover -q
git diff --check
```

并检查：

```bash
rg -n "marginal_metrics|ground_truth_hands" agents cli rag
```

预期 runtime 目录没有对新 evaluation 模块的导入。

## 十二、完成报告

报告必须包含：

- 修改文件；
- 报告 dataclass 和字段语义；
- 组合边际模型的解释边界；
- fail-closed 校验；
- Brier、copy 平方误差和校准桶的精确定义；
- 真值隔离检查结果；
- 定向和全量测试结果；
- `git diff --check` 结果；
- 明确说明尚未运行多种子校准、未生成 runtime 置信度、未接入策略，也未证明胜率提升。

## 十三、完成门槛

只有同时满足以下条件，Step J-D1c1 才能标记完成：

- 仅完整、一致的 J-D1b 进入评分；
- 所有玩家 × 正数 rank pair 均被计入；
- Brier 与 copy 平方误差使用精确有理数；
- 10 个校准桶边界确定且可精确聚合；
- 真值只进入 evaluation；
- 报告不泄露真值明细；
- invalid 输入完全零化；
- 全量测试通过；
- 没有修改 runtime、engine、benchmark 或 docs；
- 没有把组合边际描述为已校准置信度。
