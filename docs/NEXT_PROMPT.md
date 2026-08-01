# 下一步实施提示词

## Step J-D1c3c2c2：独立四策略 prompt coverage 正式验收

请在 GuanDan 项目中执行 Step J-D1c3c2c2。任务是提交当前 J-D1c3c1 至 c2c1 实现检查点，然后在干净工作区使用全新固定 seed，对四种 strategic-pass 轨迹运行两次无网络 prompt coverage 正式基准。

本步骤不修改实现、测试、docs、预算、分桶、策略 gate 或门槛，不调用真实 DeepSeek，也不评价动作质量。

## 一、前置结论

J-D1c3c2c1 开发容量已通过：

- seed `80..89`，四策略各 10 局；
- 双运行报告完全相等；
- SHA-256 为 `15370d48a49a8067d9790bbd89b54431c54e6a4dd5d5403a3b2ec23d10ccfd6b`；
- 1084 个 critical 样本全部 confidence available、payload ready；
- omitted、budget omitted、pair mismatch、diagnostics 均为 0；
- 每样本 prompt delta 精确等于 payload char count + 11；
- 唯一开发判定 `confidence_prompt_coverage_capacity_verified`。

开发 seed `80..89` 不得进入正式报告或判定。

## 二、实现检查点

当前以下十一个实现/测试文件可能尚未提交：

- `agents/card_confidence.py`
- `agents/card_confidence_pipeline.py`
- `agents/card_confidence_prompt.py`
- `agents/deepseek_ai.py`
- `agents/deepseek_client.py`
- `evaluation/confidence_prompt_benchmark.py`
- `tests/test_card_confidence.py`
- `tests/test_card_confidence_pipeline.py`
- `tests/test_card_confidence_prompt.py`
- `tests/test_confidence_prompt_benchmark.py`
- `tests/test_deepseek_prompt_step_h.py`

正式运行前：

1. 运行 `git status --short`；
2. 确认除上述文件外没有其他未提交改动；
3. 确认 docs 规划提交已在 HEAD 历史中；
4. 运行全部回归和 `git diff --check`；
5. 只暂存上述十一个实现/测试文件；
6. 用清晰提交名创建 J-D1c3c2c1 实现检查点；
7. 记录完整 HEAD；
8. 确认 `git status --short` 为空。

若存在无法归属的其他改动，停止并报告 `precondition_failed`，不要 stash、还原或混入提交。

## 三、运行前回归

提交前和提交后均确认以下命令通过：

```bash
python -m unittest tests.test_confidence_prompt_benchmark tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence -q
python -m unittest tests.test_deepseek_prompt_step_h tests.test_pass_policy_benchmark tests.test_marginal_policy_corpus tests.test_rag_step_h tests.test_action_pruning -q
python -m unittest discover -q
git diff --check
```

预期：

- 第一组 28 项通过；
- 第二组 77 项通过；
- 全量 351 项通过；
- 工作区干净。

任一失败则停止，唯一判定 `benchmark_invalid`，不得运行正式 corpus。

## 四、锁定参数

两次完整运行均使用：

```text
seeds = 10000..10049
games per policy = 50
strategic_pass_rates = 0,25,50,100
current_level_rank = 2
max_steps = 5000
max_samples_per_game = 128
max_external_cards = 12
max_search_nodes = 1,000,000
max_solutions = 100,000
```

调用：

```python
run_confidence_prompt_benchmark(
    tuple(range(10000, 10050)),
    strategic_pass_rates=(0, 25, 50, 100),
    current_level_rank="2",
    max_steps=5000,
    max_samples_per_game=128,
    max_external_cards=12,
    max_search_nodes=1_000_000,
    max_solutions=100_000,
)
```

预计双运行总耗时约 9 至 12 分钟。

正式运行期间不得修改代码、测试、docs、参数或阈值。

## 五、canonical JSON 与双运行

每次报告使用：

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

- 两个顶层 report 完全相等；
- 两个 `to_dict()` 完全相等；
- 两个 canonical JSON 完全相等；
- 两个 SHA-256 相同；
- 每个策略的 `prompt_pair_sha256` 两次相同；
- JSON 无 NaN/Infinity。

任一失败判定 `benchmark_invalid`。不得第三次运行、择优选择或多数表决。

## 六、策略行为完整性

策略顺序必须为：

1. `forced_only`
2. `strategic_pass_25`
3. `strategic_pass_50`
4. `strategic_pass_100`

每个策略必须：

- requested/completed/incomplete games = `50/50/0`；
- forced-only active pass = 0；
- pass-25 与 pass-50 满足 `0 < pass < opportunity`；
- pass-100 满足 `pass = opportunity > 0`；
- 实际主动 pass 比例严格满足 `forced < 25 < 50 < 100`；
- 独立 game、agent、counter、sample set、aggregate 和 hasher。

任一失败判定 `benchmark_invalid`。

## 七、样本完整性

每个策略必须：

- `eligible = evaluated = valid`；
- invalid = 0；
- skipped = 0；
- 顶层 diagnostics 为空；
- overall diagnostics 为空；
- 三个 external bucket diagnostics 均为空；
- overall sample count 等于 evaluated；
- 三桶 sample 合计等于 overall；
- 三桶所有可加计数逐项合计等于 overall；
- 每个 external bucket 至少 350 个 sample/valid。

任一失败判定 `benchmark_invalid`。

## 八、coverage 门槛

对四策略 overall 和三个 external bucket 分别检查：

- `confidence_available_count = sample_count`；
- `confidence_unavailable_count = 0`；
- `payload_ready_count = sample_count`；
- `payload_omitted_count = 0`；
- `budget_omitted_count = 0`；
- `ready_exact_insertion_count = sample_count`；
- `omitted_prompt_equal_count = 0`；
- `pair_mismatch_count = 0`；
- 每个 external bucket `payload_ready_count >= 350`。

benchmark 数据有效但任一 coverage 门槛失败，判定：

```text
reject_confidence_prompt_action_ablation
```

不得用其他策略或桶通过进行抵消。

## 九、字符成本门槛

对四策略 overall 和三个 external bucket 分别检查：

- `payload_char_min > 0`；
- `payload_char_max <= 2400`；
- `payload_char_sum > 0`；
- `prompt_delta_char_min = payload_char_min + 11`；
- `prompt_delta_char_max = payload_char_max + 11`；
- `prompt_delta_char_sum = payload_char_sum + 11 * payload_ready_count`；
- 所有 prompt delta 为正。

任一失败判定 `reject_confidence_prompt_action_ablation`。

原始字符总量只报告，不设置额外优化阈值，不允许事后改 2400 字符预算。

## 十、隐私与边界

报告与 `to_dict()` 必须只含聚合统计：

- 不含 seed 列表；
- 不含样本 ID；
- 不含 observation；
- 不含 prompt 文本；
- 不含 legal actions；
- 不含玩家、手牌、confidence 或 payload 明细；
- 不含 API key、请求或模型响应。

正式运行不得调用：

- `suggest_action_id()`；
- HTTP transport；
- ground truth；
- `game._state`。

任一边界失败判定 `benchmark_invalid`。

## 十一、唯一判定

严格按顺序给出一个结论：

1. 前置、回归、提交范围、可重复性、策略行为、数据完整性或隐私边界失败：`benchmark_invalid`；
2. benchmark 有效，但任一 coverage、预算或精确插入门槛失败：`reject_confidence_prompt_action_ablation`；
3. 全部通过：`confidence_prompt_coverage_verified`。

不得输出“部分通过”“总体通过”或其他模糊结论。

## 十二、输出要求

最终报告必须包含：

1. 实现检查点提交与完整 HEAD；
2. 提交前后、正式运行前后 `git status --short`；
3. 三组回归和 `git diff --check`；
4. 两次耗时、报告相等性和 canonical SHA-256；
5. 四策略 opportunity、active pass 和比例；
6. 每策略 games 与 eligible/evaluated/valid/invalid/skipped；
7. 每策略 overall 和三桶全部 coverage 计数；
8. 每策略 overall 和三桶 payload/prompt delta sum/min/max；
9. 每策略 pair digest；
10. 所有完整性、coverage 和字符门槛 pass/fail；
11. 唯一判定；
12. 明确说明未调用 DeepSeek、未形成动作质量或胜率结论。

完成后停止，不扩展到 J-D1c3c2c3，不修改 docs。
