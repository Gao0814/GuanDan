# 下一步实施提示词

## Step K-A3c2b：策略意图 prompt 覆盖独立恢复验收

请在 GuanDan 项目中完成 Step K-A3c2b。本步只运行既有 evaluation benchmark 和仓库外审计，不修改 formatter、runtime、evaluation、tests、docs 或任何仓库文件，不调用模型或网络。

### 背景与唯一目标

K-A3c2 原正式双运行使用 seed `18000..18199`，结构、覆盖、精确插入和可重复性均通过，但因预注册 near-open 字符上界错误，唯一判定保持：

`strategy_intent_prompt_coverage_benchmark_invalid`

K-A3c2a 已通过 40 个真实 formatter 调用封板正确字符契约，唯一判定：

`strategy_intent_prompt_envelope_contract_verified`

本步唯一目标是使用全新 seed 和事前锁定的正确包络，独立恢复正式 prompt coverage 验收。不得追认、改写或复用 K-A3c2 的正式结果。

### 仓库修改边界

本步不允许修改任何仓库文件，包括：

- `agents/strategy_intent_prompt.py`
- `agents/strategy_router.py`
- `agents/deepseek_ai.py`
- `agents/deepseek_client.py`
- `evaluation/strategy_intent_prompt_benchmark.py`
- `tests/test_strategy_intent_prompt.py`
- 其他 runtime、evaluation、tests、CLI、RAG、engine、config、docs 文件

runner、两份完整报告、审计摘要和 manifest 必须写入仓库外的新临时目录。不得把审计产物写入 `logs/`、仓库根目录或测试 fixture。

### 前置检查

1. 记录当前 HEAD 与 `git status --short`。
2. 确认 K-A3c2a 的 `tests/test_strategy_intent_prompt.py` 已进入独立检查点，且该检查点包含 40 组合精确字符契约。
3. 正式运行前工作区必须干净。若存在未提交改动，不得 stash、还原、提交、清理或覆盖；停止并报告 `precondition_failed`。
4. 确认以下实现文件相对 K-A3c1 检查点 `1fca3270843d51c2b565b37e7823b57ed9b950b5` 无差异：
   - `agents/strategy_intent_prompt.py`
   - `agents/strategy_router.py`
   - `agents/deepseek_ai.py`
   - `agents/deepseek_client.py`
   - `evaluation/strategy_intent_prompt_benchmark.py`
5. 阅读上述文件及：
   - `tests/test_strategy_intent_prompt.py`
   - `tests/test_strategy_intent_prompt_benchmark.py`
6. 运行前回归：

```text
python -m unittest tests.test_strategy_intent_prompt -q
python -m unittest tests.test_strategy_intent_prompt tests.test_strategy_intent_prompt_wiring tests.test_strategy_intent_prompt_benchmark tests.test_strategy_router tests.test_strategy_router_shadow tests.test_strategy_router_benchmark -q
python -m unittest discover -q
git diff --check
```

预期基线为 12 / 60 / 431 项；实际数量必须报告。任何失败都停止，不启动 benchmark。

### 锁定正式参数

以下参数不得修改：

```text
seeds = 19000..19199
strategic_pass_rates = (0, 25, 50, 100)
current_level_rank = "2"
max_steps = 5000
max_samples_per_phase_per_game = 128
```

调用既有：

```text
run_strategy_intent_prompt_benchmark(...)
```

四个策略名称与 rate 必须按报告 `policies` 列表顺序精确为：

```text
forced_only / 0
strategic_pass_25 / 25
strategic_pass_50 / 50
strategic_pass_100 / 100
```

审计必须按列表位置和显式名称→rate 映射复核，禁止依赖 canonical JSON 对象键迭代顺序。

### 执行次数与证据保存

1. runner 可先做只导入、签名和输出目录写入检查，但 smoke check 不得调用 benchmark。
2. 正式 benchmark 必须恰好完整运行两次。
3. 每次运行结束后立即把完整 `report.to_dict()` 以 `ensure_ascii=False`、`sort_keys=True`、紧凑 separators、`allow_nan=False` 写入独立 JSON，再计算 SHA-256。
4. 不得依赖标准输出保存完整报告；标准输出只打印短摘要和证据路径。
5. 两次运行后生成只含聚合检查结果的 `audit_summary.json` 与文件大小/hash 的 `manifest.json`。
6. 不得进行第三次运行、补采、换 seed、修改阈值或失败后恢复运行。

### 预注册完整性门槛

所有条件必须同时满足：

- 两个 `StrategyIntentPromptBenchmarkReport`、`to_dict()` 和 canonical JSON 完全相等；
- 两份 canonical JSON SHA-256 相同，可解析且不含 NaN/Infinity；
- requested policy count 为 4，策略名称、rate 和顺序精确匹配；
- 每个策略 games 为 `200/200/0`；
- forced-only 主动 pass 为 0；100% 策略主动 pass 等于 opportunity；25% 与 50% 均满足 `0 < active < opportunity`；
- 四策略主动 pass 比例按精确交叉乘法严格递增；
- 每个策略 `eligible = evaluated`，duplicate 和 sample-limit skipped 均为 0；
- 顶层及所有 phase bucket diagnostics 均为空；
- phase 集合精确为 `midgame/endgame/near_open_endgame/critical_endgame`；
- overall 是四个 phase 的逐字段整数和，所有现有守恒成立；
- 每个策略的 ready 样本最低数量：midgame 1400、endgame 1000、near-open 1000、critical 1800。

### 预注册覆盖与字符门槛

对四策略×四阶段共 16 个 bucket，全部要求：

- `sample_count = router_available_count = payload_ready_count = exact_insertion_count`；
- router unavailable/invalid、payload omitted/invalid、omitted equal、ready/omitted/prompt pair mismatch 全部为 0；
- `diagnostic_counts = {}`；
- `prompt_delta_char_sum = payload_char_sum + 9 * payload_ready_count`；
- `prompt_delta_char_min = payload_char_min + 9`；
- `prompt_delta_char_max = payload_char_max + 9`。

每个 phase 的观测 min/max 必须落在 K-A3c2a 封板包络内：

| phase | payload 允许包络 | delta 允许包络 |
|---|---:|---:|
| midgame | 74..81 | 83..90 |
| endgame | 74..81 | 83..90 |
| near_open_endgame | 84..91 | 93..100 |
| critical_endgame | 83..90 | 92..99 |

这里要求观测值不越过理论包络，不要求每个正式 bucket 恰好观察到理论最小值和最大值。不得因样本未出现某个 reason 而伪造或补采。

每个策略的 `prompt_pair_sha256` 必须是非空 64 位小写十六进制，且两次运行对应值相等。报告与审计 JSON 不得包含 seed 列表、逐样本 ID、observation、prompt 文本、action、玩家、手牌、API key、模型响应或真实对局日志。

### 运行后检查

重复运行前置中的三组测试与 `git diff --check`，并确认：

- HEAD 未变化；
- `git status --short` 仍为空；
- 没有网络、DeepSeek、API key、`.env`、ground truth、`game._state` 或 `record.txt` 访问；
- intent 未影响对局推进动作，仍只做 evaluation-only prompt pair 构造。

### 唯一判定

- 全部前置、双运行、完整性、覆盖、字符、隐私和回归门槛通过：`strategy_intent_prompt_coverage_recovery_verified`
- benchmark 启动后任一门槛失败、运行不完整、证据缺失或输出不可审计：`strategy_intent_prompt_coverage_recovery_invalid`
- 前置检查未满足且 benchmark 未启动：`precondition_failed`

`strategy_intent_prompt_coverage_recovery_verified` 只授权规划 K-A3d1 evaluation-only 动作消融载体。它不追认 K-A3c2 通过，不授权真实 API、默认启用、RAG 路由、完整 DeepSeek 对局或胜率声明。

### 最终报告

报告必须包含：

- 唯一判定；
- HEAD、K-A3c2a 检查点及运行前后工作区状态；
- 锁定参数与 benchmark 实际执行次数；
- 两次耗时、canonical SHA-256 与报告相等性；
- 仓库外审计目录及 runner/report/summary/manifest 的 bytes 和 SHA-256；
- 四策略 games、pass opportunity/active 和精确比例顺序；
- 16 个 bucket 的 sample/ready、payload min/max、delta min/max；
- 所有零值异常项、diagnostics、守恒和最低样本门槛结果；
- 运行前后测试数量、`git diff --check` 和边界扫描结果；
- 明确说明 K-A3c2 原判定仍为 `strategy_intent_prompt_coverage_benchmark_invalid`；
- 明确说明未修改仓库、未联网、未形成动作质量或胜率结论。
