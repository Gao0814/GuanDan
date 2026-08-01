# 下一步实施提示词

## Step J-D1c3c2c3c2a：耐久后台真实动作质量恢复验收

请在 GuanDan 项目中执行 Step J-D1c3c2c3c2a。任务是在不改变模型、采样、请求上限、质量代理和判定门槛的前提下，用全新独立语料恢复一次正式 DeepSeek 动作质量验收，并通过单一后台进程与可持续轮询避免再次被 30 分钟外层执行时限截断。

本步骤不修改任何仓库文件。旧 c3c2 结果永久保持 `quality_benchmark_invalid`，不得恢复、补采、拼接或进入新报告。

## 一、前置事实

c3c1 检查点：

```text
ad85662a47f126991e8ebe0360dc0c6c4a2f1be6
J-D1c3c2c3c1 confidence action quality harness
```

c3c1 开发判定：

```text
confidence_action_quality_harness_verified
```

首次 c3c2 正式运行：

```text
seeds = 15000..15009
verdict = quality_benchmark_invalid
```

失败事实：

- endpoint/model：`https://api.deepseek.com` / `deepseek-v4-pro`；
- timeout 60 秒、retries 0、请求上限 48；
- 外层执行器在 30 分钟中断，随后终止仍运行的子进程；
- ledger 只有连续 45 条，off/on=23/22，全部 returned 且为严格整数；
- 未生成完整 `report.json`，不得报告 same/changed、rollout 或质量结果；
- 本地 5 / 81 / 362 项测试通过，工作区干净。

旧证据目录：

```text
C:\Users\86166\AppData\Local\Temp\guandan-confidence-action-quality-c3c2-ad85662a47f1-0f1b1b08851742fea86a9965e8617154
```

旧证据 SHA-256：

- runner：`ffcc5448ea7ff5b960c58869db0c1e6d34f8eac621de425a11f56332ac4bb7a6`；
- ledger：`908fbd2e05f2c1d85e3092c4f72054ccdd810ff2c669324c15d0cf516a9d08ab`；
- failure summary：`4475786a589534b77ef8421f8f614753d1be7f9665e175312bae6396464af250`。

不得修改或覆盖该目录，不得从旧 ledger 推断缺失请求或逐样本结果。

## 二、前置检查

确认：

```bash
git rev-parse HEAD
git status --short
python -m unittest tests.test_confidence_action_quality -q
python -m unittest tests.test_confidence_action_quality tests.test_confidence_action_ablation tests.test_confidence_prompt_benchmark tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence tests.test_deepseek_prompt_step_h tests.test_pass_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

硬门槛：

- HEAD 必须包含 `ad85662a47f126991e8ebe0360dc0c6c4a2f1be6`，且该检查点后的 `evaluation/confidence_action_quality.py`、`tests/test_confidence_action_quality.py` 和 c3a 实现不得有差异；
- 工作区必须干净；
- 测试必须仍为 5 / 81 / 362 项通过；
- c3a seed `120..129` canonical SHA-256 必须仍为 `ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`；
- c3c1 seed `140..149` canonical SHA-256 必须仍为 `3a989255412180b293afcd9f99a8a32d6d399c891d829bd16d37e94b5f64eaa6`。

任一失败，停止并输出 `precondition_failed`，不得联网。

## 三、重新授权

只读取非敏感配置元数据，报告 API key 存在/缺失，不得输出、复制、散列或持久化 key。

必须向用户重新确认本次授权：

```text
endpoint = https://api.deepseek.com
model = deepseek-v4-pro
timeout = 60 seconds
retries = 0
max logical requests = 48
max physical HTTP requests = 48
single durable process deadline = 65 minutes
```

首次 c3c2 的授权不自动延续。未获得明确授权时停止，唯一状态为 `authorization_required`。不得发送探测请求。

## 四、仓库和隐私边界

授权后不得修改任何仓库文件，不得创建提交。所有 runner、进程状态和审计文件写入全新仓库外目录：

```text
%TEMP%\guandan-confidence-action-quality-c3c2a-ad85662a47f1-<unique-id>
```

不得修改：

- `engine/`、`agents/`、`evaluation/`、`tests/`；
- CLI、RAG、config；
- `.env` / `.env.example`；
- `docs/`。

不得持久化或输出：

- API key；
- prompt、observation、history；
- action ID 或 action 内容；
- reasoning、响应正文；
- 样本 ID、step/player；
- 手牌、ground truth、clone 或逐分支终局明细。

## 五、锁定参数

本次是一次全新的正式运行，不是旧运行续跑：

```text
seeds = 16000..16009
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
max requests = 48
```

调用现有 `run_confidence_action_quality(...)`，provider 使用现有 `DeepSeekClient.suggest_action_id()`。只对 24 个入选 pair 调用模型；后续分支全部使用本地 `RuleBasedAIAgent`。不运行完整 DeepSeek 对局。

不得调整 seed、样本数、模型、prompt、temperature、候选、AB/BA、rollout、质量字典序或判定门槛。

## 六、耐久后台执行协议

在仓库外创建固定 runner，并用 `Start-Process -WindowStyle Hidden` 启动唯一子进程。不得直接用一个 30 分钟前台命令承载完整 benchmark。

启动前原子写入 `process_state.json`，至少记录：

- 唯一 run ID；
- checkpoint；
- 参数摘要；
- `starting` 状态；
- 启动时间。

子进程启动后记录 PID 并切换为 `running`。runner 每次请求完成后原子更新 `heartbeat.json`，仅含：

- run ID 和 PID；
- 当前连续 request count；
- off/on count；
- 最近更新时间；
- `running` 状态。

执行要求：

1. 全程只允许一个匹配 run ID 的子进程；
2. 启动命令返回不代表 benchmark 结束；
3. 外层每 30-60 秒轮询同一 PID、heartbeat 和完成标记；
4. 单次工具等待超时、上下文续接或 30 分钟界面时限不得触发第二次启动；
5. 状态不明时先检查 PID 和仓库外状态文件，不得猜测进程已结束；
6. 子进程仍存活时继续等待，不得发送最终报告；
7. 只有用户明确停止、进程异常退出或从启动时间起达到 65 分钟，才允许终止；
8. 达到 65 分钟后终止同一 PID，生成失败审计，判 `quality_recovery_invalid`；
9. 不得因为已接近 48 条而补发手工请求；
10. 不得启动第二次正式运行。

runner 成功结束时先原子写 `report.json`，再写 `audit_summary.json`，最后写 `completion.json`。`completion.json` 是唯一成功完成标记；只有进程退出且该文件存在并通过校验，才能进入质量判定。

如果外层任务发生自动续接，必须继续轮询已有 PID，不得重新执行 runner。

## 七、审计文件

新目录至少包含：

1. `run_live_action_quality.py`；
2. `process_state.json`；
3. `heartbeat.json`；
4. `call_ledger.jsonl`；
5. `report.json`；
6. `audit_summary.json`；
7. `completion.json`。

失败时 `report.json` 和 `completion.json` 可以不存在，但必须生成 `failure_audit_summary.json`。

ledger 每行仅含连续 request index、off/on、AB/BA 位置、latency ms 和结果分类。所有 JSON 使用 `allow_nan=False`；最终 report 使用 canonical `sort_keys=True` 和紧凑分隔符。

最终报告每个文件的 bytes 和完整 SHA-256。策略顺序按固定名称/rate 映射复核，不依赖 JSON 键顺序。

## 八、完整性门槛

以下全部满足才进入质量判定：

- 唯一子进程正常退出；
- `completion.json` 存在且 run ID、PID、checkpoint、参数与其他文件一致；
- 四策略均为 10/10/0 games；
- 每策略三个桶各 selected=2，overall=6，总计 24 pair；
- 每桶 off-first/on-first 各 1；
- ledger 连续 1..48，off/on 各 24；
- logical/physical requests=48/48，retries=0；
- provider exception、malformed、no-action、非法类型、outside legal/prompt 全为 0；
- 24 pair 全部 both-valid；
- quality-evaluable=24、unevaluable=0；
- `same + changed = 24`；
- branch attempted=`same + 2 * changed`；
- 全部分支 complete，failed=0；
- clone、initial action、rollout、step-limit、terminal diagnostics 全为 0；
- `on_better + off_better + tie = 24`；
- off/on win+draw+loss 各为 24；
- overall、三桶和四策略原始整数全部守恒；
- report/summary/completion 可 JSON 序列化且无 NaN/Infinity；
- 仓库外文件存在、非空、哈希可复核且通过敏感内容扫描；
- 运行后仓库仍干净，5 / 81 / 362 项测试与 `git diff --check` 仍通过。

任一失败，唯一判定 `quality_recovery_invalid`。不得使用部分数据形成质量结论，不得重跑或补采。

## 九、质量判定

完整性全部通过后，只使用 overall 聚合，沿用 c3c2 已预注册顺序：

1. `on team win count < off team win count`，或 `on_better < off_better`：`reject_confidence_action_quality`；
2. 否则若 `on_better == off_better`：`no_observed_action_quality_gain`；
3. 否则：`retain_for_full_game_evaluation`。

同时报告四策略和三个 external bucket 的 on-better/off-better/tie、off/on win/draw/loss、placement totals 和 rollout steps，但不得事后增加分桶否决规则。

只有第三个判定允许设计完整 DeepSeek 对局评估。任何判定都不允许默认开启 confidence，也不能证明 confidence 因果效果或胜率变化。

## 十、最终报告

完成后报告：

1. checkpoint、运行前后工作区和 5 / 81 / 362 回归；
2. 旧 c3c2 invalid 证据保持未触碰；
3. 本次授权的 endpoint/model/timeout/retries/request/deadline；
4. 新审计目录、run ID、PID、启动/结束时间和总耗时；
5. runner、state、heartbeat、ledger、report、summary、completion 的 bytes 与完整 SHA-256；
6. ledger 连续性、off/on 数量和延迟 sum/min/max；
7. 四策略 opportunity/active pass、games、qualified、selected；
8. provider 分类、both-valid、same/changed；
9. branch complete/failed、quality-evaluable 和 diagnostics；
10. overall、四策略、三桶的 on-better/off-better/tie；
11. off/on win/draw/loss、placement totals、rollout steps；
12. 全部守恒、JSON 和隐私扫描；
13. 唯一判定；
14. 明确说明未运行完整 DeepSeek 对局、未证明因果效果或胜率提升、未默认开启 confidence。

完成后停止，不修改 docs，不扩展到完整对局评估。
