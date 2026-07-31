# 下一步实施提示词

## Step J-D1c2c：独立语料正式校准

请在 GuanDan 项目中执行 Step J-D1c2c。任务是使用预注册的独立 seed 对 critical-endgame 组合边际做正式、双运行、可重复的离线校准验收。

本步骤只运行现有测试和 benchmark，不修改任何代码、测试、docs、参数、分桶或阈值。

## 一、执行前提

正式运行前必须满足：

1. HEAD 已包含 J-D1c2b collector、共享 truth helper、J-D1c1/J-D1c2a；
2. 以下文件均已进入提交：
   - `evaluation/benchmark_truth.py`
   - `evaluation/marginal_corpus.py`
   - `evaluation/marginal_metrics.py`
   - `evaluation/marginal_benchmark.py`
   - 对应测试；
3. `git status --short` 为空；
4. 不在正式运行过程中创建或修改仓库文件；
5. 不使用开发 seed `40..59`。

如果当前改动尚未提交，先形成 J-D1c2b 检查点提交，再开始正式运行。

## 二、运行前回归

运行：

```bash
python -m unittest tests.test_marginal_corpus tests.test_marginal_benchmark tests.test_marginal_metrics tests.test_rank_benchmark tests.test_card_allocations tests.test_belief_metrics tests.test_ranking_metrics tests.test_card_ranker tests.test_pass_policy_benchmark tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q
git diff --check
```

预期基线：

- 定向 179 项通过；
- 全量 303 项通过；
- 无补丁格式错误；
- 工作区保持干净。

任何回归失败都停止正式 benchmark，判定 `benchmark_invalid`。

## 三、锁定参数

两次运行必须使用完全相同参数：

```text
seeds = 5000..5099
games = 100
current_level_rank = 2
max_steps = 5000
max_samples_per_game = 128
max_external_cards = 12
max_search_nodes = 1,000,000
max_solutions = 100,000
agent = default RuleBasedAIAgent
```

调用：

```python
run_marginal_corpus(
    tuple(range(5000, 5100)),
    current_level_rank="2",
    max_steps=5000,
    max_samples_per_game=128,
    max_external_cards=12,
    max_search_nodes=1_000_000,
    max_solutions=100_000,
)
```

禁止传入自定义 `agent_factory`。

## 四、双运行可重复性

完整运行两次，分别记录耗时。

对每份报告生成 canonical JSON：

```python
payload = json.dumps(
    report.to_dict(),
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
)
digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

要求：

- 两个 `MarginalCorpusReport` 完全相等；
- 两个 `to_dict()` 完全相等；
- 两段 canonical JSON 完全相等；
- 两个 SHA-256 完全相等；
- payload 无 NaN/Infinity；
- 运行前后 `git status --short` 均为空。

任一项失败，唯一判定为 `benchmark_invalid`，不得通过第三次运行挑选结果。

## 五、数据完整性门槛

以下条件必须全部满足：

1. requested/completed/incomplete = `100 / 100 / 0`；
2. eligible = evaluated = valid；
3. invalid = 0；
4. sample-limit skipped = 0；
5. top-level diagnostics = `{}`；
6. overall diagnostic counts = `{}`；
7. 三个外部牌数桶 diagnostic counts 均为 `{}`；
8. overall sample count 等于 evaluated；
9. 三个桶 sample count 之和等于 overall；
10. 三个桶 valid count 之和等于 overall valid；
11. 三个桶 rank pair count 之和等于 overall；
12. `external_0_4` 至少 700 个 valid 样本；
13. `external_5_8` 至少 700 个 valid 样本；
14. `external_9_12` 至少 700 个 valid 样本；
15. 报告可 canonical JSON 序列化；
16. 报告不包含 seed、sample、observation、玩家或 truth 明细。

任一数据完整性门槛失败，判定 `benchmark_invalid`，不继续解释校准指标。

## 六、精确指标换算

所有门槛比较优先使用报告中的整数分子/分母构造 `Fraction`，不要先转 float。

### 1. 经验正例率

```text
q = truth_positive_rate
```

如果 `q == 0` 或 `q == 1`，常数基线退化，判定 `benchmark_invalid`。

### 2. 常数概率 Brier 基线

使用同一 bucket 的经验正例率：

```text
constant_brier = q * (1 - q)
```

### 3. Brier skill

```text
brier_skill =
    (constant_brier - presence_brier_mean)
    / constant_brier
```

skill 为正表示组合边际优于只预测该 bucket 经验正例率的常数模型。

### 4. 支持度 MCE

报告原始 MCE 包含所有非空桶，容易被极少样本桶主导，因此只作为描述性指标。

正式护栏另计算：

```text
supported_mce =
    max(bin.absolute_gap for bin meeting support threshold)
```

支持度：

- overall：`prediction_count >= 200`；
- 每个 external bucket：`prediction_count >= 100`。

每个聚合范围至少要有两个达到支持度的 calibration bin；否则判定 `benchmark_invalid`。

## 七、校准与安全门槛

数据完整性通过后，检查以下全部条件。

### 1. 确定性安全

- overall certainty error count = 0；
- 三个 external bucket certainty error count 均为 0。

任何确定性错误直接失败。

### 2. ECE

- overall ECE ≤ `3/100`；
- 每个 external bucket ECE ≤ `1/20`。

### 3. Brier skill

- overall Brier skill ≥ `3/20`；
- 每个 external bucket Brier skill ≥ `1/10`。

### 4. 支持度 MCE

- overall supported MCE ≤ `1/10`；
- 每个 external bucket supported MCE ≤ `3/20`。

### 5. 描述性指标

以下必须报告，但不单独作为拒绝门槛：

- 原始 MCE；
- copy MSE；
- truth positive rate；
- 十档 prediction count、mean prediction、observed rate、absolute gap；
- Brier mean；
- Brier skill；
- supported MCE。

## 八、唯一判定

按以下顺序给出唯一判定。

### `benchmark_invalid`

任一情况：

- 回归失败；
- 工作区不干净；
- 双运行报告/hash 不一致；
- 对局、样本、diagnostics 或桶覆盖不满足完整性门槛；
- 经验正例率退化；
- 任一范围少于两个达到支持度的 calibration bin。

### `reject_combinatorial_confidence`

数据完整性全部通过，但任一 calibration/safety 门槛失败。

含义：

- 当前等权物理分配边际不能进入 runtime confidence 设计；
- 不得通过修改阈值、筛选桶或使用正式 seed 调参挽回；
- J-D1 硬约束与离线评测仍保留。

### `retain_for_policy_diverse_calibration`

数据完整性、确定性安全、ECE、Brier skill 和支持度 MCE 全部通过。

含义仅为：

- 当前组合边际可进入下一步策略分布稳健性校准；
- 不代表已经允许生成 runtime confidence；
- 不代表动作质量或胜率提升。

## 九、禁止事项

正式运行开始后，不得：

- 修改代码、测试或 docs；
- 修改 seed、对局数、样本上限或搜索上限；
- 修改三个 external bucket；
- 修改 ECE、Brier skill、support 或 MCE 门槛；
- 根据第一次结果只重跑部分 seed；
- 删除 invalid 样本或低表现桶；
- 将正式 seed 用于调参；
- 接入 runtime、RAG、DeepSeek 或策略；
- 把 RuleBasedAI corpus 外推到真实玩家或其他策略分布。

## 十、完成报告

报告必须包含：

### 前置

- HEAD commit；
- 运行前后 `git status --short`；
- 定向和全量回归结果；
- 锁定参数。

### 可重复性

- 两次运行耗时；
- 两份报告是否完全相等；
- canonical JSON SHA-256；
- JSON 无 NaN/Infinity。

### 数据完整性

- requested/completed/incomplete；
- eligible/evaluated/valid/invalid/skipped；
- top-level diagnostics；
- 三个 external bucket 的 sample、valid、invalid、rank pair；
- 16 项完整性门槛逐项结果。

### 校准指标

对 overall 和三个 external bucket 分别报告：

- truth positive rate；
- Brier mean；
- constant Brier baseline；
- Brier skill；
- copy MSE；
- ECE；
- raw MCE；
- supported MCE；
- certainty error count/rate；
- 达到支持度的 calibration bin 数；
- 每个 calibration bin 的 count、mean prediction、observed rate 和 gap。

### 门槛

- 确定性安全逐项结果；
- ECE 逐项结果；
- Brier skill 逐项结果；
- supported MCE 逐项结果；
- 唯一判定。

## 十一、完成边界

J-D1c2c 完成后仍然：

- 不修改 runtime；
- 不输出 runtime confidence；
- 不把 rank 边际加入提示词或动作剪枝；
- 不使用 pass 或其他软信号；
- 不声称策略或胜率提升。

即使判定为 `retain_for_policy_diverse_calibration`，下一步也必须先验证 forced-only 与战略 pass 等不同轨迹分布，才能讨论 runtime 准入。
