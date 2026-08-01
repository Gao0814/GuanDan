# 下一步实施提示词

## Step J-D1c3c2c3c2：真实 DeepSeek 动作质量验收

请在 GuanDan 项目中执行 Step J-D1c3c2c3c2。任务是使用已完成的 evaluation-only 质量载体，在全新 critical-endgame 语料上成对请求 confidence-off/on 动作，并用固定 RuleBased 后续推进到终局，形成有界、可审计的动作质量代理结论。

本步骤不修改 runtime、engine、prompt、confidence、RAG 或策略逻辑。它不是完整 DeepSeek 对局，也不能证明 confidence 的因果效果或胜率提升。

## 一、前置结论

c3a 检查点：

```text
e0065c6a3da70b3d4ded4b394817bfab3351c113
J-D1c3c2c3a harness
```

c3b 唯一判定：

```text
retain_for_action_quality_evaluation
```

c3c1 唯一开发判定：

```text
confidence_action_quality_harness_verified
```

c3c1 关键事实：

- 仅新增 `evaluation/confidence_action_quality.py` 和 `tests/test_confidence_action_quality.py`；
- c3a seed `120..129` 兼容 SHA-256 仍为 `ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`；
- c3c1 seed `140..149` 双运行 SHA-256 为 `3a989255412180b293afcd9f99a8a32d6d399c891d829bd16d37e94b5f64eaa6`；
- 24 pair 全部 both-valid、quality-evaluable，48 个分支全部完成；
- 假 provider 下 on-better/off-better/tie = 3/1/20，只验证载体；
- 新模块 5 项、相关 81 项、全量 362 项测试通过。

## 二、先建立 c3c1 检查点

开始前检查工作区，只允许存在以下两个 c3c1 文件：

```text
evaluation/confidence_action_quality.py
tests/test_confidence_action_quality.py
```

先运行：

```bash
python -m unittest tests.test_confidence_action_quality -q
python -m unittest tests.test_confidence_action_quality tests.test_confidence_action_ablation tests.test_confidence_prompt_benchmark tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence tests.test_deepseek_prompt_step_h tests.test_pass_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

确认结果仍为 5 / 81 / 362 项通过，并重验两个 canonical SHA-256。然后只暂存并提交这两个文件，提交名：

```text
J-D1c3c2c3c1 confidence action quality harness
```

不得把 `docs/` 或其他文件带入该提交。提交后确认工作区干净，并记录完整 HEAD。

若文件范围、测试、兼容 hash 或工作区任一不满足，停止并输出 `precondition_failed`，不得联网。

## 三、授权门槛

只读取非敏感配置元数据，确认：

- API key 是否存在，只报告存在/缺失；
- endpoint；
- model；
- timeout；
- retries；
- 本次 logical/physical request 上限。

预期锁定值：

```text
endpoint = https://api.deepseek.com
model = deepseek-v4-pro
timeout = 60 seconds
retries = 0
max logical requests = 48
max physical HTTP requests = 48
```

不得输出、复制、散列或持久化 API key。不得发送探测请求。

必须向用户明确询问是否授权本次最多 48 次、60 秒 timeout、零重试的外部请求。以前 c3b 的授权不自动延续到本步骤。未得到明确授权时停止，唯一状态为 `authorization_required`。

## 四、仓库边界

授权后不得修改任何仓库文件。live runner、ledger、report 和 audit summary 必须写入仓库外新目录，例如：

```text
%TEMP%\guandan-confidence-action-quality-c3c2-<checkpoint-prefix>
```

不得修改：

- `engine/`
- `agents/`
- `evaluation/`
- `tests/`
- `cli/`
- `rag/`
- `config.py`
- `.env` / `.env.example`
- `docs/`

不得安装依赖，不得调整模型、prompt、采样逻辑、质量字典序或门槛。

## 五、正式锁定参数

只运行一次正式语料，不做双运行，不补采，不替换失败样本：

```text
seeds = 15000..15009
strategic_pass_rates = 0,25,50,100
samples_per_bucket = 2
current_level_rank = 2
max_steps = 5000
max_samples_per_game = 128
max_external_cards = 12
max_search_nodes = 1,000,000
max_solutions = 100,000
max_rollout_steps = 5000
timeout = 60 seconds
retries = 0
```

调用 `run_confidence_action_quality(...)`，provider 使用现有 `DeepSeekClient.suggest_action_id()`。不得创建完整 DeepSeek 对局；只有入选的 24 pair 调用模型，后续分支只用 `RuleBasedAIAgent`。

每策略每桶固定选择 2 个样本，共 4 策略 × 3 桶 × 2 = 24 pair。off/on 各请求一次，因此最多 48 次 logical/physical HTTP 请求。达到上限后 fail-closed，禁止额外请求。

## 六、配对和质量契约

必须原样沿用 c3a/c3c1：

- 只采集 `critical_endgame` 和公开 observation/legal actions；
- external 0-4、5-8、9-12 三个互斥桶；
- SHA-256 固定样本优先级；
- only-pass、一次出完、confidence unavailable、payload omitted、prompt mismatch 不调用 provider；
- off/on kwargs 唯一差异为类型化 `card_confidence_prompt`；
- 每桶 AB/BA 各 1，第一侧失败仍调用另一侧；
- 不使用 fallback；响应按 exception、malformed、no-action、类型、outside legal/prompt 分类；
- 非 both-valid pair 不 rollout；
- same action 单分支复用，changed action 双分支独立运行；
- rollout 只使用 clone 的公开接口和独立 RuleBased agents；
- 终局只使用公开 winner 和 `history.finish_order`；
- 比较顺序固定为团队 outcome score，其次团队完赛位置和，其余 tie；
- 步数、pass、pressure、reasoning 不得打破 tie。

不得读取或写入 `game._state`，不得读取 ground truth，不得保存逐样本 action ID。

## 七、仓库外审计证据

至少持久化：

1. `run_live_action_quality.py`：本次固定 runner；
2. `call_ledger.jsonl`：连续请求账本；
3. `report.json`：`ConfidenceActionQualityReport.to_dict()`；
4. `audit_summary.json`：参数、完整性门槛、质量判定和文件哈希。

ledger 每行只允许包含：

- 连续 request index；
- condition：off/on；
- AB/BA 调用位置；
- latency milliseconds；
- success/failure 分类。

不得持久化或输出：

- API key；
- prompt、observation、history；
- action ID、legal/prompt action 内容；
- reasoning、响应正文；
- seed 列表、样本 ID、step/player；
- 手牌、ground truth、clone 或逐分支 winner/finish order。

对 runner、ledger、report、summary 报告 bytes 与完整 SHA-256。JSON 使用 canonical `sort_keys=True`、紧凑分隔符和 `allow_nan=False`。业务策略顺序按固定策略名/rate 映射复核，不依赖 JSON 键迭代顺序。

即使请求或 rollout 失败，也必须先尽可能写完 ledger 和失败摘要，再停止；不得通过重跑覆盖证据。

## 八、完整性硬门槛

以下全部满足才进入质量判定：

- checkpoint 后、正式运行前后工作区均干净；
- 四策略名称/rate 映射正确，均为 10/10/0 games；
- 每策略三个桶各 selected=2，overall=6，总计 24 pair；
- 每桶 off-first/on-first 各 1；
- ledger index 连续 1..48，off/on 各 24；
- logical/physical requests = 48/48，retries=0；
- provider exception、malformed、no-action、非法类型、outside legal/prompt 全部为 0；
- 24 pair 全部 both-valid；
- quality-evaluable=24、unevaluable=0；
- branch attempted = `changed * 2 + same`；
- 所有 attempted branch complete，failed=0；
- clone、initial action、rollout、step limit、terminal diagnostics 全部为 0；
- `same + changed = 24`；
- `on_better + off_better + tie = 24`；
- off/on win+draw+loss 各为 24；
- overall 与三个桶、四策略原始整数守恒；
- report/summary 可 canonical JSON 序列化且无 NaN/Infinity；
- 审计文件存在、非空、哈希可复核且无敏感内容。

任一失败，唯一判定 `quality_benchmark_invalid`。不得用部分样本形成质量结论，不得重跑或补采。

## 九、预注册质量判定

完整性全部通过后，只使用 overall 聚合，按以下顺序给出唯一判定：

1. 若 `on team win count < off team win count`，或 `on_better < off_better`：`reject_confidence_action_quality`；
2. 否则若 `on_better == off_better`：`no_observed_action_quality_gain`；
3. 否则，即 `on_better > off_better` 且 `on team win count >= off team win count`：`retain_for_full_game_evaluation`。

同时报告四策略和三个 external bucket 的 on-better/off-better/tie、off/on win/draw/loss、placement totals 和 rollout steps，但不得事后增加分桶否决或改变 overall 门槛。

样本仅 24 对，且 off/on 是两次独立模型请求，服务非确定性仍是混杂因素。因此：

- `reject` 只表示该固定代理下不应继续接入；
- `no_observed` 只表示未观察到净质量增益；
- `retain` 只授权设计完整 DeepSeek 对局评估；
- 任何判定都不证明 confidence 因果效果或胜率变化，不允许默认开启 confidence。

## 十、运行后验证

正式运行后再次执行：

```bash
python -m unittest tests.test_confidence_action_quality -q
python -m unittest tests.test_confidence_action_quality tests.test_confidence_action_ablation tests.test_confidence_prompt_benchmark tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence tests.test_deepseek_prompt_step_h tests.test_pass_policy_benchmark -q
python -m unittest discover -q
git diff --check
git status --short
```

并扫描确认仓库中没有新增 live runner、ledger、report、key、prompt、响应或反向依赖。

## 十一、最终报告

完成后报告：

1. c3c1 检查点完整 HEAD 和提交范围；
2. 运行前后工作区、5/81/362 回归、两个兼容 hash；
3. 实际 endpoint/model/timeout/retries 和授权边界；
4. 正式参数、总耗时、logical/physical request 数；
5. 仓库外证据目录、各文件 bytes 与完整 SHA-256；
6. 四策略 opportunity/active pass、games、qualified 和 selected；
7. ledger 连续性、off/on 请求数、延迟 sum/min/max；
8. provider 合法性和 pair 完整性；
9. same/changed、branch complete/failed 和 rollout diagnostics；
10. overall、四策略、三桶的 on-better/off-better/tie；
11. off/on win/draw/loss、placement totals 和 rollout steps；
12. 所有守恒与隐私扫描；
13. 唯一判定；
14. 明确说明未运行完整 DeepSeek 对局、未证明因果效果或胜率提升、未默认开启 confidence。

完成后停止，不修改 docs，不扩展到完整对局评估。
