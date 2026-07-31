# 下一步实施提示词

## 使用说明

本提示词交给负责源码和测试实现的代理。项目规划代理只维护 `docs/*.md`。

## 当前唯一任务

实现 Step J-C3a：固定种子的多局离线残局样本采集与 rank 消融指标聚合。

本轮只建立可重复的离线基准运行器。不要调整 J-C2b1 启发式权重，不要新增软信号、概率或置信度，不要接入 DeepSeek、RAG 或策略主链，也不要根据少量测试样本宣称策略提升。

## 提示词

```text
请在 GuanDan 项目中实现 Step J-C3a“多种子离线残局基准运行器”。

开始前必须阅读：

- AGENTS.md
- docs/PROJECT_STATUS.md
- docs/PLAN.md
- docs/BELIEF_STATE.md
- docs/TESTS.md
- engine/game.py
- engine/state.py
- engine/cards.py
- agents/base.py
- agents/rule_based_ai.py
- agents/game_phase.py
- agents/card_belief.py
- agents/card_constraints.py
- agents/card_allocations.py
- agents/card_signals.py
- agents/card_ranker.py
- evaluation/belief_metrics.py
- evaluation/ranking_metrics.py
- tests/test_game_flow.py
- tests/test_ranking_metrics.py

当前基线：

- 已提交基线为 `1dfc64d J-A`；
- Step J-B1 至 J-C2b2 已完成但当前尚未提交；
- J-C2b2 定向回归 120 项通过；
- 全量 `python -m unittest discover -q` 为 230 项通过；
- 当前唯一软信号是未校准的 `opponent_single_pass`；
- J-C2b2 只提供单样本消融，不能证明多样本改进。

本任务目标：

1. 用固定 seed 创建 `GuanDanGame`，使用现有 `RuleBasedAIAgent` 确定性推进对局；
2. 只在统一阶段为 `near_open_endgame` 或 `critical_endgame` 时采集当前玩家 observation；
3. 对每个样本依次运行 J-A、J-B1、J-B2、J-C2a、J-C2b1 和 J-C2b2；
4. 从离线引擎状态提取当前观察者之外、未完赛且剩余牌数大于 0 的真实手牌；
5. 将真实手牌只传给 `evaluation.ranking_metrics.evaluate_rank_ranking()`；
6. 聚合 overall、`near_open_endgame`、`critical_endgame` 三组 baseline/soft/delta；
7. 记录游戏、样本、无效输入、样本上限、步数上限和诊断计数；
8. 输出不可变、JSON 友好且不泄露逐样本真值的报告。

范围要求：

1. 新增 `evaluation/rank_benchmark.py`。
2. 新增 `tests/test_rank_benchmark.py`。
3. 如确有需要，只允许对 `evaluation/__init__.py` 做最小导出调整。
4. 不修改 `engine/`、`agents/`、CLI、RAG、DeepSeek 或 docs。
5. 不修改 J-A 至 J-C2b2 的现有契约和启发式参数默认值。
6. 不新增第三方依赖，不访问网络，不调用 DeepSeek。
7. 不写日志、JSON、缓存或其他运行产物到仓库。
8. 不实现 J-C3b 的正式批量结论、权重搜索、置信度校准或 Step K。

建议公开接口：

- frozen/slots dataclass `RankBenchmarkBucket`
- frozen/slots dataclass `RankBenchmarkReport`
- `aggregate_rank_reports(
      reports: Sequence[RankAblationReport],
      *,
      phase: str,
  ) -> RankBenchmarkBucket`
- `run_rank_benchmark(
      seeds: Sequence[int],
      *,
      current_level_rank: str = "2",
      max_steps: int = 5000,
      max_samples_per_game: int = 24,
      max_external_cards: int = 12,
      max_search_nodes: int = 1_000_000,
      max_solutions: int = 100_000,
  ) -> RankBenchmarkReport`

可以调整命名，但必须保留“纯聚合函数”和“真实对局采集函数”两层，便于分别测试计数聚合与引擎采集。

输入校验：

1. `seeds` 必须是非字符串 Sequence，且至少包含一个元素。
2. 每个 seed 必须是非 bool 的整数。
3. seed 不得重复，避免同一局被无意重复加权。
4. `current_level_rank` 必须符合引擎支持的级牌点数。
5. `max_steps`、`max_samples_per_game`、`max_external_cards`、`max_search_nodes`、`max_solutions` 都必须是非 bool 的正整数。
6. 参数无效时抛出明确 `ValueError`，不得静默修正。
7. 输入顺序必须保留；相同 seed 顺序和参数重复运行应得到完全相同的报告。

对局推进：

1. 每个 seed 创建独立 `GuanDanGame(seed=seed, current_level_rank=...)` 并调用 `reset()`。
2. 为 1 至 4 号玩家创建现有 `RuleBasedAIAgent`。
3. 每一步先调用 `game.observe()`，从公开 observation 计算统一阶段。
4. 动作选择只使用该 observation 和当前 `game.legal_actions()`。
5. `RuleBasedAIAgent` 返回的 action ID 必须通过现有合法 ID 校验，再传给 `game.step(action_id)`。
6. 不复制规则 AI 的排序逻辑，不自行构造动作。
7. 达到 `max_steps` 但对局未结束时停止该局，增加未完成局计数和规范化诊断 `max_steps_reached`。
8. 一个 observation 的稳定身份为 `(seed, step_no, observer_player_id)`，同一身份最多评估一次。

样本选择：

1. 只评估统一阶段恰好为 `near_open_endgame` 或 `critical_endgame` 的 observation。
2. 两个阶段按分类器最终结果互斥，不把 critical 样本重复计入 near-open 桶。
3. `eligible_sample_count` 记录目标阶段 observation 数。
4. 每局最多评估 `max_samples_per_game` 个目标阶段样本。
5. 超出每局上限的目标阶段 observation 不运行信念流水线，计入 `sample_limit_skipped_count`。
6. `evaluated_sample_count = valid_sample_count + invalid_sample_count`。
7. 不因某一阶段没有样本而伪造样本或复制另一阶段数据。

公开推断流水线：

对每个被评估 observation，严格按以下顺序：

1. `classify_game_phase(observation)`
2. `build_card_belief(observation, phase_context)`
3. `build_card_constraints(card_belief)`
4. `enumerate_card_allocations(...)`
5. `build_public_signal_state(observation, card_belief)`
6. `build_card_rankings(card_belief, constraints, allocation, signals)`
7. `evaluate_rank_ranking(card_belief, ranking, ground_truth_hands)`

J-A 至 J-C2b1 的构造过程只能读取 observation 或上一步公开输出。不得把真实手牌、`GameState`、`PlayerState` 或其他引擎内部对象传给 `agents/`。

离线真值边界：

1. 允许且仅允许 `evaluation/rank_benchmark.py` 为离线评测读取 `game._state`。
2. 不要修改 `engine/` 来新增真值接口。
3. 真值观察者必须等于当前 `state.current_player_id`。
4. 真值映射只包含观察者之外、未完赛且手牌非空的玩家。
5. 每张真实 Card 使用 `engine.cards.card_to_token()` 转换，不自行拼接 token。
6. 真值只作为 `evaluate_rank_ranking()` 的函数参数存在。
7. 不得把真值写入 observation、belief、constraints、allocation、signals 或 ranking。
8. `agents/`、CLI、RAG、DeepSeek 不得导入 `evaluation`。

聚合规则：

1. 只把 `valid_input=True` 的 `RankAblationReport` 纳入指标。
2. 无效报告增加 invalid 计数，其 diagnostics 进入频次统计，不做部分评分。
3. baseline 和 soft 分别累加以下原始计数：
   - player_count
   - truth_rank_count
   - candidate_covered_count
   - candidate_missed_count
   - top1_hit_count
   - top1_selected_count
   - top3_hit_count
   - top3_selected_count
4. 聚合后从累加计数重新计算 candidate recall、Top-1/Top-3 recall、precision 和 average selection size。
5. 禁止直接平均每个样本的 recall、precision 或 average selection size。
6. worst-case MRR 按每个样本的 `truth_rank_count` 加权：
   `sum(sample_mrr * sample_truth_rank_count) / sum(sample_truth_rank_count)`。
7. 有有效样本但聚合 `truth_rank_count=0` 时沿用 J-C2b2 的确定零分母语义；完全无有效样本的空桶所有比率为 0.0。
8. 所有 delta 必须从聚合后的 `soft - baseline` 重算，不能平均样本 delta。
9. `candidate_recall_delta` 必须保持为 0，若不为 0 应视为实现错误。
10. overall 由两个互斥阶段桶的有效原始计数合并得到，不能平均两个阶段指标。

诊断聚合：

1. 报告至少区分：
   - `max_steps_reached`
   - `sample_limit_reached`
   - `duplicate_sample`
   - J-C2b2 无效报告返回的诊断类别
2. 诊断频次按类别聚合；对 `category:detail` 只统计冒号前的 category，避免高基数和玩家明细泄露。
3. 同一样本内同一诊断类别最多计数一次。
4. 诊断只影响对应计数，不允许修改或补全推断结果。

RankBenchmarkBucket 至少包含：

- phase
- sample_count
- valid_sample_count
- invalid_sample_count
- baseline
- soft
- J-C2b2 同名 delta 字段
- diagnostic_counts

其中 baseline 和 soft 可以复用 `RankMetricSnapshot`，但必须重新构造聚合快照，不得修改单样本对象。

RankBenchmarkReport 至少包含：

- requested_game_count
- completed_game_count
- incomplete_game_count
- eligible_sample_count
- evaluated_sample_count
- valid_sample_count
- invalid_sample_count
- sample_limit_skipped_count
- overall
- by_phase
- diagnostic_counts

`by_phase` 必须稳定包含 `near_open_endgame` 和 `critical_endgame` 两个桶，即使其中一个为空。

报告安全：

1. 所有数据类使用 `@dataclass(frozen=True, slots=True)`。
2. 集合或映射字段不得暴露可变内部状态。
3. 每层提供 JSON 友好的 `to_dict()`。
4. `json.dumps(report.to_dict())` 必须成功。
5. 报告不得包含：
   - seed 值列表或逐 seed 结果
   - ground truth hands
   - 逐玩家真实 token 或 rank
   - 逐样本报告
   - 可逆推出某局隐藏手牌的明细
6. 允许输出聚合计数、比例、阶段名和规范化诊断频次。
7. 不得出现 NaN 或 Infinity。

测试要求：

`tests/test_rank_benchmark.py` 至少覆盖：

1. 空 seeds、字符串 seeds、bool/int 非法 seed 和重复 seed 被拒绝；
2. 非法级牌及所有非正/非整数上限被拒绝；
3. 固定 seed 和参数重复运行报告完全一致；
4. 规则 AI 选择始终来自当前合法动作；
5. 仅 near-open/critical observation 进入 eligible 计数；
6. critical 不重复进入 near-open 桶；
7. 每个 `(seed, step_no, observer)` 最多评估一次；
8. 每局样本上限正确增加 skipped 计数；
9. `max_steps` 正确记录未完成局和诊断；
10. 离线真值排除 self、已完赛和空手玩家，token 转换正确；
11. 真值不进入任一 `agents` 输入；
12. 有效与无效单样本报告分别计数；
13. 无效样本不进入指标；
14. 诊断 detail 按 category 去重聚合；
15. 不同分母样本证明 recall/precision 是微聚合而非样本均值；
16. average selection size 由总 selected / 总 player 重算；
17. MRR 按 truth rank 数加权；
18. overall 由两个阶段原始计数合并，不平均阶段比率；
19. 聚合 delta 等于聚合 soft 减 baseline；
20. candidate recall delta 恒为 0；
21. 空阶段桶稳定、全为有限数且不伪造样本；
22. `to_dict()` 可 JSON 序列化；
23. 报告不含 seed 列表、逐样本结果或真值 token/rank/hand 字段；
24. 所有输出不可变；
25. 固定合成报告的聚合不修改输入；
26. `agents/`、CLI、RAG、DeepSeek 没有新增对 `evaluation` 的反向导入。

测试中可以对纯聚合函数使用人工构造的 `RankAblationReport`，以精确验证不同分母、MRR 权重和空桶。真实对局采集至少使用一个固定 seed 做小规模集成测试；不要为单元测试运行大批种子。

兼容要求：

- `tests/test_ranking_metrics.py` 必须保持通过；
- `tests/test_card_ranker.py` 必须保持通过；
- `tests/test_card_signals.py` 必须保持通过；
- `tests/test_belief_metrics.py` 必须保持通过；
- `tests/test_card_allocations.py` 必须保持通过；
- `tests/test_card_constraints.py` 必须保持通过；
- `tests/test_card_belief.py` 必须保持通过；
- `tests/test_card_tracker.py` 必须保持通过；
- `tests/test_game_phase.py` 必须保持通过；
- 全量 unittest 必须无回归。

完成后运行：

python -m unittest tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q
git diff --check

最终报告必须包含：

- 修改文件；
- 离线真值隔离方式；
- 对局推进与样本选择规则；
- 聚合分母、MRR 权重和 delta 的定义；
- 有效、无效、跳过和步数上限的计数口径；
- diagnostics 聚合方式；
- 定向和全量测试数量；
- 未解决风险；
- 明确说明 J-C3a 只建立多种子离线基准能力，尚未运行正式基准、证明启发式改进、校准概率/置信度、接入策略或提升胜率。
```

## 完成判定

只有同时满足以下条件，Step J-C3a 才能标记完成：

- 固定种子对局可重复；
- 采集只发生在两个指定残局阶段；
- runtime 推断流水线只消费公开 observation；
- 真值访问严格限制在 `evaluation/`；
- baseline/soft 采用原始计数微聚合；
- MRR 按真实 rank 数加权；
- overall 不直接平均阶段比率；
- 无效样本不参与指标；
- 报告不泄露逐样本或逐玩家真值；
- 未修改现有软启发式和主决策链；
- 现有 230 项测试无回归；
- 实施代理向项目规划代理报告实际测试结果。
