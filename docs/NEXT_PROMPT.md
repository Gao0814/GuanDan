# 下一步实施提示词

## Step J-D1c3b：独立多策略正式校准

请在 GuanDan 项目中执行 Step J-D1c3b。任务是使用独立固定 seed，对 forced-only 与 25/50/100% strategic-pass 四种轨迹分别做正式组合边际校准。

本步骤只运行现有测试和 benchmark，不修改代码、测试、docs、策略、参数、分桶或阈值。

## 一、执行前提

正式运行前必须：

1. HEAD 已包含：
   - `evaluation/marginal_policy_corpus.py`
   - `tests/test_marginal_policy_corpus.py`
   - J-D1c1 至 J-D1c3a 全部依赖；
2. `git status --short` 为空；
3. J-D1c2c 判定为 `retain_for_policy_diverse_calibration`；
4. J-D1c3a 判定为 `policy_diversity_capacity_verified`；
5. 不使用开发 seed `60..69` 或单策略正式 seed `5000..5099`。

若 J-D1c3a 尚未提交，先形成检查点提交并确保工作区干净。

## 二、运行前回归

```bash
python -m unittest tests.test_marginal_policy_corpus tests.test_marginal_corpus tests.test_marginal_benchmark tests.test_marginal_metrics tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_card_allocations tests.test_belief_metrics tests.test_ranking_metrics tests.test_card_ranker tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q
git diff --check
```

预期：

- 定向 187 项通过；
- 全量 311 项通过；
- 工作区保持干净。

任一失败则判定 `benchmark_invalid`，不运行正式 corpus。

## 三、锁定参数

两次完整运行均使用：

```text
seeds = 7000..7049
games per policy = 50
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
    tuple(range(7000, 7050)),
    strategic_pass_rates=(0, 25, 50, 100),
    current_level_rank="2",
    max_steps=5000,
    max_samples_per_game=128,
    max_external_cards=12,
    max_search_nodes=1_000_000,
    max_solutions=100_000,
)
```

预计双运行总耗时约 10 至 12 分钟。

## 四、双运行可重复性

对每次完整报告生成：

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
- canonical JSON 完全相等；
- SHA-256 完全相等；
- 四个策略的 corpus、行为计数逐项相等；
- JSON 无 NaN/Infinity；
- 运行前后工作区均干净。

失败时不得增加第三次运行挑选结果，直接判定 `benchmark_invalid`。

## 五、策略行为完整性

顶层必须包含且只包含：

```text
forced_only
strategic_pass_25
strategic_pass_50
strategic_pass_100
```

每个策略：

- opportunity count > 0；
- `0 <= active_pass <= opportunity`。

额外门槛：

- forced-only active pass = 0；
- 25% active pass > 0 且 < opportunity；
- 50% active pass > 0 且 < opportunity；
- 100% active pass = opportunity；
- 实际 `active_pass / opportunity` 严格满足：

```text
forced < pass25 < pass50 < pass100
```

任一行为门槛失败，判定 `benchmark_invalid`，因为策略分布没有按预注册方式形成。

## 六、每策略数据完整性

四个策略分别满足全部条件：

1. requested/completed/incomplete = `50 / 50 / 0`；
2. eligible = evaluated = valid；
3. invalid = 0；
4. skipped = 0；
5. top-level corpus diagnostics = `{}`；
6. overall diagnostics = `{}`；
7. 三个 external bucket diagnostics 均为 `{}`；
8. overall sample count = evaluated；
9. 三桶 sample 总数 = overall；
10. 三桶 valid 总数 = overall；
11. 三桶 rank pair 总数 = overall；
12. `external_0_4` valid samples ≥ 350；
13. `external_5_8` valid samples ≥ 350；
14. `external_9_12` valid samples ≥ 350；
15. corpus 可 JSON 序列化；
16. payload 不含 seed、sample ID、observation、玩家或 truth 明细。

任一策略的数据完整性失败，顶层判定 `benchmark_invalid`。

## 七、精确指标定义

对四个策略的：

- overall
- external_0_4
- external_5_8
- external_9_12

共 16 个聚合范围分别计算，不跨策略平均。

使用 `Fraction`：

```text
q = truth_positive_rate
constant_brier = q * (1 - q)
brier_skill =
    (constant_brier - presence_brier_mean)
    / constant_brier
```

如果任一范围 `q == 0` 或 `q == 1`，判定 `benchmark_invalid`。

## 八、支持度 MCE

原始 MCE 只报告，不作为单独拒绝门槛。

另计算：

```text
supported_mce =
    max(bin.absolute_gap for supported bins)
```

支持度：

- overall：bin prediction count ≥ 200；
- external bucket：bin prediction count ≥ 100。

每个策略的每个聚合范围至少要有两个支持度达标 bin，否则判定 `benchmark_invalid`。

## 九、逐策略校准护栏

16 个聚合范围必须分别通过。

### 确定性安全

- certainty error count = 0。

### ECE

- 每个策略 overall ECE ≤ `3/100`；
- 每个策略每个 external bucket ECE ≤ `1/20`。

### Brier skill

- 每个策略 overall Brier skill ≥ `3/20`；
- 每个策略每个 external bucket Brier skill ≥ `1/10`。

### supported MCE

- 每个策略 overall supported MCE ≤ `1/10`；
- 每个策略每个 external bucket supported MCE ≤ `3/20`。

不得：

- 对四策略指标求平均后验收；
- 用 forced-only 的通过抵消 strategic-pass 失败；
- 用 overall 通过抵消某 external bucket 失败；
- 用 MRR、Top-K 或其他旧指标替代当前校准护栏。

## 十、唯一判定

### `benchmark_invalid`

任一情况：

- 回归或工作区前提失败；
- 双运行报告/hash 不一致；
- 策略行为梯度失败；
- 任一策略数据不完整；
- 任一范围正例率退化；
- 任一范围少于两个支持度达标 bin。

### `reject_runtime_confidence`

benchmark 有效，但任一策略、任一聚合范围未通过 certainty、ECE、Brier skill 或 supported MCE。

含义：

- 当前组合边际不得设计为通用 runtime confidence；
- 不得修改正式阈值或筛选策略/桶挽回；
- J-D1 硬约束、整数边际和离线工具继续保留。

### `policy_diverse_calibration_verified`

四策略的 16 个聚合范围全部通过。

含义仅为：

- 可进入 J-D1c3c runtime confidence 准入设计；
- 不等于已经接入 runtime；
- 不证明动作质量或胜率提升。

## 十一、禁止事项

正式运行开始后不得：

- 修改代码、测试或 docs；
- 修改 strategic-pass gate；
- 修改 seed、对局数、搜索/样本上限；
- 修改 external bucket；
- 修改支持度或校准阈值；
- 根据第一次结果补采或删除样本；
- 删除表现差的策略；
- 使用跨策略平均；
- 接入 runtime、RAG、DeepSeek、提示词或动作剪枝；
- 声称真实玩家或胜率结论。

## 十二、完成报告

必须包含：

### 前置与可重复性

- HEAD；
- 前后 git status；
- 定向/全量回归；
- 锁定参数；
- 两次耗时；
- 报告相等性与 SHA-256。

### 策略行为

每个策略报告：

- opportunity；
- active pass；
- 实际比例；
- 行为完整性门槛。

### 数据完整性

每个策略报告：

- requested/completed/incomplete；
- eligible/evaluated/valid/invalid/skipped；
- diagnostics；
- 三个 external bucket 的 sample、valid、invalid、rank pair；
- 16 项完整性门槛。

### 校准

每个策略的 overall 与三桶分别报告：

- truth positive rate；
- Brier mean；
- constant baseline；
- Brier skill；
- copy MSE；
- ECE；
- raw MCE；
- supported MCE；
- certainty count/rate；
- 支持度 bin 数；
- 十档 count、mean prediction、observed rate、gap。

### 判定

- 16 个范围的 certainty/ECE/skill/MCE 护栏；
- 唯一判定；
- 明确结论边界。

## 十三、完成边界

即使判定为 `policy_diverse_calibration_verified`，本步骤仍然：

- 不生成 runtime confidence；
- 不修改 agent 决策；
- 不进入 RAG、DeepSeek 或提示词；
- 不改变动作剪枝；
- 不证明胜率提升。

下一步只能先设计最小、fail-closed、可消融的 runtime confidence 契约，再单独验证策略收益。
