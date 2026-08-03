# 下一步实施提示词

## Step K-A3c2：策略意图 prompt 独立语料正式覆盖验收

请在 GuanDan 项目中完成 Step K-A3c2。本步不修改仓库，只运行已封板的 `run_strategy_intent_prompt_benchmark()`，使用全新独立语料正式验证四策略×四阶段的 ready 覆盖、精确插入、字符成本和可重复性。不得调用 DeepSeek 或任何网络。

### 1. 前置条件

1. K-A3c1 实现必须形成独立检查点提交。
2. 记录 HEAD 和 K-A3c1 检查点。
3. 运行前执行 `git status --short`，工作区必须为空。
4. 若工作区不干净，立即停止并唯一报告 `precondition_failed`；不要 stash、还原、提交、清理或触碰现有改动。
5. 确认以下文件相对 K-A3c1 检查点无差异：
   - `evaluation/strategy_intent_prompt_benchmark.py`
   - `tests/test_strategy_intent_prompt_benchmark.py`
   - `agents/strategy_intent_prompt.py`
   - `agents/deepseek_ai.py`
   - `agents/deepseek_client.py`
6. 正式运行前、后都执行：

```text
python -m unittest tests.test_strategy_intent_prompt_benchmark -q
python -m unittest tests.test_strategy_intent_prompt_benchmark tests.test_strategy_intent_prompt_wiring tests.test_strategy_intent_prompt tests.test_strategy_router_benchmark tests.test_strategy_router -q
python -m unittest discover -q
git diff --check
```

预期基线为 6、52、430 项通过。任一回归失败，不得启动或继续正式 benchmark。

### 2. 锁定参数

- 永久排除开发 seed `300..309`；
- 正式 seeds：`18000..18199`；
- strategic-pass rates：`(0, 25, 50, 100)`，保持调用顺序；
- 每个策略 200 局，策略之间使用独立 game、agent、seen set、聚合器和 pair hasher；
- `current_level_rank=2`；
- `max_steps=5000`；
- `max_samples_per_phase_per_game=128`；
- phase、skip 顺序、router、formatter、剪枝、prompt pair 和字符预算全部保持不变。

不得修改 seed、策略、样本上限、字符预算、门槛或采样规则。

### 3. 运行次数

1. 在仓库外 runner 中先完成 import、参数、写权限与输出路径 smoke check；smoke check 不得调用 benchmark。
2. 正式 benchmark 完整运行恰好两次。
3. 第一次正式 benchmark 开始后，不得第三次运行、补采、改参数或事后筛样本。
4. runner 或审计脚本只能位于仓库外，不得创建或修改仓库文件。

### 4. 禁止边界

全程不得：

- 调用 `DeepSeekClient.suggest_action_id()`；
- 创建真实 DeepSeek client；
- 发起 HTTP 或其他网络请求；
- 读取 API key、`.env`、配置或环境变量；
- 读取 ground truth、`game._state`、隐藏手牌或 `record.txt`；
- 让 intent payload 影响对局推进动作；
- 修改 runtime 默认开关。

### 5. 仓库外证据

创建：

```text
%LOCALAPPDATA%\Temp\guandan-strategy-intent-prompt-k-a3c2-<short-head>-<run-id>
```

至少保留：

- runner；
- `run1.json`、`run2.json` 两份完整 canonical report；
- `audit_summary.json`；
- 包含所有证据文件 bytes 和 SHA-256 的 `manifest.json`。

要求：

- 不依赖标准输出保存正式数据；
- 两次 report、`to_dict()`、canonical JSON 完全相等；
- 两份 canonical JSON 逐字节相同且 SHA-256 相同；
- 策略按固定 name/rate 显式 lookup，不依赖 JSON 键序；
- audit 分开输出 `structural_integrity_pass` 与 `coverage_pass`；
- JSON 可解析且无 NaN/Infinity；
- report 不包含 seed、样本 ID、observation、action、prompt、玩家、手牌或逐样本结果。

### 6. 结构完整性门槛

四个策略都必须满足：

- games 为 `200 / 200 / 0`；
- unavailable、router invalid、payload invalid、omitted、duplicate、sample-limit 均为 0；
- ready/omitted pair mismatch 均为 0；
- 顶层、overall 和全部 phase diagnostics 为空；
- `sample = router_available + router_unavailable + router_invalid`；
- `router_available + router_unavailable = payload_ready + payload_omitted + payload_invalid`；
- `sample = router_invalid + payload_invalid + payload_ready + payload_omitted`；
- `payload_ready = exact_insertion + ready_pair_mismatch`；
- `payload_omitted = omitted_prompt_equal + omitted_pair_mismatch`；
- `observed = only_pass + finishing + opening + eligible`；
- `eligible = duplicate + sample_limit + evaluated`；
- overall 的所有 count、char sum 和 min/max 与四 phase 原始数据守恒；
- forced-only active pass 为 0；
- 100% active pass 等于 opportunity；
- 四策略实际主动 pass 比例严格递增。

### 7. 正式覆盖门槛

每个策略的 phase `sample = router_available = payload_ready = exact_insertion`，且至少达到：

| phase | 最低 ready 样本 |
|---|---:|
| `midgame` | 1400 |
| `endgame` | 900 |
| `near_open_endgame` | 1000 |
| `critical_endgame` | 1800 |

全部 16 个策略×阶段桶都必须：

- payload omitted/invalid 为 0；
- prompt pair mismatch 为 0；
- payload char sum >0；
- prompt delta sum 精确等于 `payload_char_sum + 9 * payload_ready_count`；
- prompt delta min/max 分别等于 payload min/max +9。

每个 policy 的现有 `prompt_pair_sha256` 必须非空且两次运行一致；不得要求或事后新增报告中不存在的 phase digest 字段。

字符边界保持 K-A3c1 固定文本理论范围：

| phase | payload 字符范围 | delta 字符范围 |
|---|---|---|
| `midgame` | 74..79 | 83..88 |
| `endgame` | 74..79 | 83..88 |
| `near_open_endgame` | 84..89 | 93..98 |
| `critical_endgame` | 83..90 | 92..99 |

每个 bucket 的实际 min/max 只需落在对应闭区间内，不要求一定命中区间两端。

### 8. 唯一判定

严格按以下顺序给出一个判定：

1. 前置条件或回归失败：`precondition_failed`；
2. 双运行、哈希、策略映射、结构守恒、pair、字符关系、审计证据或禁止边界失败：`strategy_intent_prompt_coverage_benchmark_invalid`；
3. 结构完整性全部通过，但任一 phase 最低 ready 样本门槛失败：`strategy_intent_prompt_coverage_insufficient`；
4. 全部门槛通过：`strategy_intent_prompt_coverage_verified`。

`strategy_intent_prompt_coverage_verified` 只授权下一步 K-A3d1 evaluation-only、provider 可注入的 off/on 动作消融载体；不授权真实 API、动作质量结论、RAG 路由、默认启用或胜率声明。

### 9. 最终报告

必须包含：

- 唯一判定；
- HEAD、K-A3c1 检查点、运行前后工作区状态；
- 6/52/430 回归与 `git diff --check`；
- 锁定参数、两次耗时、审计目录；
- 所有证据文件 bytes/SHA-256 和 canonical report SHA-256；
- 四策略 games、opportunity/active pass、skip、完整性与 diagnostics；
- 4 策略×4 phase 的 sample/ready/omitted、payload 和 delta 字符成本；
- 四个 policy pair digests；
- 全部结构和覆盖门槛逐项通过/失败；
- 明确说明未修改仓库、未联网、未读取隐藏状态，intent 未影响推进动作，且未形成动作质量或胜率结论。
