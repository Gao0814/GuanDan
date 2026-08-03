# 下一步实施提示词

## Step K-A2b2a：策略路由独立语料扩容恢复验收

请在 GuanDan 项目中完成 Step K-A2b2a。K-A2b2 的结构完整性、守恒和语义覆盖均通过，但 forced-only、25%、50% 策略的 endgame available 样本分别为 583、660、663，未达到预注册 700 门槛。本步只使用全新 seed 将语料扩大到每策略 200 局；不得降低门槛、修改实现或重用失败语料。

### 1. 前置条件

1. HEAD 必须包含 K-A2b1a 检查点 `7f014db0c871a6ff851ab331e4ef4f19c357a909`，且关键实现相对该检查点无差异。
2. 运行前执行 `git status --short`，工作区必须为空。
3. 若工作区不干净，立即停止并唯一报告 `precondition_failed`；不要 stash、还原、提交或清理现有改动。
4. 确认以下文件未修改：
   - `evaluation/strategy_router_benchmark.py`
   - `tests/test_strategy_router_benchmark.py`
   - `agents/strategy_router.py`
   - `agents/deepseek_ai.py`
5. 正式运行前、后都执行：

```text
python -m unittest tests.test_strategy_router_benchmark -q
python -m unittest tests.test_strategy_router_benchmark tests.test_strategy_router_shadow tests.test_strategy_router tests.test_game_phase tests.test_hand_evaluator tests.test_pass_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

预期分别为 11、61、407 项通过。任一回归失败，不得启动或继续正式 benchmark。

### 2. 锁定参数

- 永久排除 K-A2b2 的 seed `16000..16099`；
- 新 seeds：`17000..17199`；
- policy rates：`(0, 25, 50, 100)`，保持调用顺序；
- 每个策略 200 局，策略之间使用独立 game、agent、样本集合和聚合状态；
- `current_level_rank=2`；
- `max_steps=5000`；
- `max_samples_per_phase_per_game=128`；
- 使用现有默认 `RuleBasedAIAgent` / `StrategicPassAIAgent` 推进；
- phase、intent、reason、relation、采样顺序、跳过规则和全部 K-A2b2 门槛保持不变。

### 3. 运行次数

1. 正式 benchmark 完整运行恰好两次。
2. 正式运行前先在仓库外 runner 中完成 import、参数和输出目录 smoke check；smoke check 不得调用 `run_strategy_router_benchmark()`。
3. 一旦第一次正式 benchmark 开始，不得第三次运行、补采、改 seed、调阈值、替换策略或事后筛样本。
4. runner 只能在仓库外修改。仓库内不得新增、修改或删除任何文件。

### 4. 审计证据

在仓库外创建：

```text
%LOCALAPPDATA%\Temp\guandan-strategy-router-k-a2b2a-<short-head>-<run-id>
```

至少保留：

- runner；
- `run1.json`、`run2.json` 两份完整 canonical JSON；
- `audit_summary.json`；
- 包含文件 bytes 和 SHA-256 的 `manifest.json`。

要求：

- 不依赖标准输出保存正式数据；
- 两次 report、`to_dict()`、canonical JSON 完全相等；
- 两份 canonical JSON 逐字节相同且 SHA-256 相同；
- 策略必须按固定名称和 rate 显式 lookup，不依赖 JSON 键序；
- audit summary 分开输出 `structural_integrity_pass` 与 `coverage_pass`，不能把覆盖门槛失败混称为结构完整性失败；
- JSON 可解析且无 NaN/Infinity；
- 不保留 seed 列表、样本 ID、observation、action、玩家、手牌或逐样本内容。

### 5. 结构完整性门槛

四个策略都必须满足：

- games 为 `200 / 200 / 0`；
- `unavailable=0`、`invalid=0`、`duplicate=0`、`sample_limit=0`；
- 顶层、overall 和全部 phase diagnostics 为空；
- `sample = available + unavailable + invalid`；
- available 的 intent、reason、relation、free/follow、weak/nonweak 分别守恒；
- `observed = only_pass + finishing + opening + eligible`；
- `eligible = duplicate + sample_limit + evaluated`；
- overall 等于四个 phase 的原始整数和；
- forced-only 主动 pass 为 0；
- strategic-pass-100 主动 pass 等于 opportunity；
- 四策略实际主动 pass 比例严格递增。

### 6. 原覆盖门槛

不得随 200 局扩容提高或降低 K-A2b2 的绝对门槛。

每个策略的 phase available 最低门槛：

| phase | 最低 available 样本 |
|---|---:|
| `midgame` | 700 |
| `endgame` | 700 |
| `near_open_endgame` | 500 |
| `critical_endgame` | 1000 |

每个策略 overall 的 `run_out`、`block_opponent`、`support_teammate`、`control` 均至少 400。

分阶段 intent：

- `midgame`：`run_out`、`support_teammate`、`control` 大于 0，`block_opponent` 可为 0；
- `endgame`：`run_out`、`support_teammate`、`control` 大于 0，`block_opponent` 可为 0；
- `near_open_endgame` 与 `critical_endgame`：四种 intent 都大于 0。

每个策略 × 每个 phase 的 relation `none / teammate / opponent` 都必须大于 0。

每个策略 overall reason：

- `can_finish_now == 0`；
- `weak_hand`、`stable_control`、`teammate_controls_table`、`urgent_opponent_controls_table`、`teammate_more_urgent`、`opponent_more_urgent`、`urgency_tie_block_opponent`、`opponent_urgent`、`teammate_urgent` 均大于 0。

### 7. 唯一判定

严格按以下顺序给出一个判定：

1. 前置条件或回归失败：`precondition_failed`；
2. 双运行、哈希、策略映射、结构完整性、守恒或审计证据失败：`strategy_router_coverage_recovery_invalid`；
3. 结构完整性全部通过，但任一原覆盖门槛仍失败：`strategy_router_coverage_still_insufficient`；
4. 全部门槛通过：`strategy_router_coverage_verified`。

`strategy_router_coverage_verified` 只授权下一步单独设计 K-A3a intent 消费消融载体；不授权直接把 intent 接入 DeepSeek prompt、RAG、剪枝、fallback 或动作选择，不启用默认开关，也不代表动作质量或胜率提升。

### 8. 最终报告

必须报告：

- 唯一判定；
- HEAD、检查点、运行前后工作区状态；
- 11/61/407 回归与 `git diff --check`；
- 锁定参数、两次耗时、审计目录；
- 所有证据文件 bytes/SHA-256 和 canonical report SHA-256；
- 四策略 games、opportunity/active pass、结构完整性与 diagnostics；
- 4 策略 × 4 phase 的 sample/available、四 intent、三 relation；
- 每个策略 overall 的完整 reason 原始计数；
- 原 273 项门槛口径下的通过/失败总数和失败项；
- 明确说明未修改仓库、未联网、未读取隐藏状态，且未形成动作质量或胜率结论。
