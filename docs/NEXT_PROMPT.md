# 下一步实施提示词

## 使用说明

本提示词交给负责执行评测的代理。项目规划代理只维护 `docs/*.md`。

## 当前唯一任务

执行 Step J-C3c2：在独立固定 seed 上，对 forced-only 与 25%/50%/100% 战略 pass 策略运行两次完整 rank 基准，并按预注册的 Top-K recall 护栏给出唯一判定。

本轮不修改代码、不调权重、不筛选 seed，也不因 MRR 改善忽略真实 rank 召回损失。

## 提示词

```text
请在 GuanDan 项目中执行 Step J-C3c2“战略性 pass 策略分布正式验收”。

开始前阅读：

- AGENTS.md
- docs/PROJECT_STATUS.md
- docs/PLAN.md
- docs/BELIEF_STATE.md
- docs/TESTS.md
- evaluation/pass_policy_benchmark.py
- evaluation/rank_benchmark.py
- evaluation/ranking_metrics.py
- agents/card_ranker.py
- agents/rule_based_ai.py
- tests/test_pass_policy_benchmark.py
- tests/test_rank_benchmark.py

当前状态：

- 已提交基线为 `49ef31e J-C3b`；
- Step J-C3c1 已实现并通过 140 项定向、250 项全量测试；
- J-C3c1 尚未形成可追溯提交时不得开始正式基准；
- J-C3b seed 1000..1199 只覆盖 RuleBasedAI 被迫 pass；
- seed 20..29 已用于 J-C3c1 开发容量试跑，禁止进入正式结论；
- 开发试跑显示 25% 战略 pass 下 overall Top-3 recall delta 约为 -0.126899；
- 该开发结果只用于预注册召回护栏，不能替代本轮独立 holdout。

范围：

1. 不修改、创建、删除、格式化或提交任何文件。
2. 不修改启发式、gate、pass rate、测试、docs、配置或依赖。
3. 不访问网络，不调用 DeepSeek。
4. 不写 JSON、日志、缓存或临时结果到仓库。
5. 不运行权重搜索，不替换或追加 seed。
6. 不实现 J-C3d、策略主链或 Step K。

前置检查：

1. 运行 `git status --short`。
2. 确认以下文件均已被 Git 跟踪并包含在 HEAD：
   - `evaluation/rank_benchmark.py`
   - `evaluation/pass_policy_benchmark.py`
   - `tests/test_pass_policy_benchmark.py`
3. 记录 `git rev-parse HEAD`。
4. 工作区必须干净。
5. 如果 J-C3c1 未提交或工作区不干净：
   - 停止正式基准；
   - 不要 stash、还原、提交或清理；
   - 报告 `precondition_failed`；
   - 不输出策略信号判定。

回归检查：

python -m unittest tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q

任何测试失败时停止，判定为 `benchmark_invalid`。

正式参数一次性锁定：

- seeds：`tuple(range(2000, 2100))`
- requested games per policy：100
- strategic pass rates：`(0, 25, 50, 100)`
- policy names：
  - `forced_only`
  - `strategic_pass_25`
  - `strategic_pass_50`
  - `strategic_pass_100`
- `current_level_rank="2"`
- `max_steps=5000`
- `max_samples_per_game=512`
- `max_external_cards=12`
- `max_search_nodes=1_000_000`
- `max_solutions=100_000`

不得修改、筛选、重排或补充 seed/rate。每个策略必须使用完全相同的输入参数。

运行要求：

1. 在同一个 Python 进程内，用上述参数调用
   `run_pass_policy_benchmark()` 两次。
2. 分别记录两次耗时，耗时不进入 hash。
3. 断言两个 `PassPolicyBenchmarkReport` 完全相等。
4. 对每次 `report.to_dict()` 使用 canonical JSON：

   `json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)`

5. 对 canonical JSON UTF-8 字节计算 SHA-256。
6. 两次 SHA-256 必须完全一致。
7. 只在标准输出打印：
   - 两次耗时；
   - 两次 SHA-256；
   - 第二次报告的格式化聚合 JSON。
8. 不把结果重定向到仓库文件。

数据完整性门槛：

以下任一条件不满足，唯一判定为 `benchmark_invalid`：

1. 两次完整报告不相等；
2. 两次 SHA-256 不一致；
3. `requested_policy_count != 4`；
4. by_policy 名称或顺序与锁定策略不一致；
5. 任一策略 `requested_game_count != 100`；
6. 任一策略 `completed_game_count != 100`；
7. 任一策略 `incomplete_game_count != 0`；
8. 任一策略 `eligible != evaluated`；
9. 任一策略 `evaluated != valid`；
10. 任一策略 `invalid != 0`；
11. 任一策略 `sample_limit_skipped_count != 0`；
12. 任一策略顶层或阶段 diagnostics 非空；
13. 任一策略 near-open 有效样本少于 500；
14. 任一策略 critical 有效样本少于 500；
15. 报告存在 NaN、Infinity 或不可 JSON 序列化值。

策略行为完整性：

以下任一条件不满足，判定为 `benchmark_invalid`：

1. 每个策略 `strategic_pass_opportunity_count > 0`；
2. forced-only `strategic_pass_count == 0`；
3. strategic-pass-25 满足
   `0 < pass_count < opportunity_count`；
4. strategic-pass-50 满足
   `0 < pass_count < opportunity_count`；
5. strategic-pass-100 满足
   `pass_count == opportunity_count`；
6. 所有策略都满足
   `0 <= pass_count <= opportunity_count`。

不同策略会改变后续轨迹，因此不要求机会数相同，也不要求 25%/50%
的实际 pass 比例精确等于名义 rate。

硬候选安全门槛：

对四个策略的 overall、near-open、critical 分别要求：

1. baseline candidate recall 为 1.0；
2. soft candidate recall 为 1.0；
3. candidate recall delta 为 0.0。

允许绝对浮点误差 `1e-12`。任一不满足判定为
`benchmark_invalid`，因为软信号不应改变硬候选覆盖。

forced-only 复验门槛：

forced-only 必须同时满足：

1. 三个桶 Top-1 recall delta 均不小于 `-1e-12`；
2. 三个桶 Top-3 recall delta 均不小于 `-1e-12`；
3. overall Top-1 precision delta 至少 `0.002`；
4. overall Top-3 precision delta 至少 `0.002`；
5. overall worst-case MRR delta 至少 `0.001`；
6. near-open/critical 的 Top-1 precision delta 均大于 0；
7. near-open/critical 的 Top-3 precision delta 均大于 0；
8. near-open/critical 的 MRR delta 均大于 0。

forced-only 未通过时，判定为 `reject_unconditioned_pass_signal`。

战略 pass recall 护栏：

分别对 strategic-pass-25、50、100 的 overall、near-open、critical
检查：

1. Top-1 recall delta 不得低于 `-0.03`；
2. Top-3 recall delta 不得低于 `-0.02`；
3. Top-1 precision delta 不得低于 `-0.002`；
4. Top-3 precision delta 不得低于 `-0.002`。

MRR 和 average selection size 仍需完整报告，但不能抵消上述任一护栏失败。

唯一判定顺序：

1. 前置、测试、可重复性、数据完整性、策略行为或硬候选安全失败：
   `benchmark_invalid`
2. forced-only 复验失败：
   `reject_unconditioned_pass_signal`
3. strategic-pass-25 任一桶任一 recall/precision 护栏失败：
   `reject_unconditioned_pass_signal`
4. strategic-pass-25 全部通过，但 50 或 100 任一护栏失败：
   `retain_with_policy_conditioning`
5. forced-only 和 25/50/100 全部通过：
   `retain_for_confidence_calibration`

不得新增第五种结论，不得因 MRR 为正而覆盖 Top-K recall 失败。

结论含义：

- `reject_unconditioned_pass_signal`：
  当前把 enemy-single pass 无条件作为负向持牌信号的方式不能进入置信度校准或 runtime；下一步应重新设计为策略条件化证据，或撤销该软扣分。
- `retain_with_policy_conditioning`：
  低主动 pass 压力可接受，但必须先建立对手 pass 倾向或上下文条件，不能直接校准当前无条件信号。
- `retain_for_confidence_calibration`：
  只允许进入 J-C3d 离线校准，仍不代表可接入策略或提升胜率。

最终报告必须包含：

1. 前置检查结果与 HEAD SHA；
2. 两条测试命令及 140/250 结果；
3. 正式参数；
4. 两次运行耗时和 SHA-256；
5. 每个策略的 opportunity/pass count 和实际比例；
6. 每个策略的 requested/completed/incomplete；
7. 每个策略的 eligible/evaluated/valid/invalid/skipped；
8. 每个策略的 diagnostics；
9. 每个策略 overall、near-open、critical 的：
   - sample count
   - baseline/soft candidate recall
   - baseline/soft Top-1 recall、precision、average selection size
   - baseline/soft Top-3 recall、precision、average selection size
   - baseline/soft worst-case MRR
   - 全部 delta
10. 对每条完整性、forced-only 和战略 pass 护栏逐项给出 pass/fail；
11. 最终唯一判定；
12. 未解决风险；
13. 运行前后 `git status --short` 一致且本任务未修改文件。
```

## 完成判定

Step J-C3c2 只有在以下条件满足时才算执行完成：

- J-C3c1 已提交且工作区干净；
- 140/250 回归通过；
- 4 个策略各 100 局完整运行两次；
- 两次报告和 SHA-256 一致；
- 未更改 seed、rate、gate 或其他参数；
- Top-K recall 护栏优先于 MRR；
- 按顺序给出唯一判定；
- 没有修改任何文件；
- 没有把离线策略分布结果表述为置信度、策略集成或胜率提升。
