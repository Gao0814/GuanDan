# 下一步实施提示词

## Step J-D1c3b2：独立扩容多策略正式校准

请在 GuanDan 项目中执行 Step J-D1c3b2。任务是在完全冻结现有组合边际模型、策略变体、十档分桶和验收门槛的前提下，使用全新固定 seed 扩大四策略独立语料，解决 J-D1c3b 唯一的支持度不足。

本步骤只运行现有测试和 benchmark，不修改代码、测试、docs、策略、参数解释、分桶、支持阈值或数值护栏。

## 一、已知结论

J-D1c3b 已按 seed `7000..7049`、四策略各 50 局完成两次正式运行：

- 两次报告完全相等，SHA-256 均为 `67ed39e3b39b22dd7f2b660c70dc66eb5f6add3c11c0e3dc8315a1a8ca6a7eee`；
- 四策略数据完整性、行为边界和行为比例梯度通过；
- 所有对局完成，invalid、skip、diagnostics 均为 0；
- 15/16 个策略/范围通过全部护栏；
- `strategic_pass_100 / external_0_4` 只有一个 count>=100 的支持 bin，未满足至少两个支持 bin；
- 唯一判定为 `benchmark_invalid`，不是模型拒绝，也不授权 runtime confidence。

该失败语料只能用于确定下一次样本规模。不得将 seed `7000..7049` 混入新报告、阈值调整或最终判定。

## 二、执行前提

正式运行前必须满足：

1. HEAD 包含 J-D1c3a 实现和 J-D1c3b 结果文档；
2. `git status --short` 为空；
3. `evaluation/marginal_policy_corpus.py` 和 `tests/test_marginal_policy_corpus.py` 均在 HEAD；
4. J-D1c2c 判定为 `retain_for_policy_diverse_calibration`；
5. J-D1c3a 判定为 `policy_diversity_capacity_verified`；
6. J-D1c3b 判定为 `benchmark_invalid`，唯一失败原因是支持 bin 数不足；
7. 不使用任何历史 seed：`40..69`、`1000..1199`、`2000..2099`、`3000..3049`、`5000..5099`、`7000..7049`。

任一前提不满足时，立即停止并报告 `precondition_failed`，不得启动正式 benchmark。

## 三、运行前回归

运行：

```bash
python -m unittest tests.test_marginal_policy_corpus tests.test_marginal_corpus tests.test_marginal_benchmark tests.test_marginal_metrics tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_card_allocations tests.test_belief_metrics tests.test_ranking_metrics tests.test_card_ranker tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q
git diff --check
```

预期：

- 定向 187 项通过；
- 全量 311 项通过；
- `git diff --check` 通过；
- 工作区保持干净。

任一失败则判定 `benchmark_invalid`，不得运行正式 corpus。

## 四、锁定参数

两次完整运行均使用：

```text
seeds = 8000..8119
games per policy = 120
rates = 0, 25, 50, 100
current_level_rank = 2
max_steps = 5000
max_samples_per_game = 128
max_external_cards = 12
max_search_nodes = 1,000,000
max_solutions = 100,000
```

调用：

```python
run_marginal_policy_corpus(
    tuple(range(8000, 8120)),
    strategic_pass_rates=(0, 25, 50, 100),
    current_level_rank="2",
    max_steps=5000,
    max_samples_per_game=128,
    max_external_cards=12,
    max_search_nodes=1_000_000,
    max_solutions=100_000,
)
```

120 局仅用于提高偏斜范围的支持度余量。不得修改 count>=100 的 external 支持阈值，也不得合并 calibration bin。

预计双运行总耗时约 24 至 30 分钟。必须完成两次全量运行；除非首次运行已出现明确完整性失败，否则不得只运行一次。

## 五、双运行可重复性

每次完整报告使用以下 canonical JSON：

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

必须满足：

- 两个顶层报告完全相等；
- 两个 `to_dict()` 完全相等；
- 两个 canonical JSON 完全相等；
- 两个 SHA-256 完全相同；
- JSON 不含 NaN 或 Infinity。

任一失败立即判定 `benchmark_invalid`。不得第三次运行、择优选择或多数表决。

## 六、数据完整性

四个策略必须保持顺序：

1. `forced_only`
2. `strategic_pass_25`
3. `strategic_pass_50`
4. `strategic_pass_100`

每个策略必须满足：

- requested/completed/incomplete games = `120/120/0`；
- `eligible_samples = evaluated_samples = valid_samples`；
- invalid samples = 0；
- sample-limit skipped = 0；
- 顶层 diagnostics 为空；
- overall diagnostics 为空；
- 三个 external bucket diagnostics 均为空；
- overall sample 数等于 evaluated samples；
- 三桶 sample/valid/rank-pair 合计分别等于 overall；
- `external_0_4`、`external_5_8`、`external_9_12` 各至少 800 个 valid 样本；
- 报告可 JSON 序列化且不包含 seed、样本 ID、observation、玩家预测或 truth 明细。

任一项失败判定 `benchmark_invalid`。

## 七、策略行为完整性

必须报告每个策略的 opportunity、active pass 和实际比例，并满足：

- forced-only 的 active pass = 0；
- strategic-pass-25 满足 `0 < active_pass < opportunity`；
- strategic-pass-50 满足 `0 < active_pass < opportunity`；
- strategic-pass-100 满足 `active_pass = opportunity > 0`；
- 实际比例严格满足 `forced < pass-25 < pass-50 < pass-100`；
- 每个策略独立创建 game、agent、counter 和 corpus。

任一项失败判定 `benchmark_invalid`。

## 八、支持度前提

对四个策略分别检查：

- `overall`：支持 bin 定义为 prediction count >=200；
- 每个 external bucket：支持 bin 定义为 prediction count >=100；
- 每个策略的 overall 和三个 external bucket 都必须至少有两个支持 bin。

必须输出全部 16 个策略/范围的十档 prediction count 和支持 bin 数。

任一范围少于两个支持 bin，唯一判定为 `benchmark_invalid`。不得继续用该报告作 runtime 准入判定，也不得以其他范围通过抵消。

## 九、校准与安全护栏

只有数据完整性、策略行为、可重复性和全部支持度前提通过后，才检查以下数值护栏。

每个策略的 `overall` 和三个 external bucket 必须满足：

### 确定性安全

- certainty error count = 0；
- certainty error rate = 0。

### ECE

- overall ECE <= `3/100`；
- 每个 external bucket ECE <= `1/20`。

### Brier skill

使用常数预测基线：

```text
constant_brier = positive_rate * (1 - positive_rate)
brier_skill = (constant_brier - model_brier) / constant_brier
```

要求：

- overall Brier skill >= `3/20`；
- 每个 external bucket Brier skill >= `1/10`；
- 正例率必须严格位于 0 和 1 之间。

### Supported MCE

- overall 的 supported MCE <= `1/10`；
- 每个 external bucket 的 supported MCE <= `3/20`。

原始 MCE 与 copy MSE 只报告，不单独作为拒绝门槛。

## 十、唯一判定

严格按以下顺序给出一个结论：

1. 任一执行前提、回归、双运行一致性、数据完整性、策略行为或支持度前提失败：`benchmark_invalid`；
2. benchmark 有效，但任一 certainty、ECE、Brier skill 或 supported MCE 护栏失败：`reject_runtime_confidence`；
3. benchmark 有效且全部 16 个策略/范围通过所有护栏：`policy_diverse_calibration_verified`。

不得使用“部分通过”“整体平均通过”或其他模糊结论。

## 十一、输出要求

最终报告必须包含：

1. HEAD 和运行前后 `git status --short`；
2. 定向、全量回归和 `git diff --check`；
3. 两次运行耗时、报告相等性和 SHA-256；
4. 四策略 opportunity、active pass 和实际比例；
5. 每策略 games 与 eligible/evaluated/valid/invalid/skipped；
6. 每策略 overall 和三桶的 sample、valid、rank-pair；
7. 全部 16 个范围的正例率、Brier mean、常数 Brier、Brier skill、copy MSE、ECE、raw MCE、supported MCE、certainty error；
8. 全部 16 个范围的十档 prediction count 与支持 bin 数；
9. 每项完整性、支持度和数值门槛的 pass/fail；
10. 唯一判定与结论边界。

## 十二、范围限制

- 不修改 `engine/`、runtime `agents/`、CLI、RAG 或 DeepSeek；
- 不修改 `evaluation/`、测试或 docs；
- 不改变 strategic-pass gate；
- 不改变十档校准定义；
- 不改变支持度阈值或数值护栏；
- 不使用 J-D1c3b 数据参与新报告；
- 不生成 runtime confidence；
- 不接入策略主链；
- 不宣称动作质量或胜率提升。

只有 `policy_diverse_calibration_verified` 才允许下一步设计最小、fail-closed、可消融的 runtime confidence 契约；其他判定继续暂停 runtime 接入。
