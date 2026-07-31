# 下一步实施提示词

## 使用说明

本提示词交给负责执行评测的代理。项目规划代理只维护 `docs/*.md`。

## 当前唯一任务

执行 Step J-C3b：在预注册参数和独立固定种子上运行两次完整 RuleBasedAI 离线基准，并按预先锁定的门槛给出唯一判定。

本轮是数据验收，不是代码实现。不得修改任何文件，不得调参，不得根据结果替换种子，也不得接入策略主链。

## 提示词

```text
请在 GuanDan 项目中执行 Step J-C3b“预注册 RuleBasedAI 正式 rank 基准”。

开始前阅读：

- AGENTS.md
- docs/PROJECT_STATUS.md
- docs/PLAN.md
- docs/BELIEF_STATE.md
- docs/TESTS.md
- evaluation/rank_benchmark.py
- evaluation/ranking_metrics.py
- agents/card_ranker.py
- agents/rule_based_ai.py
- tests/test_rank_benchmark.py
- tests/test_ranking_metrics.py

当前状态：

- Git 检查点 `4950538 J-B1 至 J-C2b2` 已存在；
- Step J-C3a 已实现并通过 130 项定向、240 项全量测试；
- J-C3a 当前尚未形成新的可追溯提交时，不得开始正式基准；
- seed 0..19 已用于开发容量试跑，禁止用于本轮正式结论；
- 开发试跑证明默认每局 24 样本会明显截断，因此本轮锁定每局上限 512；
- 当前唯一软信号是 `opponent_single_pass`；
- 本轮结论只适用于 RuleBasedAI 轨迹。

范围：

1. 不修改、创建、删除、格式化或提交任何文件。
2. 不修改启发式、参数默认值、测试、docs、配置或依赖。
3. 不访问网络，不调用 DeepSeek。
4. 不写 JSON、日志、缓存或临时结果到仓库。
5. 不运行权重搜索，不试验其他 seed 区间。
6. 不实现 J-C3c/J-C3d 或 Step K。

前置检查：

1. 运行 `git status --short`。
2. 确认 `evaluation/rank_benchmark.py` 和 `tests/test_rank_benchmark.py` 已被 Git 跟踪且包含在 HEAD。
3. 记录 `git rev-parse HEAD`。
4. 工作区必须干净。
5. 如果 J-C3a 文件未提交或工作区不干净：
   - 停止正式基准；
   - 不要 stash、还原、提交或清理；
   - 报告 `precondition_failed` 及具体状态；
   - 不输出启发式判定。

回归检查：

python -m unittest tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q

任何测试失败时停止，不运行正式基准，判定为 `benchmark_invalid`。

正式参数一次性锁定为：

- seeds：`tuple(range(1000, 1200))`
- requested games：200
- `current_level_rank="2"`
- `max_steps=5000`
- `max_samples_per_game=512`
- `max_external_cards=12`
- `max_search_nodes=1_000_000`
- `max_solutions=100_000`

不得修改、筛选、重排或补充 seed。不得因为结果不理想而重跑其他参数。

运行要求：

1. 在同一个 Python 进程内，用上述完全相同参数调用 `run_rank_benchmark()` 两次。
2. 分别记录两次耗时，耗时不进入结果 hash。
3. 断言两个 `RankBenchmarkReport` 完全相等。
4. 对每次 `report.to_dict()` 使用以下 canonical JSON：

   `json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)`

5. 对 canonical JSON 的 UTF-8 字节计算 SHA-256。
6. 两次 SHA-256 必须完全一致。
7. 只在标准输出打印：
   - 两次耗时；
   - 两次 SHA-256；
   - 第二次报告的格式化聚合 JSON。
8. 不将结果重定向到仓库文件。

建议使用标准库 `time`、`json`、`hashlib` 和
`evaluation.rank_benchmark.run_rank_benchmark` 完成，不新增脚本文件。

数据完整性门槛：

以下任一条件不满足，唯一判定为 `benchmark_invalid`：

1. 两次报告不完全相等；
2. 两次 SHA-256 不一致；
3. `requested_game_count != 200`；
4. `completed_game_count != 200`；
5. `incomplete_game_count != 0`；
6. `eligible_sample_count != evaluated_sample_count`；
7. `evaluated_sample_count != valid_sample_count`；
8. `invalid_sample_count != 0`；
9. `sample_limit_skipped_count != 0`；
10. 顶层 `diagnostic_counts` 非空；
11. overall 或任一阶段桶存在 invalid 样本；
12. `near_open_endgame.valid_sample_count < 1000`；
13. `critical_endgame.valid_sample_count < 1000`；
14. 报告存在 NaN、Infinity 或不可 JSON 序列化值。

硬候选安全门槛：

数据完整性通过后，以下任一条件不满足，判定为
`reject_on_locked_corpus`：

1. overall、near-open、critical 的 baseline candidate recall 均为 1.0；
2. overall、near-open、critical 的 soft candidate recall 均为 1.0；
3. 三个桶的 `candidate_recall_delta` 均为 0.0。

浮点零比较允许绝对误差 `1e-12`。

软排序保留门槛：

只有以下条件全部满足，才判定为
`retain_for_policy_diverse_validation`：

1. overall、near-open、critical 的 Top-1 recall delta 均不小于 `-1e-12`；
2. overall、near-open、critical 的 Top-3 recall delta 均不小于 `-1e-12`；
3. overall Top-1 precision delta 至少为 `0.002`；
4. overall Top-3 precision delta 至少为 `0.002`；
5. overall worst-case MRR delta 至少为 `0.001`；
6. near-open 和 critical 的 Top-1 precision delta 均大于 0；
7. near-open 和 critical 的 Top-3 precision delta 均大于 0；
8. near-open 和 critical 的 worst-case MRR delta 均大于 0；
9. 三个桶的 Top-1 average selection size delta 均不大于 `1e-12`；
10. 三个桶的 Top-3 average selection size delta 均不大于 `1e-12`。

数据完整性通过但任一硬候选或软排序门槛不满足时，判定为
`reject_on_locked_corpus`。不得在同一 seed 集上调权重后重新申报通过。

结论边界：

- `retain_for_policy_diverse_validation` 只表示保留该信号进入 J-C3c；
- 不表示概率或置信度已校准；
- 不表示可接入 DeepSeek、RAG 或策略主链；
- 不表示真实玩家、DeepSeek 或其他策略下仍有效；
- 不表示动作质量或胜率提升。

原因是现有 RuleBasedAIAgent 只在不存在非 pass 合法动作时 pass，
没有覆盖“有牌可压但战略性 pass”的策略分布。

最终报告必须包含：

1. 前置检查结果和 HEAD SHA；
2. 实际执行的两条测试命令及 130/240 测试结果；
3. 正式参数；
4. 两次运行耗时和 SHA-256；
5. requested/completed/incomplete 数；
6. eligible/evaluated/valid/invalid/skipped 数；
7. diagnostics；
8. overall、near-open、critical 各自的：
   - sample count
   - baseline/soft candidate recall
   - baseline/soft Top-1 recall、precision、average selection size
   - baseline/soft Top-3 recall、precision、average selection size
   - baseline/soft worst-case MRR
   - 全部 delta
9. 对每条数据完整性、硬候选和软排序门槛逐项给出 pass/fail；
10. 最终唯一判定：
    - `benchmark_invalid`
    - `reject_on_locked_corpus`
    - `retain_for_policy_diverse_validation`
11. 未解决风险；
12. 运行前后 `git status --short` 一致，且本任务未修改文件。
```

## 完成判定

Step J-C3b 只有在以下条件满足时才算执行完成：

- J-C3a 已提交且工作区干净；
- 130/240 回归通过；
- 锁定的 200 个 seed 完整运行两次；
- 两次报告与 SHA-256 一致；
- 未更改参数或筛选样本；
- 按预注册门槛给出唯一判定；
- 没有修改任何文件；
- 没有把 RuleBasedAI 结论表述为策略集成、置信度或胜率提升。
