# 下一步实施提示词

## Step J-D1c3c2c3c2b：不可变证据只读恢复审计

请在 GuanDan 项目中执行 Step J-D1c3c2c3c2b。任务是只读复核 c3c2a 已落盘的完整证据，修正“canonical JSON 键迭代顺序被误当业务策略顺序”的审计方法，并在不修改原文件、不联网、不重跑模型的前提下判断现有 report 是否满足原预注册完整性与动作质量门槛。

c3c2a 的正式判定 `quality_recovery_invalid` 必须永久保留。本步骤产生新的恢复审计结论，不得覆盖、重写或冒充原 summary/completion。

## 一、源证据

仓库基线：

```text
source HEAD = ee3b3252b8f244feae0d74a784c3746ff3ff60c1
c3c1 checkpoint = ad85662a47f126991e8ebe0360dc0c6c4a2f1be6
```

c3c2a 运行事实：

```text
seeds = 16000..16009
run ID = 6999cb8cde244f0c96a95601c504062f
PID = 8728
elapsed = 1890.133 seconds
requests = 48/48
verdict = quality_recovery_invalid
```

源目录：

```text
C:\Users\86166\AppData\Local\Temp\guandan-confidence-action-quality-c3c2a-ad85662a47f1-699cabeb8ea448878a510de9c2fec30f
```

必须锁定以下源文件：

| 文件 | bytes | SHA-256 |
|---|---:|---|
| `run_live_action_quality.py` | 9708 | `c020860c67c2663c9ed87adda974774697c396d186b82c4f7547bbccebc33a5c` |
| `process_state.json` | 508 | `4a4ff3d487f3257fbc7d0a82392c04d3c9f5df9cabb667fa534a2be5359c2adc` |
| `heartbeat.json` | 219 | `33bba4c0a966dd88e0e9c1293dc783be346cba0c65e5744acb8de28269d3d6e3` |
| `call_ledger.jsonl` | 10263 | `c60f5d35d9ee907efd926c7e3f03ba5fdb918c463892da3f1abab6a6c2ee49df` |
| `report.json` | 15623 | `57df2cd1826f3e5226ab66cf2a7590f7158ec88c4843e0f7839672b3f3bb090f` |
| `audit_summary.json` | 21345 | `9d9522155bea9d3c0dc24d40c33d6b0f3872d4e5ed75c8788a8d154cc0f1a2ab` |
| `completion.json` | 916 | `cfed3329699e822a84313c0e92b0c3a1dbec2dd08956f3ae0e126d9fea0b25c6` |
| `postrun_explicit_mapping_validation.json` | 按实际读取报告 | `52bab7e2de283b48d76839be4926fd75597d66046078512d8c04c94c9c5d3229` |

首次 c3c2 的 45 条失败 ledger 目录不得读取、合并或参与本步骤。

## 二、前置检查

运行：

```bash
git status --short
git merge-base --is-ancestor ad85662a47f126991e8ebe0360dc0c6c4a2f1be6 HEAD
git diff ad85662a47f126991e8ebe0360dc0c6c4a2f1be6..HEAD -- evaluation/confidence_action_ablation.py evaluation/confidence_action_quality.py tests/test_confidence_action_ablation.py tests/test_confidence_action_quality.py
python -m unittest tests.test_confidence_action_quality -q
python -m unittest tests.test_confidence_action_quality tests.test_confidence_action_ablation tests.test_confidence_prompt_benchmark tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence tests.test_deepseek_prompt_step_h tests.test_pass_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

要求：

- 工作区干净；
- c3c1 checkpoint 是 HEAD 祖先；
- c3a/c3c1 implementation 和测试自 checkpoint 后无差异；
- 回归仍为 5 / 81 / 362 项通过；
- c3a/c3c1 canonical hashes 仍分别为 `ce3262ad...a9095` 与 `3a989255...eaa6`；
- 所有源文件存在、bytes 与完整 SHA-256 匹配。

任一失败，停止并输出 `precondition_failed`。本步骤不需要也不得请求网络授权。

## 三、只读边界

不得修改源目录中的任何文件。开始前和结束后都重新计算全部源文件 bytes/SHA-256，必须完全不变。

恢复验证器和输出写入新的仓库外目录：

```text
%TEMP%\guandan-confidence-action-quality-c3c2b-readonly-6999cb8c-<unique-id>
```

不得修改仓库，不得创建提交，不得读取 `.env`、API key 或 config，不得发起 HTTP/DeepSeek 请求。

不得输出或持久化 prompt、observation、action ID、reasoning、响应正文、手牌、ground truth 或逐样本终局明细。

## 四、显式策略映射

业务策略集合固定为：

```text
forced_only -> 0
strategic_pass_25 -> 25
strategic_pass_50 -> 50
strategic_pass_100 -> 100
```

验证器必须：

- 对 mapping 使用精确 key set 比较；
- 按上述固定名称逐项 lookup；
- 核对每个策略对象内部的 rate；
- 单独核对主动 pass 计数和比例严格递增；
- 不比较 Python dict/JSON object 的迭代顺序；
- 不把 `sort_keys=True` 后的字母序当作调用顺序或策略顺序。

预期主动 pass/opportunity：

```text
forced_only active pass = 0, rate = 0
strategic_pass_25 = 40 / 102
strategic_pass_50 = 59 / 98
strategic_pass_100 = 111 / 111
```

forced-only 的 opportunity 必须从 report 独立读取并验证为合法非负整数，不从其他策略推断。比例比较使用精确整数交叉乘法，不使用浮点近似。

## 五、原 summary 失败路径门槛

先递归枚举 `audit_summary.json` 中所有 false 检查路径，不得只读取顶层 `integrity_pass`。

允许恢复的唯一情况是：

1. 恰好一个原子失败检查表示策略顺序不等；
2. 该失败可由 canonical JSON 键排序与业务顺序混淆完整解释；
3. 顶层或聚合 `integrity_pass=false` 只是该原子失败的派生结果；
4. 原 summary 中没有第二个独立失败检查；
5. addendum 的 source hashes、run ID、显式映射与独立验证一致。

必须在 recovered summary 中记录原子 false path 和派生 false path。不得按宽泛字符串匹配忽略失败，也不得直接信任 addendum 的结论。

若存在任何其他失败、未知字段、无法解释的 false path 或 addendum 不一致，判 `recovered_audit_invalid`。

## 六、独立完整性重算

恢复验证器必须从 ledger/report/state/heartbeat/completion 独立重算，不复制原 summary 的最终布尔值。

至少验证：

- run ID、PID、checkpoint、参数和源 hashes 跨文件一致；
- PID 已退出，runner 正常完成；
- ledger index 连续 1..48，off/on=24/24；
- 每条状态为 returned，返回 action 为严格非 bool 整数的事实计数成立；
- logical/physical requests=48/48、retries=0；
- off/on latency sum=590242/1247160 ms，min/max 从 ledger 独立重算；
- 四策略均 10/10/0 games；
- 策略映射和主动 pass 计数符合第四节；
- 每策略每个 external bucket selected=2，overall=6，总计 24 pair；
- 每桶 off-first/on-first 各 1；
- provider exception、malformed、no-action、非法类型、outside legal/prompt 全为 0；
- 24 pair 全部 both-valid；
- quality-evaluable=24、unevaluable=0；
- `same + changed = 24`；
- branch attempted=`same + 2 * changed`；
- 全部分支 complete，failed=0；
- clone、initial action、rollout、step-limit、terminal diagnostics 全为 0；
- `on_better + off_better + tie = 24`；
- off/on win+draw+loss 各为 24；
- overall 等于三个 bucket 原始整数之和；
- 四策略合计等于全局原始整数；
- report、summary、completion 无 NaN/Infinity 且结构合法；
- 隐私扫描无敏感字段或内容。

任何守恒失败都判 `recovered_audit_invalid`，不得形成质量结论。

## 七、双验证确定性

使用同一个只读验证器完整运行两次。两次均从原源文件重新读取，不得以 run1 输出作为 run2 输入。

输出：

- `recover_readonly_audit.py`；
- `recovered_summary_run1.json`；
- `recovered_summary_run2.json`；
- `recovery_audit_manifest.json`。

recovered summary 不包含运行时间、随机 ID 或其他不稳定字段。两份对象、`to_dict` 等价结构、canonical JSON 和 SHA-256 必须完全一致。

若双验证不一致，判 `recovered_audit_invalid`。

## 八、质量判定

只有第五至第七节全部通过后，才允许从已验证的 report 读取 overall 聚合，并沿用 c3c2 原预注册顺序：

1. `on team win count < off team win count`，或 `on_better < off_better`：`reject_confidence_action_quality`；
2. 否则若 `on_better == off_better`：`no_observed_action_quality_gain`；
3. 否则：`retain_for_full_game_evaluation`。

同时报告 overall、四策略和三个 external bucket 的：

- selected、same/changed；
- on-better/off-better/tie；
- off/on win/draw/loss；
- placement totals；
- rollout steps；
- branch complete/failed 和 diagnostics。

不得事后增加分桶否决规则，不得读取逐样本动作解释质量差异。

`retain` 只允许设计完整 DeepSeek 对局评估，不允许默认启用 confidence，也不证明 confidence 因果效果或胜率提升。

## 九、最终验证

结束前：

- 再次复核所有源文件 hashes 未变；
- 复核运行前后仓库工作区干净；
- 再跑 5 / 81 / 362 项回归和 `git diff --check`；
- 对恢复目录执行敏感内容扫描；
- 报告恢复验证器及三个输出文件的 bytes 和完整 SHA-256。

## 十、唯一判定

严格只输出一个：

1. 任一前置、源 hash、失败路径、显式映射、完整性、双验证、JSON 或隐私门槛失败：`recovered_audit_invalid`；
2. 完整性恢复成功后，按第八节输出 `reject_confidence_action_quality`、`no_observed_action_quality_gain` 或 `retain_for_full_game_evaluation`。

原 c3c2a 的 `quality_recovery_invalid` 永远不被改写；本步骤的判定必须标明来自独立只读恢复审计。

## 十一、最终报告

完成后报告：

1. HEAD、checkpoint、工作区和 5 / 81 / 362 回归；
2. 源目录、八个文件 bytes/hashes 及前后不变证明；
3. 原 summary 的全部 false paths 及原子/派生分类；
4. addendum 的独立一致性检查；
5. 显式策略映射和主动 pass 精确计数；
6. ledger、请求、延迟、games、selected、provider、pair 和 rollout 守恒；
7. 双验证相等性与 recovered canonical SHA-256；
8. 新恢复目录和输出文件 bytes/hashes；
9. overall、四策略、三桶质量聚合；
10. 隐私与边界扫描；
11. 唯一判定；
12. 明确说明未联网、未调用模型、未修改原证据、未运行完整 DeepSeek 对局、未证明因果效果或胜率提升。

完成后停止，不修改 docs，不扩展到完整对局评估。
