# 下一步实施提示词

## Step K-A2b2：策略路由独立语料正式覆盖验收

请在 GuanDan 项目中完成 Step K-A2b2。本步只运行现有 `evaluation/strategy_router_benchmark.py`，验证 K-A2b1a 封板后的路由分布在全新独立语料上可重复、完整且覆盖非退化；不得修改任何仓库文件，也不得评价动作质量。

### 1. 前置条件

1. K-A2b1a 实现必须已形成独立检查点提交。
2. 运行前执行 `git status --short`，工作区必须为空。
3. 若工作区不干净，立即停止并唯一报告 `precondition_failed`；不要 stash、还原、提交、清理或触碰现有改动。
4. 记录 HEAD，并确认以下文件相对 K-A2b1a 检查点无差异：
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

预期基线分别为 11、61、407 项通过。任一回归失败，不得启动或继续正式 benchmark。

### 2. 锁定参数

- seeds：`16000..16099`；
- policy rates：`(0, 25, 50, 100)`，保持调用顺序；
- 每个策略 100 局，策略之间使用独立 game、agent、样本集合和聚合状态；
- `current_level_rank=2`；
- `max_steps=5000`；
- `max_samples_per_phase_per_game=128`；
- 只使用现有默认 `RuleBasedAIAgent` / `StrategicPassAIAgent` 推进；
- 完整运行恰好两次，不得第三次运行、补采、改 seed、调阈值或事后筛样本。

### 3. 执行与证据

1. 直接调用现有 `run_strategy_router_benchmark()`，不得复制、修改或替换载体逻辑。
2. 不调用 DeepSeek、HTTP 或其他网络，不读取 API key、`.env`、ground truth、`game._state`、`record.txt` 或隐藏手牌。
3. 在仓库外创建审计目录：

```text
%LOCALAPPDATA%\Temp\guandan-strategy-router-k-a2b2-<short-head>-<run-id>
```

4. 至少保留：runner、两份完整 canonical JSON 报告、`audit_summary.json` 和含 bytes/SHA-256 的 manifest。
5. 不依赖标准输出保存正式数据，避免工具截断；标准输出只显示短摘要和审计目录。
6. 两次 report、`to_dict()`、canonical JSON 必须完全相等，两份 canonical JSON 必须逐字节相同且 SHA-256 相同。
7. 策略复核必须按固定名称和 rate 显式 lookup，不能依赖 JSON mapping 的键迭代顺序。
8. 审计输出不得保留 seed 列表、样本 ID、observation、action、玩家、手牌或逐样本记录。

### 4. 数据完整性门槛

四个策略都必须满足：

- games 为 `100 / 100 / 0`；
- `unavailable=0`、`invalid=0`、`duplicate=0`、`sample_limit=0`；
- 顶层、overall 和全部 phase diagnostics 均为空；
- `sample = available + unavailable + invalid`；
- available 的 intent、reason、relation、free/follow、weak/nonweak 分别守恒；
- `observed = only_pass + finishing + opening + eligible`；
- `eligible = duplicate + sample_limit + evaluated`；
- overall 等于四个 phase 的原始整数和；
- forced-only 主动 pass 为 0；
- strategic-pass-100 主动 pass 等于 opportunity；
- 四策略实际主动 pass 比例严格递增。

每个策略的 phase 有效样本最低门槛：

| phase | 最低 available 样本 |
|---|---:|
| `midgame` | 700 |
| `endgame` | 700 |
| `near_open_endgame` | 500 |
| `critical_endgame` | 1000 |

### 5. 覆盖门槛

每个策略的 overall 中，四种 intent 均至少 400 个样本：

- `run_out`
- `block_opponent`
- `support_teammate`
- `control`

分阶段 intent 覆盖：

- `midgame`：`run_out`、`support_teammate`、`control` 必须大于 0；`block_opponent` 可为 0；
- `endgame`：`run_out`、`support_teammate`、`control` 必须大于 0；`block_opponent` 可为 0；
- `near_open_endgame`：四种 intent 都必须大于 0；
- `critical_endgame`：四种 intent 都必须大于 0。

每个策略 × 每个 phase 的 relation `none / teammate / opponent` 都必须大于 0。

每个策略的 overall reason 覆盖必须满足：

- `can_finish_now == 0`，因为一次出完已在 router 采样前跳过；
- 以下 reason 均大于 0：`weak_hand`、`stable_control`、`teammate_controls_table`、`urgent_opponent_controls_table`、`teammate_more_urgent`、`opponent_more_urgent`、`urgency_tie_block_opponent`、`opponent_urgent`、`teammate_urgent`。

这些门槛只验证路由分支在独立公开轨迹上有覆盖，不比较 intent 是否正确，也不把频率差异解释为策略收益。

### 6. 唯一判定

严格按以下顺序给出一个判定：

1. 前置条件或回归失败：`precondition_failed`；
2. 双运行、哈希、策略映射、完整性、守恒或审计证据失败：`strategy_router_coverage_benchmark_invalid`；
3. 完整性全部通过，但任一预注册样本或覆盖门槛失败：`strategy_router_coverage_insufficient`；
4. 全部门槛通过：`strategy_router_coverage_verified`。

`strategy_router_coverage_verified` 只授权下一步单独设计 K-A3a 的 intent 消费消融载体；不授权直接把 intent 接入 DeepSeek prompt、RAG、剪枝、fallback 或动作选择，不启用默认开关，也不代表动作质量或胜率提升。

### 7. 最终报告

最终报告必须包含：

- 唯一判定；
- HEAD、K-A2b1a 检查点、运行前后工作区状态；
- 四组回归命令与结果；
- 锁定参数和两次耗时；
- 审计目录、文件 bytes 与 SHA-256、canonical report SHA-256；
- 四策略的 games、opportunity/active pass、完整性和 diagnostics；
- 4 策略 × 4 phase 的 sample/available、四 intent、三 relation；
- 每个策略 overall 的完整 reason 原始计数；
- 所有预注册门槛逐项通过/失败表；
- 明确说明未修改仓库、未联网、未读取隐藏状态，且未形成动作质量或胜率结论。
