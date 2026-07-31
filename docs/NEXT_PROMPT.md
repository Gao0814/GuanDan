# 下一步实施提示词

## Step J-D1c3c2c1：四策略配对 prompt 覆盖与成本开发基准

请在 GuanDan 项目中实现 Step J-D1c3c2c1。任务是建立 evaluation-only、无网络的配对 prompt collector，在 forced-only 与 25/50/100% strategic-pass 四种轨迹上量化 confidence ready 覆盖、omitted 原因、字符成本和 off/on 精确插入一致性。

本步骤不调用真实 DeepSeek，不选择模型动作，不修改 runtime，也不形成动作质量或胜率结论。

## 一、前置状态

J-D1c3c2b2 已完成：

- off、shadow-only、prompt 三态开关严格；
- ready payload 是 client kwargs 的唯一差异；
- omitted/unavailable 与 shadow-only kwargs、prompt、动作和 fallback 相同；
- DeepSeekClient 只插入一次固定 `【残局牌面信念】` 章节；
- 定向 54 项、相关 48 项、全量 345 项测试通过。

现有 confidence/prompt 文件可能尚未提交。保留全部已有改动，不要删除、还原或重写。

## 二、修改范围

只允许新增：

- `evaluation/confidence_prompt_benchmark.py`
- `tests/test_confidence_prompt_benchmark.py`

不要修改任何现有文件，包括 runtime agents、DeepSeekClient、evaluation 既有模块、CLI、RAG、engine、config 或 docs。

不得新增依赖，不扩展到 J-D1c3c2c2/c3。

## 三、禁止边界

新 benchmark：

- 不得调用 `DeepSeekClient.suggest_action_id()`；
- 不得调用 HTTP transport；
- 不得读取 API key；
- 不得读取 `game._state` 或 ground truth；
- 不得导入 `evaluation.benchmark_truth`；
- 不得保留 observation、prompt、手牌、玩家边际或逐样本报告；
- 不得影响生成轨迹的 evaluation agent。

只允许使用：

- `GuanDanGame.observe()` 与 `legal_actions()`；
- `classify_game_phase()`；
- `build_runtime_card_confidence()`；
- `build_card_confidence_prompt_payload()`；
- `DeepSeekClient._prune_legal_actions()`；
- `DeepSeekClient._build_structured_prompt()`；
- evaluation-only `StrategicPassAIAgent`。

## 四、报告结构

新增 frozen、slots dataclass：

### `ConfidencePromptCoverageBucket`

至少包含：

- `sample_count`
- `confidence_available_count`
- `confidence_unavailable_count`
- `payload_ready_count`
- `payload_omitted_count`
- `budget_omitted_count`
- `ready_exact_insertion_count`
- `omitted_prompt_equal_count`
- `pair_mismatch_count`
- `payload_char_sum`
- `payload_char_min`
- `payload_char_max`
- `prompt_delta_char_sum`
- `prompt_delta_char_min`
- `prompt_delta_char_max`
- `diagnostic_counts`

### `PolicyConfidencePromptReport`

至少包含：

- `policy_name`
- `strategic_pass_rate`
- `strategic_pass_opportunity_count`
- `strategic_pass_count`
- requested/completed/incomplete games
- eligible/evaluated/valid/invalid/skipped samples
- `overall`
- `by_external_count`
- `prompt_pair_sha256`
- 顶层 `diagnostic_counts`

### `ConfidencePromptBenchmarkReport`

至少包含：

- `requested_policy_count`
- caller 顺序的不可变 `by_policy` mapping

全部报告必须 frozen/slots、JSON 友好，mapping 使用不可变副本。

报告不得包含 seed 列表、样本 ID、observation、legal actions、prompt 文本、confidence/payload 明细、玩家或手牌。

## 五、运行入口

提供：

```python
run_confidence_prompt_benchmark(
    seeds: Sequence[int],
    *,
    strategic_pass_rates: Sequence[int] = (0, 25, 50, 100),
    current_level_rank: str = "2",
    max_steps: int = 5000,
    max_samples_per_game: int = 128,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
) -> ConfidencePromptBenchmarkReport
```

输入验证沿用既有 benchmark 风格：

- seeds 为非空、唯一、非 `bool` 整数序列；
- rates 为非空、唯一、0..100 非 `bool` 整数序列；
- current level rank 合法；
- 所有上限为非 `bool` 正整数；
- `max_external_cards <= 12`。

无效调用参数显式抛 `ValueError`。

## 六、采集流程

每个 rate 必须创建独立：

- game；
- agent；
- strategic-pass counter；
- sample set；
- aggregate；
- prompt pair hasher。

每步：

1. 读取公开 observation；
2. 只在 `critical_endgame` 进入采集；
3. sample ID 仅在内存中使用 `(seed, step_no, observer_player_id)` 去重；
4. 按 external unknown count 分到互斥桶：`external_0_4`、`external_5_8`、`external_9_12`；
5. 每局超过样本上限只计 skipped 与规范诊断；
6. 获取本步 legal actions；
7. 使用同一个 phase context 构建 runtime confidence；
8. 对 confidence 构建一次 prompt payload；
9. 按 DeepSeek agent 当前逻辑计算 pruned actions；
10. 使用完全相同的公开参数构建 off prompt；
11. 使用相同参数并传入 payload 构建 on prompt；
12. 聚合状态、字符成本和配对一致性；
13. 使用该策略 agent 从原始 legal actions 选择动作并推进游戏。

off/on prompt 的可选上下文固定为空：

- `rag_context=None`
- `hand_evaluation=None`
- `card_tracking_summary=None`

这保证本步骤只测 confidence 章节增量，不评估其他功能。

## 七、配对一致性

### ready payload

必须构造预期 on prompt：在 off prompt 的唯一 `【场景标签】` 标题前插入：

```text
【残局牌面信念】
<payload.text>

```

要求：

- 实际 on prompt 与预期文本完全相等；
- 新标题恰好出现一次；
- payload text 恰好出现一次；
- `delta = len(on_prompt) - len(off_prompt) > 0`；
- `ready_exact_insertion_count` 增加。

### omitted payload

要求：

- on prompt 与 off prompt 完全相等；
- delta = 0；
- `omitted_prompt_equal_count` 增加。

任一不满足：

- `pair_mismatch_count` 增加；
- 记录规范诊断 `prompt_pair_mismatch`；
- 不保留实际 prompt。

## 八、聚合规则

- `sample_count = available + unavailable`；
- `sample_count = ready + omitted`；
- `evaluated = valid + invalid`，只有结构完整且完成配对检查的样本计入 valid；
- ready 样本才计 payload char 与正 prompt delta；
- min/max 在没有 ready 样本时稳定为 0；
- `budget_omitted_count` 只统计含 `prompt_budget_exceeded` 的 payload；
- confidence 和 payload diagnostics 按冒号前类别聚合；
- 同一样本同一类别只计一次；
- overall 必须直接聚合原始样本统计，不能平均三个桶；
- 三桶合计必须与 overall 每个可加计数一致；
- strategic pass 必须满足 `0 <= pass <= opportunity`。

## 九、prompt pair hash

每个策略维护一个 SHA-256 hasher。

按样本采集顺序，将以下 canonical JSON 编码后加入 hasher：

```text
[external_bucket_name, off_prompt, on_prompt]
```

要求：

- `ensure_ascii=False`
- `sort_keys=True`
- `separators=(",", ":")`
- 不把 sample ID 或 seed 写入 hash payload；
- 最终报告只保留十六进制 digest，不保留 prompt。

相同参数双运行时 digest 和完整报告必须一致。

## 十、测试要求

至少覆盖：

- 输入参数严格验证；
- 默认四策略顺序与自定义 rate 顺序；
- 每个 `(seed, player_id)` 创建独立 agent；
- forced active pass=0，100% active pass=opportunity；
- 只采 critical，三个 external bucket 互斥；
- duplicate/sample-limit/max-steps 诊断；
- ready 精确插入与正 delta；
- omitted prompt 完全相等与零 delta；
- mismatch 只计诊断，不泄露 prompt；
- available/unavailable、ready/omitted 守恒；
- overall 与三桶原始计数守恒；
- payload/prompt delta sum/min/max；
- 没有 ready 样本时 min/max 为 0；
- diagnostics 规范化和同样本去重；
- report frozen、mapping 不可变、JSON 序列化；
- 同参数报告与 digest 可重复；
- 报告没有 seed、样本 ID、observation、prompt、玩家或手牌字段；
- 源码不调用 `suggest_action_id`、transport、API key、ground truth 或 `game._state`。

测试不得进行网络请求。

## 十一、验证命令

运行：

```bash
python -m unittest tests.test_confidence_prompt_benchmark tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence -q
python -m unittest tests.test_deepseek_prompt_step_h tests.test_pass_policy_benchmark tests.test_marginal_policy_corpus tests.test_rag_step_h tests.test_action_pruning -q
python -m unittest discover -q
git diff --check
```

边界扫描：

```bash
rg -n "suggest_action_id|_post_json|api_key|ground_truth|game\._state|benchmark_truth" evaluation/confidence_prompt_benchmark.py
rg -n "confidence_prompt_benchmark" agents cli rag engine
```

两条均不得出现实际调用或反向导入。

## 十二、开发容量试验

单元测试全部通过后运行两次：

```text
seeds = 80..89
rates = 0,25,50,100
games per policy = 10
current_level_rank = 2
max_steps = 5000
max_samples_per_game = 128
max_external_cards = 12
max_search_nodes = 1,000,000
max_solutions = 100,000
```

开发门槛：

- 两次报告、`to_dict()` 和 canonical JSON hash 完全一致；
- 四策略各 10/10 局完成，无 incomplete；
- invalid/duplicate/sample-limit/pair mismatch 均为 0；
- 四策略三个 external bucket 均有样本；
- 每个策略每个 bucket 至少有一个 ready 样本；
- `budget_omitted_count=0`；
- `ready_exact_insertion_count=payload_ready_count`；
- `omitted_prompt_equal_count=payload_omitted_count`；
- 所有 ready delta 为正且不超过 payload 字符数加固定章节开销；
- 所有报告 JSON 可序列化且无 prompt/observation 明细。

若通过，唯一开发判定为：

```text
confidence_prompt_coverage_capacity_verified
```

否则：

```text
development_capacity_failed
```

开发结果不能作为动作质量、模型收益或胜率结论。

## 十三、输出要求

最终报告必须包含：

1. 修改文件；
2. 报告 dataclass 和运行入口；
3. 配对 prompt 构建与 exact insertion 规则；
4. 聚合、诊断与 hash 规则；
5. 定向和全量测试结果；
6. 边界扫描结果；
7. 双次开发运行耗时与 hash；
8. 四策略行为、样本、ready/omitted、字符成本和各桶覆盖；
9. 唯一开发判定；
10. 明确说明没有调用 DeepSeek、没有动作质量或胜率结论。

完成后停止，不扩展到 J-D1c3c2c2/c3，不修改 docs。
