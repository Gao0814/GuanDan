# 下一步实施提示词

## Step J-D1c3c2c3b：真实 DeepSeek 响应安全 live pilot

请在 GuanDan 项目中执行 Step J-D1c3c2c3b。任务是先提交已完成的 J-D1c3c2c3a harness 检查点，然后在用户明确授权当前 DeepSeek endpoint/model 和最多 48 次无重试外部请求后，使用全新固定语料运行一次小规模 confidence-off/on 真实响应安全试验。

本步骤只验证真实模型响应是否可解析、是否严格落在相同 prompt candidates 中，以及观察到的 same/changed、pass/pressure 行为。它不运行完整 DeepSeek 对局，不评价动作优劣或胜率，不启用默认 confidence。

## 一、前置结论

J-D1c3c2c3a 已完成，唯一开发判定：

```text
confidence_action_ablation_harness_verified
```

当前尚未提交的文件应仅为：

- `evaluation/confidence_action_ablation.py`
- `tests/test_confidence_action_ablation.py`

已验证：

- 单文件 6 项、相关 76 项、全量 357 项通过；
- seed `120..129` 四策略每桶 4 样本双运行；
- 两份 report 完全相等；
- canonical SHA-256：`ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`；
- 每轮 48 pair / 96 次假 provider 调用全部 valid；
- 未读取配置、密钥、网络、ground truth 或 `game._state`。

假 provider 的 changed=48 是刻意选择首/末候选的接线结果，不得用于真实模型结论。

## 二、c3a 实现检查点

首先：

1. 运行 `git status --short`；
2. 确认除上述两个未跟踪文件外无其他改动；
3. 运行：

```bash
python -m unittest tests.test_confidence_action_ablation -q
python -m unittest tests.test_confidence_action_ablation tests.test_confidence_prompt_benchmark tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence tests.test_deepseek_prompt_step_h tests.test_pass_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

4. 预期 6 / 76 / 357 项通过；
5. 只暂存上述两个文件；
6. 提交名：`J-D1c3c2c3a paired action ablation harness`；
7. 记录完整提交 SHA；
8. 确认 `git status --short` 为空。

若存在其他无法归属的改动，停止并报告 `precondition_failed`。不要 stash、还原、清理或混入提交。

## 三、网络授权门槛

提交和回归通过后，只读取非敏感配置元数据：

- API key 是否存在，仅输出 yes/no；
- `DEEPSEEK_BASE_URL` 的 scheme 与 host，不输出 query、userinfo 或 key；
- `DEEPSEEK_MODEL`；
- 本步骤固定 `timeout_seconds=60`；
- 本步骤固定 `max_retries=0`；
- 最大 logical/physical HTTP requests = 48；
- 完整最坏超时窗口为 48 x 60 秒，不包含本地采集时间。

要求：

- 不输出、散列、复制或持久化 API key；
- base URL 必须为 HTTPS 且 host 非空，否则停止 `precondition_failed`；
- model 必须非空；
- key 不存在时停止 `precondition_failed`；
- 在发出任何请求前，把 host、model、timeout、retries 和 48 次上限报告给用户；
- 明确询问用户是否授权本次外部网络调用及调用上限；
- 只有用户在当前任务中明确同意后才可继续；不得把本提示词本身视为授权。

未获得授权时，停止并输出唯一状态：

```text
authorization_required
```

此时不要创建 live runner，不要发起探测请求或“测试连接”。

## 四、允许的运行边界

获得授权后：

- 不修改任何仓库文件；
- 不修改 `.env`、config、timeout、model 或 base URL；
- 不调用 `DeepSeekAIAgent.select_action()`；
- 不启用 CLI 或完整 DeepSeek 对局；
- 只在仓库外创建临时 runner、ledger、aggregate report 和 summary；
- provider 必须包装一个 `DeepSeekClient(..., timeout_seconds=60, max_retries=0).suggest_action_id`；
- wrapper 每次只调用底层 provider 一次；
- provider 返回后立即丢弃 reasoning，只向 harness 返回相同 action_id 和 `reasoning=None`；
- `verbose=False`，不得打印请求 prompt、模型 reasoning、响应正文或 action ID。

网络命令如需沙箱外权限，必须使用正常审批流程，不得绕过。

## 五、仓库外审计目录

创建全新的仓库外目录，例如：

```text
%TEMP%\guandan-confidence-action-live-c3b-<HEAD前12位>
```

若目录已存在且非空，不得覆盖或删除旧证据，改用新的明确目录。

目录至少包含：

- `run_live_action_ablation.py`
- `call_ledger.jsonl`
- `report.json`
- `audit_summary.json`

记录 runner 的绝对路径、字节数和 SHA-256。runner 文件不得包含 API key 或其散列。

正式运行前用 sentinel 文件验证 UTF-8 写入、flush、`os.fsync()`、原子替换、重新读取和 SHA-256。sentinel 失败时停止，不得发起请求。

## 六、逐调用 ledger

audited provider 在每个逻辑调用结束或抛异常后，立即向 `call_ledger.jsonl` 追加一行并执行 flush + `os.fsync()`。

每行只允许包含：

- schema version；
- 从 1 开始的连续 call index；
- condition：`off` 或 `on`，通过 kwargs 是否含 `card_confidence_prompt` 判定；
- elapsed milliseconds；
- outcome：`returned` 或 `exception`；
- returned action 是否为严格非 bool 整数；
- exception class 名称，成功时为空。

ledger 不得包含：

- seed、step、player 或样本 ID；
- observation、history、hand；
- prompt、legal/prompt actions；
- action ID；
- reasoning、响应正文或 SSE chunk；
- URL、Authorization header、API key；
- ground truth。

若进程中断，保留 ledger 作为失败证据，不得续跑、重跑或补采。

## 七、锁定 corpus 与请求参数

只运行一次：

```text
seeds = 13000..13009
strategic_pass_rates = 0,25,50,100
samples_per_bucket = 2
current_level_rank = 2
max_steps = 5000
max_samples_per_game = 128
max_external_cards = 12
max_search_nodes = 1,000,000
max_solutions = 100,000
timeout_seconds = 60
max_retries = 0
```

调用：

```python
run_confidence_action_ablation(
    tuple(range(13000, 13010)),
    suggestion_provider=audited_provider,
    strategic_pass_rates=(0, 25, 50, 100),
    samples_per_bucket=2,
    current_level_rank="2",
    max_steps=5000,
    max_samples_per_game=128,
    max_external_cards=12,
    max_search_nodes=1_000_000,
    max_solutions=100_000,
)
```

预期选择：4 策略 x 3 桶 x 2 = 24 pair；每 pair off/on 各一次，共 48 请求。每策略每桶必须 off-first=1、on-first=1。

不得第二次运行、补采、替换失败样本、调整 seed、增加重试或更换 model。

## 八、aggregate 持久化

`run_confidence_action_ablation()` 返回后立即：

1. 调用 `report.to_dict()`；
2. 使用 `ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")`、`allow_nan=False` 生成 canonical JSON；
3. 写临时文件、flush、`os.fsync()`，再原子替换为 `report.json`；
4. 重新读取并验证 UTF-8、JSON 结构、字节数和 SHA-256；
5. 不向 stdout 输出完整 report 或 JSON。

策略与 external bucket 必须按显式 name/rate 解析，不得依赖 canonical JSON 键顺序表达业务顺序。

## 九、数据完整性门槛

必须满足：

- 四策略顺序/映射为 forced-only、25、50、100；
- 每策略 requested/completed/incomplete = 10/10/0；
- forced active pass = 0；
- 25/50 满足 `0 < pass < opportunity`；
- 100 满足 `pass = opportunity > 0`；
- 实际 active-pass rate 严格递增；
- 每策略三个桶 qualified candidate 均至少 2；
- 每策略每桶 selected=2、off-first=1、on-first=1；
- overall selected=6；
- 四策略总 selected=24；
- 每策略和每桶 diagnostics 为空；
- duplicate、sample-limit、unexpected external 均为 0；
- ledger 恰好 48 行，index 连续 1..48；
- ledger off/on 各 24；
- aggregate off/on attempted 各 24；
- logical/physical requests 均不超过 48；
- report、ledger、runner 和 summary 均可重新读取和哈希；
- 运行后工作区干净。

任一失败均为 `live_benchmark_invalid`，不得重跑。

## 十、真实响应安全门槛

完整数据上必须满足：

- off/on exception = 0；
- off/on malformed result = 0；
- off/on no-action = 0；
- off/on invalid action type = 0；
- off/on outside legal = 0；
- off/on outside prompt = 0；
- 四策略总 both-valid pair = 24；
- only-off-valid / only-on-valid / neither-valid = 0；
- same-action + changed-action = 24；
- pass/pressure 计数满足各自不超过 valid response count。

这些门槛只验证模型响应和候选边界。不得把 fallback 结果计为模型 valid；harness 不使用 fallback。

## 十一、描述性动作结果

完整报告以下指标，但不设置事后收益阈值：

- 四策略和三个 external bucket 的 same/changed；
- off/on pass selection；
- off/on pressure selection；
- prompt pair digest；
- off/on ledger latency sum/min/max；
- condition 与调用顺序分布。

解释边界：

- changed=0：当前 pilot 未观察到 confidence 改变动作；
- changed>0：只说明不同 prompt 条件下观察到不同动作；
- 单次 off/on 不能排除服务非确定性，即使 `temperature=0`；
- pass/pressure 变化不等于动作更优或更差；
- 不读取 ground truth，不运行后续对局，因此没有胜率结论。

## 十二、audit summary

从落盘 `report.json` 和 `call_ledger.jsonl` 生成 `audit_summary.json`，至少包含：

- schema/version；
- 完整 HEAD 和 c3a commit；
- sanitized host、model、timeout、retries 和锁定参数；
- runner/report/ledger 的路径、字节数和 SHA-256；
- 实际请求数和耗时聚合；
- 四策略行为与 corpus 完整性；
- 四策略/三桶全部响应分类、same/changed、pass/pressure；
- 每项门槛 pass/fail；
- 唯一判定。

原子写入后重新解析并记录 summary 字节数与 SHA-256。不得包含逐样本或模型文本。

## 十三、运行后回归

正式运行后再次运行：

```bash
python -m unittest tests.test_confidence_action_ablation -q
python -m unittest tests.test_confidence_action_ablation tests.test_confidence_prompt_benchmark tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence tests.test_deepseek_prompt_step_h tests.test_pass_policy_benchmark -q
python -m unittest discover -q
git diff --check
git status --short
```

必须仍为 6 / 76 / 357 项通过且工作区干净，否则判定 `live_benchmark_invalid`。

## 十四、唯一判定

严格按顺序只输出一个：

1. 未获网络/调用上限授权：`authorization_required`；
2. 提交、回归、配置、HTTPS、审计、传输、请求上限、corpus 或工作区完整性失败：`live_benchmark_invalid`；
3. 数据完整但任一真实响应安全门槛失败：`reject_confidence_prompt_live_response`；
4. 响应安全全部通过且 changed=0：`no_observed_confidence_action_effect`；
5. 响应安全全部通过且 changed>0：`retain_for_action_quality_evaluation`。

`retain_for_action_quality_evaluation` 只授权下一步设计动作质量评估。它不证明 confidence 导致动作变化，不授权默认开启，也不代表胜率提升。

## 十五、最终报告

最终必须报告：

1. c3a 提交 SHA 和提交范围；
2. 运行前后工作区、回归与 `git diff --check`；
3. 用户授权的 host/model/timeout/retries/请求上限，不含 key；
4. 审计目录和 runner/report/ledger/summary 的路径、字节数、SHA-256；
5. 实际耗时和逻辑/物理请求数；
6. 四策略 games、strategic-pass 行为和 qualified/selected；
7. 每策略/每桶 AB/BA、响应分类和守恒；
8. same/changed、pass/pressure 与 latency；
9. 所有完整性和响应安全门槛；
10. 唯一判定；
11. 明确说明未输出密钥、prompt、action ID、reasoning 或响应原文；
12. 明确说明未运行完整 DeepSeek 对局、未形成动作质量或胜率结论。

完成后停止，不修改 docs，不扩展到 J-D1c3c2c3c。
