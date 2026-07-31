# 下一步实施提示词

## Step J-D1c3a：策略分布多样性 marginal corpus 载体

请在 GuanDan 项目中实现 Step J-D1c3a。目标是复用现有 evaluation-only `StrategicPassAIAgent` 与 `run_marginal_corpus()`，为 forced-only、25%、50%、100% strategic-pass 轨迹分别生成隔离的组合边际校准报告。

本步骤实现多策略包装器并运行开发容量试验，不做正式多策略校准，不生成 runtime confidence。

## 一、开始前检查

先阅读：

- `evaluation/pass_policy_benchmark.py`
- `evaluation/marginal_corpus.py`
- `evaluation/marginal_benchmark.py`
- `evaluation/marginal_metrics.py`
- `tests/test_pass_policy_benchmark.py`
- `tests/test_marginal_corpus.py`
- `docs/PROJECT_STATUS.md`

确认：

- J-D1c2c 判定为 `retain_for_policy_diverse_calibration`；
- 该判定只覆盖默认 RuleBasedAI；
- `run_marginal_corpus()` 已提供 keyword-only `agent_factory(seed, player_id)`；
- `StrategicPassAIAgent` 只读取公开 observation 与 legal actions；
- rate 0 回退 RuleBasedAI，rate 100 在所有合格机会主动 pass。

开始前运行：

```bash
python -m unittest tests.test_marginal_corpus tests.test_marginal_benchmark tests.test_marginal_metrics tests.test_rank_benchmark tests.test_card_allocations tests.test_belief_metrics tests.test_ranking_metrics tests.test_card_ranker tests.test_pass_policy_benchmark tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q
```

当前基线为定向 179 项、全量 303 项通过。若不同，先报告实际状态，不要覆盖不明改动。

## 二、允许修改范围

只新增：

- `evaluation/marginal_policy_corpus.py`
- `tests/test_marginal_policy_corpus.py`

不要修改：

- `engine/`
- `agents/`
- 现有 evaluation 模块
- strategic-pass 策略或 gate
- marginal collector、metrics、aggregator
- RAG、DeepSeek、CLI
- docs
- 依赖配置

不要新增第三方依赖。

## 三、公开接口

实现：

```python
run_marginal_policy_corpus(
    seeds: Sequence[int],
    *,
    strategic_pass_rates: Sequence[int] = (0, 25, 50, 100),
    current_level_rank: str = "2",
    max_steps: int = 5000,
    max_samples_per_game: int = 128,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
) -> MarginalPolicyCorpusReport
```

每个 rate 都调用一次独立的 `run_marginal_corpus()`。

## 四、策略命名与顺序

固定命名：

```text
0   -> forced_only
25  -> strategic_pass_25
50  -> strategic_pass_50
100 -> strategic_pass_100
```

要求：

- 输出 mapping 顺序与调用方传入 rates 顺序一致；
- 默认顺序固定为 0、25、50、100；
- rates 必须是非空、无重复、非 bool 整数 Sequence；
- 每个 rate 位于 0..100；
- 非法 rates 在启动任何 corpus 前抛出 `ValueError`。

不要导入或依赖 `pass_policy_benchmark.py` 的私有命名/校验 helper；可在新模块中实现小型本地校验。`StrategicPassAIAgent` 本身直接复用。

## 五、策略隔离

对每个 rate：

1. 创建新的 `created_agents` 列表；
2. factory 每次返回全新的 `StrategicPassAIAgent`；
3. 调用独立的 `run_marginal_corpus()`；
4. corpus 完成后汇总该策略所有 agent 的：
   - `strategic_pass_opportunity_count`
   - `strategic_pass_count`
5. 构造该策略独立报告；
6. 不把 game、agent、计数器或报告列表复用到下一个 rate。

每个 `(rate, seed, player_id)` 只创建一个 agent。

## 六、建议报告结构

### 1. PolicyVariantMarginalReport

冻结、slots dataclass，至少包含：

```python
strategic_pass_rate: int
strategic_pass_opportunity_count: int
strategic_pass_count: int
corpus: MarginalCorpusReport
```

`to_dict()` 必须展开为 JSON 友好结构。

### 2. MarginalPolicyCorpusReport

冻结、slots dataclass，至少包含：

```python
requested_policy_count: int
by_policy: Mapping[str, PolicyVariantMarginalReport]
```

要求：

- mapping 不可变；
- 不保留 seeds、agent、游戏或逐样本对象；
- 不跨策略平均 calibration 指标；
- 不增加一个掩盖单策略失败的 overall-across-policy 指标；
- `to_dict()` 顺序稳定、JSON 友好。

## 七、行为不变量

每个策略满足：

```text
0 <= strategic_pass_count
  <= strategic_pass_opportunity_count
```

额外要求：

- rate 0：`strategic_pass_count == 0`；
- rate 100：`strategic_pass_count == strategic_pass_opportunity_count`；
- forced-only corpus 必须与同参数默认 `run_marginal_corpus()` 完全相等；
- forced pass 不计入 strategic pass count；
- opportunity 和主动 pass 只由现有 `StrategicPassAIAgent` 统计；
- 包装器不得重新判断 pass 机会。

## 八、参数透传

以下参数原样传给每个独立 corpus：

- seeds
- current level rank
- max steps
- per-game sample limit
- external card limit
- search node limit
- solution limit

不要：

- 为不同策略使用不同 seed；
- 根据前一策略结果改变后续参数；
- 因某策略样本较少而补采；
- 使用 truth 调整 agent 或 gate；
- 复用一个策略的 corpus 作为另一个策略结果。

## 九、确定性与安全

同一参数双运行必须：

- 完整 `MarginalPolicyCorpusReport` 相等；
- `to_dict()` 相等；
- canonical JSON SHA-256 相等；
- 四个策略各自 corpus 相等；
- opportunity/pass 计数相等；
- JSON 无 NaN/Infinity。

报告不得包含：

- seed 列表；
- sample ID；
- observation/history；
- 玩家级预测；
- truth hand/token/rank；
- agent 对象或逐 agent 计数。

## 十、最低测试覆盖

在 `tests/test_marginal_policy_corpus.py` 至少覆盖：

1. 默认策略名称与顺序；
2. 自定义 rate 顺序稳定；
3. 空 rates 拒绝；
4. 重复 rates 拒绝；
5. bool、负数、超过 100、非整数拒绝；
6. 非 Sequence/string rates 拒绝；
7. 每个策略调用独立 corpus；
8. 每个 rate/seed/player 只创建一次 agent；
9. 不同策略不共享 agent；
10. rate 0 strategic pass count 为 0；
11. rate 100 pass count 等于 opportunity；
12. 所有策略满足 pass 不超过 opportunity；
13. forced-only corpus 等于默认 marginal corpus；
14. collector 参数完整透传；
15. 一个策略失败时显式传播异常，不返回部分顶层报告；
16. report/dataclass frozen + slots；
17. mapping 不可变；
18. `to_dict()` 可由 `json.dumps(..., allow_nan=False)` 序列化；
19. payload 不包含 seed/sample/observation/player/truth/token/rank 明细；
20. 固定小 seed 双运行报告和 hash 相等；
21. 四策略 corpus 的游戏、样本和 bucket 计数各自可审计；
22. 包装器不输出跨策略平均 calibration 指标；
23. runtime agents、CLI 和 RAG 不导入新 evaluation 模块。

测试使用 mock 或小 seed，不运行正式多策略 corpus。

## 十一、开发容量试验

实现和全量测试通过后，使用以下开发参数完整运行两次：

```text
seeds = 60..69
games per policy = 10
rates = 0, 25, 50, 100
current_level_rank = 2
max_steps = 5000
max_samples_per_game = 128
max_external_cards = 12
max_search_nodes = 1,000,000
max_solutions = 100,000
```

记录：

- 两次总耗时；
- 两份完整报告是否相等；
- canonical JSON SHA-256；
- 每个策略 opportunity、active pass、实际 pass/opportunity 比例；
- 每个策略 requested/completed/incomplete；
- eligible/evaluated/valid/invalid/skipped；
- diagnostics；
- 三个 external bucket 的 samples、valid、rank pairs；
- overall 与三桶的 Brier skill、ECE、raw MCE、supported MCE、certainty error；
- 四策略是否都覆盖三个 external bucket。

开发容量要求：

- 每个策略 10/10 局完成；
- invalid = 0；
- skipped = 0；
- diagnostics 为空；
- 三个 external bucket 均非空；
- forced-only 主动 pass 为 0；
- rate 25/50/100 都有 opportunity；
- rate 25/50 有主动 pass；
- rate 100 pass = opportunity；
- 实际主动 pass 比例满足 `rate25 < rate50 < rate100`；
- 两次完整报告和 hash 相等。

若满足，判定：

```text
policy_diversity_capacity_verified
```

该判定只允许预注册 J-D1c3b，不表示任一策略已通过正式校准。

## 十二、开发指标边界

开发 seed 只用于：

- 验证四策略容量；
- 检查行为梯度；
- 估算正式运行耗时；
- 确认各外部牌数桶有样本；
- 观察是否需要更高样本量。

不得用开发结果：

- 调整组合边际；
- 选择有利策略；
- 删除表现差的桶；
- 声称正式校准通过；
- 生成 runtime confidence；
- 接入策略或宣称胜率提升。

## 十三、验证命令

先运行：

```bash
python -m unittest tests.test_marginal_policy_corpus tests.test_marginal_corpus tests.test_marginal_benchmark tests.test_marginal_metrics tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_card_allocations tests.test_belief_metrics tests.test_ranking_metrics tests.test_card_ranker tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
```

再运行：

```bash
python -m unittest discover -q
git diff --check
```

检查边界：

```bash
rg -n "marginal_policy_corpus" agents cli rag
```

预期 runtime 无导入。

## 十四、完成报告

报告必须包含：

- 修改文件；
- 两层 dataclass 与策略命名；
- agent/corpus 隔离方式；
- opportunity/pass 行为不变量；
- forced-only 与默认 corpus 一致性；
- 定向、全量测试和 `git diff --check`；
- 开发双运行耗时、hash；
- 四策略完整计数、行为计数、桶覆盖和描述性校准指标；
- 唯一开发判定；
- 明确说明未运行正式策略分布校准、未生成 runtime confidence、未接入策略或证明胜率提升。

## 十五、完成门槛

只有同时满足以下条件，Step J-D1c3a 才能标记完成：

- 四策略独立运行且无共享状态；
- rate 0/100 行为边界正确；
- forced-only corpus 与默认 collector 一致；
- 报告不可变、确定、无真值明细；
- 开发双运行报告和 hash 一致；
- 四策略容量与行为梯度满足要求；
- 全量测试通过；
- runtime/engine/现有评测语义未修改；
- 未把开发试跑解释为正式校准。
