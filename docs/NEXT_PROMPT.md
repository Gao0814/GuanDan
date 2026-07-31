# 下一步实施提示词

## 使用说明

本提示词交给负责执行评测的代理。项目规划代理只维护 `docs/*.md`。

## 当前唯一任务

执行 Step J-C3d2：用独立固定 seed 对 hard-only neutral ranker 做四策略双运行封板，证明撤销后不再因 pass 策略分布产生任何排序差异。

本轮只运行已有评测器，不修改文件，不研究新信号。

## 提示词

```text
请在 GuanDan 项目中执行 Step J-C3d2“neutral rank baseline 正式封板”。

开始前阅读：

- AGENTS.md
- docs/PROJECT_STATUS.md
- docs/PLAN.md
- docs/BELIEF_STATE.md
- docs/TESTS.md
- agents/card_ranker.py
- evaluation/ranking_metrics.py
- evaluation/rank_benchmark.py
- evaluation/pass_policy_benchmark.py
- tests/test_card_ranker.py
- tests/test_rank_benchmark.py
- tests/test_pass_policy_benchmark.py

当前状态：

- 已提交基线为 `9a44c07 J-C3c2`；
- J-C3d1 已删除 `opponent_single_pass` 评分路径和两个 penalty 参数；
- J-C3d1 定向 140 项、全量 250 项测试通过；
- J-C3d1 尚未形成可追溯提交时不得开始正式封板；
- seed 30..34 已用于开发试跑，禁止进入本轮正式结论；
- 开发试跑中四种策略的全部 overall delta 均严格为 0。

范围：

1. 不修改、创建、删除、格式化或提交任何文件。
2. 不修改 ranker、benchmark、gate、rate、测试、docs 或配置。
3. 不访问网络，不调用 DeepSeek。
4. 不写 JSON、日志、缓存或临时结果到仓库。
5. 不研究新概率、新 evidence、置信度或策略路由。
6. 不使用 J-C3b/J-C3c2 或开发试跑 seed 替代本轮 holdout。

前置检查：

1. 运行 `git status --short`。
2. 确认以下文件已被 Git 跟踪并包含在 HEAD：
   - `agents/card_ranker.py`
   - `evaluation/rank_benchmark.py`
   - `evaluation/pass_policy_benchmark.py`
   - `tests/test_card_ranker.py`
3. 记录 `git rev-parse HEAD`。
4. 工作区必须干净。
5. 如果 J-C3d1 未提交或工作区不干净：
   - 停止；
   - 不要 stash、还原、提交或清理；
   - 报告 `precondition_failed`；
   - 不输出 neutral 判定。

回归检查：

python -m unittest tests.test_card_ranker tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q

任何测试失败时停止，判定为 `benchmark_invalid`。

正式参数锁定：

- seeds：`tuple(range(3000, 3050))`
- requested games per policy：50
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

不得修改、筛选、重排或补充 seed/rate。

运行要求：

1. 在同一个 Python 进程内，用锁定参数调用
   `run_pass_policy_benchmark()` 两次。
2. 记录两次耗时，耗时不进入 hash。
3. 断言两个 `PassPolicyBenchmarkReport` 完全相等。
4. canonical JSON 定义为：

   `json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)`

5. 对 canonical JSON UTF-8 字节计算 SHA-256。
6. 两次 SHA-256 必须完全一致。
7. 只向标准输出打印耗时、SHA-256 和第二次聚合 JSON。
8. 不将输出重定向到仓库文件。

数据完整性门槛：

以下任一不满足，唯一判定为 `benchmark_invalid`：

1. 两次报告不相等；
2. 两次 SHA-256 不一致；
3. `requested_policy_count != 4`；
4. 策略名称或顺序不符合锁定集合；
5. 任一策略 requested/completed/incomplete 不是 `50/50/0`；
6. 任一策略 `eligible != evaluated`；
7. 任一策略 `evaluated != valid`；
8. 任一策略 invalid 不为 0；
9. 任一策略 skipped 不为 0；
10. 任一策略顶层或阶段 diagnostics 非空；
11. 任一策略 near-open 有效样本少于 500；
12. 任一策略 critical 有效样本少于 500；
13. 报告存在 NaN、Infinity 或不可 JSON 序列化值。

策略行为完整性：

以下任一不满足，判定为 `benchmark_invalid`：

1. 每个策略 opportunity count 大于 0；
2. forced-only pass count 为 0；
3. rate 25 满足 `0 < pass < opportunity`；
4. rate 50 满足 `0 < pass < opportunity`；
5. rate 100 满足 `pass == opportunity`；
6. 所有策略满足 `0 <= pass <= opportunity`。

不同策略会改变轨迹，因此不要求 opportunity count 相同，也不要求
25/50 的实际比例精确等于名义 rate。

neutral 封板门槛：

对四个策略的 overall、near-open、critical 共 12 个 bucket，逐一要求：

1. `baseline == soft`，即两个 `RankMetricSnapshot` 逐字段完全相等；
2. baseline candidate recall 为 1.0；
3. soft candidate recall 为 1.0；
4. `candidate_recall_delta == 0.0`；
5. `top1_recall_delta == 0.0`；
6. `top1_precision_delta == 0.0`；
7. `top1_average_selection_size_delta == 0.0`；
8. `top3_recall_delta == 0.0`；
9. `top3_precision_delta == 0.0`；
10. `top3_average_selection_size_delta == 0.0`；
11. `worst_case_mrr_delta == 0.0`。

由于 baseline 与 neutral 来自同一候选和同一零分 tier，以上 delta
应为精确 0.0。若实现只因浮点表示产生差异，可额外报告
`abs(delta) <= 1e-12`，但 `baseline == soft` 仍必须成立。

唯一判定：

- 任一前置、测试、可重复性、数据、策略行为或 neutral 门槛失败：
  `benchmark_invalid`
- 全部通过：
  `neutral_baseline_verified`

不得输出其他结论。`neutral_baseline_verified` 只表示被拒绝信号已安全撤销，
不表示存在新的猜牌能力、概率、置信度、策略集成或胜率提升。

最终报告必须包含：

1. 前置检查与 HEAD SHA；
2. 两条测试命令及 140/250 结果；
3. 正式参数；
4. 两次耗时和 SHA-256；
5. 每个策略 opportunity/pass count 和实际比例；
6. 每个策略 requested/completed/incomplete；
7. 每个策略 eligible/evaluated/valid/invalid/skipped；
8. 每个策略 diagnostics；
9. 每个策略 overall/near-open/critical 的 sample count；
10. 12 个 bucket 的 baseline/soft 完整指标和全部 delta；
11. 对数据、策略行为和 neutral 门槛逐项给出 pass/fail；
12. 最终唯一判定；
13. 未解决风险；
14. 运行前后 `git status --short` 一致且未修改文件。
```

## 完成判定

Step J-C3d2 只有在以下条件满足时才算完成：

- J-C3d1 已提交且工作区干净；
- 140/250 回归通过；
- 四个策略各 50 局完整运行两次；
- 报告和 SHA-256 可重复；
- 12 个 bucket 的 baseline 与 neutral snapshot 完全相同；
- 所有 delta 严格为 0；
- 按规则给出唯一判定；
- 未修改任何文件；
- 未把安全撤销表述为新能力或胜率提升。
