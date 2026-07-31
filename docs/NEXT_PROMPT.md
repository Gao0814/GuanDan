# 下一步实施提示词

## Step J-D1c2b：固定 seed 边际采集器与开发容量试验

请在 GuanDan 项目中实现 Step J-D1c2b。目标是用确定性规则 AI 对局采集 `critical_endgame` 的完整 J-D1b 边际报告，按外部未知牌数量分桶，并交给 J-D1c2a 做精确聚合。

本步骤使用开发 seed 测量采集完成率、有效样本量、截断情况、可重复性和运行成本，不形成正式校准结论。

## 一、开始前检查

先阅读：

- `evaluation/marginal_metrics.py`
- `evaluation/marginal_benchmark.py`
- `evaluation/rank_benchmark.py`
- `evaluation/pass_policy_benchmark.py`
- `tests/test_marginal_metrics.py`
- `tests/test_marginal_benchmark.py`
- `tests/test_rank_benchmark.py`
- `agents/game_phase.py`
- `docs/PROJECT_STATUS.md`

确认当前契约：

- J-D1b 只有完整分配才输出物理分母和 rank 边际；
- J-D1c1 只接受完整、一致的 allocation 与显式 truth；
- J-D1c2a 只消费 `MarginalEvaluationReport` 序列并精确微聚合；
- `critical_endgame` 的外部未知牌上限为 12；
- `near_open_endgame` 的 13..20 张默认超出 J-D1b 精确枚举上限，不能混入当前校准样本。

开始前运行：

```bash
python -m unittest tests.test_marginal_benchmark tests.test_marginal_metrics tests.test_card_allocations tests.test_belief_metrics tests.test_ranking_metrics tests.test_card_ranker tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q
```

当前独立复核基线为定向 166 项、全量 290 项通过。若结果不同，先报告实际状态，不要覆盖不明改动。

## 二、允许修改范围

允许：

- 新增 `evaluation/benchmark_truth.py`
- 新增 `evaluation/marginal_corpus.py`
- 新增 `tests/test_marginal_corpus.py`
- 最小修改 `evaluation/rank_benchmark.py`，改用共享 truth helper
- 如保持旧私有 helper 兼容需要，可最小修改 `tests/test_rank_benchmark.py`

不要修改：

- `engine/`
- `agents/`
- J-A/J-B/J-D1a/J-D1b
- `evaluation/marginal_metrics.py`
- `evaluation/marginal_benchmark.py`
- ranking/pass-policy 指标与策略语义
- RAG、DeepSeek、CLI
- docs
- 依赖配置

不要新增第三方依赖。

## 三、共享 truth helper

把现有 `evaluation/rank_benchmark.py` 中读取 `game._state` 的逻辑移动到：

```python
evaluation/benchmark_truth.py
```

建议公开函数：

```python
extract_ground_truth_hands(
    game: GuanDanGame,
    observer_player_id: object,
) -> dict[object, tuple[str, ...]]
```

要求：

- 该文件成为 evaluation 中唯一直接读取 `game._state` 的位置；
- 只允许在公开推断对象已经构建完成后调用；
- observer 必须与当前玩家一致，否则抛出 `ValueError`；
- 只返回未完赛、非 observer 且仍有手牌的玩家；
- 使用 `card_to_token()`；
- 不缓存、不记录、不序列化 truth；
- rank benchmark 默认行为和历史报告结构完全不变。

为避免破坏既有测试或外部调用，可以在 `rank_benchmark.py` 保留：

```python
_ground_truth_hands_from_state = extract_ground_truth_hands
```

不要保留第二份 `_state` 读取实现。

## 四、采集器公开接口

在 `evaluation/marginal_corpus.py` 中实现：

```python
run_marginal_corpus(
    seeds: Sequence[int],
    *,
    current_level_rank: str = "2",
    max_steps: int = 5000,
    max_samples_per_game: int = 128,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
    agent_factory: Callable[[int, int], BaseAgent] | None = None,
) -> MarginalCorpusReport
```

默认 agent 为每局、每位玩家新建的 `RuleBasedAIAgent`。

## 五、目标样本

只在统一阶段为：

```text
critical_endgame
```

时记为 eligible。

不要采集：

- `near_open_endgame`
- `endgame`
- `midgame`
- `opening`

原因：当前精确分配默认只覆盖外部未知牌不超过 12 张；near-open 的 13..20 张不是完整物理边际样本。

每个 eligible observation 的公开外部未知牌数必须位于 0..12，否则记录 `unexpected_external_count` 并跳过评分。

## 六、公开推断与真值顺序

每个被评估样本严格按以下顺序：

```text
classify_game_phase(observation)
  -> build_card_belief(observation, phase_context)
  -> build_card_constraints(card_belief)
  -> enumerate_card_allocations(...)
  -> extract_ground_truth_hands(game, observer_player_id)
  -> evaluate_rank_marginals(card_belief, allocation, truth)
```

要求：

- truth 提取必须发生在所有 public-only 推断完成后；
- truth 只短暂传给 `evaluate_rank_marginals()`；
- truth 不进入 belief、constraints、allocation、agent 或 report；
- 不运行 `card_signals`、`card_ranker` 或 ranking metrics；
- 不用 truth 决定是否采样或调整搜索参数。

## 七、对局推进

沿用现有 rank benchmark 契约：

- 每个 seed 创建独立 `GuanDanGame`；
- 每个 `(seed, player_id)` 只调用一次 factory；
- agent 只读取 observation 与 legal actions；
- 所有返回值经过 `require_legal_action_id()`；
- 每局最多 `max_steps`；
- game over 计入 completed，否则计入 incomplete 和 `max_steps_reached`；
- 不复用 game、agent 或计数器。

factory 返回非法 agent 或 action 时保持显式失败，不静默替换。

## 八、样本去重与上限

样本 ID：

```python
(seed, step_no, observer_player_id)
```

要求：

- 全运行去重；
- 重复时记录 `duplicate_sample`，不重复评分；
- 每局达到 `max_samples_per_game` 后继续推进游戏，但不再评分；
- 每个被上限跳过的 observation 增加 `sample_limit_skipped_count`；
- 每局首次触发上限时记录一次 `sample_limit_reached`；
- eligible、evaluated、skipped 的关系可审计。

## 九、外部未知牌分桶

使用互斥、完整的三个固定桶：

```text
external_0_4
external_5_8
external_9_12
```

按 `GamePhaseContext.external_unknown_count` 分桶。

要求：

- 每个 evaluated report 恰好进入一个桶；
- 三个桶的 sample/valid/invalid/pair 原始总数与 overall 一致；
- overall 必须直接聚合全部单样本报告；
- 不通过平均三个桶的派生指标构造 overall；
- mapping key 和输出顺序固定为上述顺序。

## 十、报告结构

定义冻结、slots：

```python
MarginalCorpusReport
```

至少包含：

```python
requested_game_count: int
completed_game_count: int
incomplete_game_count: int
eligible_sample_count: int
evaluated_sample_count: int
valid_sample_count: int
invalid_sample_count: int
sample_limit_skipped_count: int
overall: MarginalBenchmarkBucket
by_external_count: Mapping[str, MarginalBenchmarkBucket]
diagnostic_counts: Mapping[str, int]
```

要求：

- `overall = aggregate_marginal_reports(all_reports, phase="overall")`；
- 每个外部牌数桶使用原始报告调用聚合器；
- 桶值的 phase 可保持 `critical_endgame`，mapping key 表达外部牌区间；
- top-level valid/invalid 与 overall 一致；
- top-level diagnostics 由 runtime diagnostics 与 overall invalid diagnostics 合并；
- 不重复累加 external bucket 中已经进入 overall 的 invalid diagnostics；
- diagnostics 按类别规范化并使用不可变稳定排序 mapping；
- `to_dict()` JSON 友好；
- 不含 seed、sample ID、逐样本报告、observation、玩家、rank、token 或 truth。

## 十一、输入校验

启动任何游戏前验证：

- seeds 是非空、无重复、非 bool 整数 Sequence；
- `current_level_rank` 是引擎支持的普通 rank；
- `max_steps`、`max_samples_per_game`、`max_external_cards`、`max_search_nodes`、`max_solutions` 为非 bool 正整数；
- `max_external_cards <= 12`；
- `agent_factory` 为 `None` 或 callable。

非法配置抛出 `ValueError`，不得返回部分报告。

## 十二、计数不变量

每份完整报告满足：

```text
requested_game_count
  == completed_game_count + incomplete_game_count

evaluated_sample_count
  == valid_sample_count + invalid_sample_count

overall.sample_count
  == evaluated_sample_count

overall.valid_sample_count
  == valid_sample_count

overall.invalid_sample_count
  == invalid_sample_count

sum(external bucket sample_count)
  == evaluated_sample_count

eligible_sample_count
  == evaluated_sample_count
     + sample_limit_skipped_count
     + duplicate/unexpected skips
```

如最后一项存在额外跳过原因，应有独立计数或 diagnostics，不能静默丢样本。

## 十三、确定性与安全

同一参数运行两次必须：

- `MarginalCorpusReport` 完全相等；
- `to_dict()` 完全相等；
- canonical JSON SHA-256 相等；
- 不含 NaN/Infinity；
- 不依赖 Python `hash()`、时间或全局随机状态。

报告不得保留：

- seed 列表；
- 逐局/逐样本结果；
- observation/history；
- 玩家级预测；
- ground truth hand/token/rank 明细。

## 十四、最低测试覆盖

在 `tests/test_marginal_corpus.py` 至少覆盖：

1. 固定单 seed 重复运行报告相等；
2. 多 seed 的 requested/completed/incomplete 计数；
3. 只采集 `critical_endgame`；
4. near-open 不进入 eligible；
5. 外部 0/4/5/8/9/12 的桶边界；
6. 三个外部桶互斥且覆盖 overall；
7. overall 由原始报告聚合；
8. top-level valid/invalid 与 overall 一致；
9. 默认 RuleBasedAI 可完成对局；
10. factory 每个 seed/player 只调用一次；
11. factory agent action 仍经过合法 ID 校验；
12. 每局样本上限与 skipped count；
13. `sample_limit_reached` 每局最多计一次；
14. max steps 产生 incomplete 和 diagnostic；
15. duplicate sample 不重复评分；
16. unexpected external count 有诊断且不评分；
17. allocation invalid/truncated 进入 invalid report，不污染指标；
18. runtime diagnostics 与 overall invalid diagnostics 合并但不重复 bucket；
19. seeds 空、重复、bool、非整数拒绝；
20. level rank 非法拒绝；
21. 所有数值上限的 0、负数、bool 拒绝；
22. `max_external_cards > 12` 拒绝；
23. 非 callable factory 拒绝；
24. report/dataclass/mapping 不可变；
25. `to_dict()` 可由 `json.dumps(..., allow_nan=False)` 序列化；
26. payload 不包含 seed、sample、observation、player、truth、token、rank 明细；
27. truth helper observer 不一致时失败；
28. truth helper 只返回活跃外部玩家；
29. rank benchmark 继续使用共享 helper，默认报告契约无变化；
30. evaluation 中只有 `benchmark_truth.py` 直接读取 `game._state`。

测试应优先使用小 seed、mock 或低成本 fixture，不要让全量单测运行正式 corpus。

## 十五、开发容量试验

实现和全量测试通过后，运行两次完全相同的开发试验：

```text
seeds = 40..59
games = 20
current_level_rank = 2
max_steps = 5000
max_samples_per_game = 128
max_external_cards = 12
max_search_nodes = 1,000,000
max_solutions = 100,000
default RuleBasedAIAgent
```

必须记录：

- 两次运行耗时；
- 两份报告是否完全相等；
- canonical JSON SHA-256；
- requested/completed/incomplete；
- eligible/evaluated/valid/invalid/skipped；
- 三个外部牌数桶的 sample、valid、invalid、rank pair；
- overall Brier mean、copy MSE、ECE、MCE、certainty error rate；
- diagnostics。

开发试验只回答：

- 20 局是否能完成；
- 128 样本上限是否足够；
- 搜索是否经常截断；
- 三个外部牌数桶是否有样本；
- 运行成本是否适合正式语料。

不要根据该开发 seed：

- 宣称模型已校准；
- 设定 runtime confidence；
- 调整概率；
- 筛选有利样本；
- 接入策略。

如果两次报告或 hash 不一致，Step J-D1c2b 不得标记完成。

## 十六、验证命令

先运行：

```bash
python -m unittest tests.test_marginal_corpus tests.test_marginal_benchmark tests.test_marginal_metrics tests.test_rank_benchmark tests.test_card_allocations tests.test_belief_metrics tests.test_ranking_metrics tests.test_card_ranker tests.test_pass_policy_benchmark tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
```

再运行：

```bash
python -m unittest discover -q
git diff --check
```

检查 `_state` 和真值边界：

```bash
rg -n "game\\._state|ground_truth_hands|extract_ground_truth_hands" evaluation agents cli rag
```

预期：

- 只有 `evaluation/benchmark_truth.py` 直接读取 `game._state`；
- runtime 不导入 evaluation；
- corpus report 不保存 truth。

## 十七、完成报告

报告必须包含：

- 修改文件；
- 共享 truth helper 与兼容方式；
- 采集阶段、外部牌数桶和样本 ID；
- 对局、样本、diagnostics 计数；
- truth 提取顺序和隔离；
- 单元测试与 `git diff --check`；
- 开发试验双运行耗时、hash、完整计数和聚合指标；
- 明确判定 `development_capacity_verified` 或说明失败原因；
- 明确说明开发结果不是正式校准、没有 runtime 置信度、没有策略接入或胜率结论。

## 十八、完成门槛

只有同时满足以下条件，Step J-D1c2b 才能标记完成：

- collector 只采集 critical exact-allocation 目标；
- truth 只在 public inference 后短暂进入 evaluation；
- overall 与外部牌数桶由原始报告精确聚合；
- 计数、去重、上限和 diagnostics 可审计；
- 同参数双运行报告及 hash 完全一致；
- 开发运行完成且容量风险已报告；
- 全量测试通过；
- runtime/engine/策略语义未修改；
- 未把开发试跑解释为正式校准。
