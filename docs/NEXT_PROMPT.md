# 下一步实施提示词

## Step J-D1c3c2c2a：可持久化 prompt coverage 恢复正式验收

请在 GuanDan 项目中执行 Step J-D1c3c2c2a。任务是在不修改仓库文件的前提下，使用全新固定 seed 对四种 strategic-pass 轨迹运行两次无网络 prompt coverage 正式基准，并先把每次完整 canonical JSON 持久化到仓库外审计目录，再从文件生成完整门槛报告。

本步骤不是对 seed `10000..10049` 的第三次运行，也不是补采。原 J-D1c3c2c2 已永久判定 `benchmark_invalid`；本步骤使用全新 seed 和预注册的落盘审计链路做独立恢复验收。

本步骤不得修改实现、测试、docs、配置、预算、分桶、策略 gate 或门槛；不得调用真实 DeepSeek、网络、ground truth 或引擎内部状态；不得扩展到 J-D1c3c2c3 动作 A/B。

## 一、已知前置结论

实现检查点：

```text
bc689a37f462672033d754cce7060897d70c7612
J-D1c3c2c1 confidence prompt coverage benchmark
```

首次正式运行 J-D1c3c2c2：

- seed `10000..10049`，四策略各 50 局，完整运行两次；
- 两次耗时 344.621s / 342.153s；
- report、`to_dict()`、canonical JSON 完全相等；
- SHA-256 均为 `1d6506250def487c16d4da2c4fcf1aed2cdfd13231a6096347b768e0c8680a8f`；
- 工具层截断 stdout，未保留 4 策略 x 4 范围的完整聚合；
- 唯一判定 `benchmark_invalid`；未第三次运行、补采或改参。

不得使用原运行的局部输出宣告任何正式门槛通过，也不得再次使用 seed `10000..10049`。

## 二、仓库前置检查

1. 运行 `git status --short`，必须为空；
2. 记录完整 `HEAD`；
3. 确认 `bc689a37f462672033d754cce7060897d70c7612` 是当前 HEAD 的祖先；
4. 确认该实现检查点之后除 `docs/*.md` 外没有源码或测试变化；
5. 确认以下 benchmark/runtime 文件相对 `bc689a3` 无差异：
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
6. 不要提交、stash、还原或清理任何文件。

任一前置失败，停止并报告 `precondition_failed`，不得运行正式 corpus。

## 三、运行前回归

运行：

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
- `git diff --check` 通过；
- 工作区仍为空。

任一失败，停止并判定 `benchmark_invalid`，不得运行正式 corpus。

## 四、仓库外审计目录

正式运行前，在仓库外创建一个全新的审计目录，例如：

```text
%TEMP%\guandan-confidence-prompt-jd1c3c2c2a-<HEAD前12位>
```

要求：

- 目录不在 GuanDan 工作树内；
- 若候选目录已存在且非空，不得覆盖或删除旧证据，改用新的、明确记录的目录；
- 记录绝对路径；
- 先用一个很小的 sentinel JSON 验证 UTF-8 写入、`flush`、`fsync`、原子替换、重新读取和 SHA-256；
- sentinel 失败时停止，判定 `benchmark_invalid`，不得启动正式运行；
- 运行用临时 Python 脚本也放在该目录，不得加入仓库；
- 记录临时 runner 文件的 SHA-256。

## 五、结果持久化协议

临时 runner 每次只执行一次 `run_confidence_prompt_benchmark()`，并在函数返回后立即：

1. 调用 `report.to_dict()`；
2. 使用以下规范生成 canonical JSON：

```python
json.dumps(
    report.to_dict(),
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
)
```

3. 以 UTF-8 写入同目录临时文件；
4. `flush` 并 `os.fsync()`；
5. 原子替换为 `run1.json` 或 `run2.json`；
6. 重新读取文件，验证非空、UTF-8 可解码、JSON 可解析；
7. 计算文件字节数和 SHA-256；
8. stdout 只输出一行短元数据：run 编号、耗时、绝对路径、字节数、SHA-256。

严禁向 stdout 输出 report 对象、`to_dict()`、canonical JSON 或 16 个范围的完整明细。工具输出截断不得再次成为证据链的一部分。

若一次正式运行已经开始，则该次结果写入、解析或校验失败都判定 `benchmark_invalid`；不得重跑该次、不得补采。

## 六、锁定参数

两次完整运行均使用：

```text
seeds = 11000..11049
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
    tuple(range(11000, 11050)),
    strategic_pass_rates=(0, 25, 50, 100),
    current_level_rank="2",
    max_steps=5000,
    max_samples_per_game=128,
    max_external_cards=12,
    max_search_nodes=1_000_000,
    max_solutions=100_000,
)
```

只允许 `run1`、`run2` 两次。不得第三次运行、择优选择、多数表决、修改 seed、修改参数或调整门槛。

## 七、文件级可重复性

两次完成后，从磁盘重新读取 `run1.json` 和 `run2.json`，必须满足：

- 两个文件均存在且非空；
- 两个 JSON 均可按 UTF-8 解析；
- 顶层结构完整；
- 两个文件字节完全一致；
- 两个 canonical JSON SHA-256 相同；
- 每个策略的 `prompt_pair_sha256` 相同；
- JSON 无 NaN/Infinity；
- 不依赖仍在内存中的 report 对象完成比较。

任一失败判定 `benchmark_invalid`。

## 八、审计摘要文件

使用只读解析器从已落盘的 `run1.json` 生成 `audit_summary.json`，仍写入同一仓库外审计目录。摘要至少包含：

- schema/version；
- 完整 HEAD 和实现检查点；
- 锁定参数；
- runner 路径和 SHA-256；
- 两次耗时、文件绝对路径、字节数和 SHA-256；
- 文件级可重复性 pass/fail；
- 四策略 opportunity、active pass、实际比例和 pair digest；
- 四策略 games 与 eligible/evaluated/valid/invalid/skipped；
- 四策略 overall 和三个 external bucket 的全部 coverage 与字符计数；
- 每个范围各门槛的 pass/fail；
- 顶层唯一判定。

生成后重新读取 `audit_summary.json`，验证 UTF-8、JSON 结构和 SHA-256。最终报告必须给出该文件的绝对路径、字节数和哈希。

## 九、策略与数据完整性

策略顺序必须为：

1. `forced_only`
2. `strategic_pass_25`
3. `strategic_pass_50`
4. `strategic_pass_100`

每个策略必须满足：

- requested/completed/incomplete games = `50/50/0`；
- forced-only active pass = 0；
- pass-25 与 pass-50 满足 `0 < pass < opportunity`；
- pass-100 满足 `pass = opportunity > 0`；
- 实际主动 pass 比例严格满足 `forced < 25 < 50 < 100`；
- `eligible = evaluated = valid`；
- invalid = 0；
- skipped = 0；
- 顶层 diagnostics 为空；
- overall diagnostics 为空；
- 三个 external bucket diagnostics 均为空；
- overall sample count 等于 evaluated；
- 三桶所有可加计数逐项合计等于 overall；
- 每个 external bucket 至少 350 个 sample/valid。

任一失败判定 `benchmark_invalid`，不得跨策略或跨桶抵消。

## 十、16 个范围的 coverage 门槛

对四策略的 overall、`external_0_4`、`external_5_8`、`external_9_12` 分别检查：

- `confidence_available_count = sample_count`；
- `confidence_unavailable_count = 0`；
- `payload_ready_count = sample_count`；
- `payload_omitted_count = 0`；
- `budget_omitted_count = 0`；
- `ready_exact_insertion_count = sample_count`；
- `omitted_prompt_equal_count = 0`；
- `pair_mismatch_count = 0`；
- 每个 external bucket `payload_ready_count >= 350`。

benchmark 数据有效但任一 coverage 门槛失败，判定 `reject_confidence_prompt_action_ablation`。

## 十一、16 个范围的字符成本门槛

对每个范围分别检查：

- `payload_char_min > 0`；
- `payload_char_max <= 2400`；
- `payload_char_sum > 0`；
- `prompt_delta_char_min = payload_char_min + 11`；
- `prompt_delta_char_max = payload_char_max + 11`；
- `prompt_delta_char_sum = payload_char_sum + 11 * payload_ready_count`；
- 所有 prompt delta 为正。

benchmark 数据有效但任一字符门槛失败，判定 `reject_confidence_prompt_action_ablation`。不得事后修改 2400 字符预算或固定开销。

## 十二、隐私与边界

确认 benchmark 和审计文件：

- 不调用 `suggest_action_id()`、HTTP transport 或真实 DeepSeek；
- 不读取 ground truth 或 `game._state`；
- 不修改 runtime、RAG、剪枝、CLI 或配置；
- 不包含 seed 列表、样本 ID、observation、prompt 文本、legal actions、玩家或手牌明细；
- 不包含 API key、请求或模型响应；
- 仓库运行前后保持干净。

任一边界失败判定 `benchmark_invalid`。

## 十三、唯一判定

严格按顺序只给出一个结论：

1. 前置、回归、持久化、文件解析、可重复性、策略行为、数据完整性或隐私边界失败：`benchmark_invalid`；
2. benchmark 有效，但任一 coverage、预算或精确插入门槛失败：`reject_confidence_prompt_action_ablation`；
3. 全部通过：`confidence_prompt_coverage_verified`。

不得输出“部分通过”“总体通过”或其他模糊结论。

## 十四、最终输出

最终报告必须包含：

1. 完整 HEAD、实现检查点和运行前后工作区状态；
2. 三组回归和 `git diff --check`；
3. 审计目录、runner 路径及其 SHA-256；
4. 两次耗时、JSON 路径、字节数和 SHA-256；
5. `audit_summary.json` 路径、字节数和 SHA-256；
6. 两次文件级相等性结论；
7. 四策略行为和样本完整性表；
8. 4 策略 x 4 范围的全部 coverage 表；
9. 4 策略 x 4 范围的 payload/prompt delta sum/min/max 表；
10. 每策略 pair digest；
11. 所有门槛 pass/fail；
12. 唯一判定；
13. 明确说明原 seed `10000..10049` 结果仍保持 `benchmark_invalid`；
14. 明确说明未调用 DeepSeek、未形成动作质量或胜率结论。

完成后停止，不扩展到 J-D1c3c2c3，不修改 docs。
