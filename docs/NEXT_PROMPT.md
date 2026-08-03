# 下一步实施提示词

## Step K-A2b1：离线路由分布载体与开发容量验证

请在 GuanDan 项目中完成 Step K-A2b1。本步只在 `evaluation/` 建立可重复的策略路由分布载体，并运行小型双运行开发容量试验。不修改 runtime，不让 intent 影响动作，不评价策略质量或胜率。

## 一、当前基线

K-A2a 已完成，唯一判定：

```text
strategy_router_shadow_verified
```

已验证：

- `DeepSeekAIAgent` 具有严格布尔、默认关闭的 `strategy_router_shadow_enabled`；
- `last_strategy_intent` 每次决策重置，只作非展示审计字段；
- only-pass、一次出完和开局公式命中均跳过 router；
- 普通模型链传入同一 phase、原始 legal actions 并复用已有手牌评估；
- router available/unavailable 或异常均不改变 prompt、RAG、剪枝、fallback、action 或 decision source；
- 定向 25 项、相关 100 项、全量 396 项通过；
- 未调用网络或读取隐藏状态。

当前未知四种 intent 在不同阶段和不同公开策略轨迹中的自然分布。K-A2b1 的目标是获得可审计的原始计数，为 K-A2b2 预注册独立 seed 正式覆盖门槛提供依据。

## 二、允许修改范围

只允许新增：

- `evaluation/strategy_router_benchmark.py`
- `tests/test_strategy_router_benchmark.py`

不得修改：

- `agents/`
- `engine/`
- `cli/`
- `rag/`
- `config.py`
- 其他 `evaluation/` 模块
- 其他测试
- `docs/`
- `.env` / `.env.example`

不得新增依赖。

## 三、公开 API

在 `evaluation/strategy_router_benchmark.py` 中提供：

- `StrategyRouteBucket`
- `PolicyStrategyRouteReport`
- `StrategyRouterBenchmarkReport`
- `run_strategy_router_benchmark(...)`

建议签名：

```python
run_strategy_router_benchmark(
    seeds: Sequence[int],
    *,
    current_level_rank: str = "2",
    strategic_pass_rates: Sequence[int] = (0, 25, 50, 100),
    max_steps: int = 5000,
    max_samples_per_phase_per_game: int = 128,
) -> StrategyRouterBenchmarkReport
```

所有输入严格校验：

- `seeds` 是非空、无重复、非 bool 整数序列；
- `current_level_rank` 是引擎支持的普通级牌；
- rates 是非空、无重复、非 bool 的 0..100 整数序列；
- `max_steps` 和每阶段每局样本上限是非 bool 正整数。

输入错误抛 `ValueError`，不开始部分对局。

## 四、策略语料

复用 `evaluation.pass_policy_benchmark.StrategicPassAIAgent`，默认四个策略：

- `forced_only` / rate 0
- `strategic_pass_25` / rate 25
- `strategic_pass_50` / rate 50
- `strategic_pass_100` / rate 100

要求：

1. 每个 rate 独立创建 game、四个 agent、sample ID 集合、计数器和聚合器。
2. 同一 rate 内每个 `(seed, player_id)` 只创建一个 agent。
3. 每个 agent 返回值都必须经过已有 `require_legal_action_id()` 校验后再传给 `game.step()`。
4. rate 顺序按调用方输入保存，但不得依赖 JSON object 键迭代顺序验收策略映射。
5. 顶层报告使用有序 policy tuple/list 序列化，每项同时保留 `policy_name` 和 `strategic_pass_rate`，避免重复之前 canonical JSON 键序假阴性。

记录每个策略的 strategic-pass opportunity、active pass 和实际比例所需原始计数。

## 五、样本口径

每个引擎 step 只处理当前公开 observer 一次。先取：

- `observation = game.observe()`
- `legal_actions = game.legal_actions()`

跳过顺序必须固定，并尽量与 K-A2a runtime shadow 边界一致：

1. 若是 only-pass，记录 `only_pass_skipped_count`，不路由；
2. 若存在一次出完的合法非 pass 动作，记录 `finishing_skipped_count`，不路由；
3. 计算一次统一 `GamePhaseContext`；
4. `opening` 记录 `opening_skipped_count`，不路由；
5. `midgame`、`endgame`、`near_open_endgame`、`critical_endgame` 为互斥目标阶段；
6. 使用 `(seed, step_no, observer_player_id)` 作为该策略内部 sample ID，重复样本只记 diagnostics，不重复评估；
7. 样本上限按“每局、每阶段”单独计数，避免 midgame 先耗尽整局配额；
8. 合格样本只调用一次 `evaluate_hand(observation, legal_actions)` 和一次 `route_strategy_intent(...)`；
9. router 必须收到同一 phase 实例与原始 legal actions，不调用剪枝、RAG、confidence 或 DeepSeek。

不得读取 `record.txt`。第 2/16/20 轮公开 fixture 已由 K-A1/A1a 单元测试锁定，本步不复制原日志。

## 六、聚合契约

### `StrategyRouteBucket`

每个 bucket 至少包含：

- bucket 名称：`overall` 或四个 phase 之一；
- `sample_count`；
- `available_count`；
- `unavailable_count`；
- `invalid_count`：仅评分/router 抛异常或返回错误类型等载体失败；
- 四种 intent 的固定键计数；
- reason code 计数；
- table leader relation 计数：`none`、`teammate`、`opponent`；
- free-lead / follow 计数；
- weak / non-weak 计数；
- 规范化 diagnostic category 计数。

守恒要求：

- `sample = available + unavailable + invalid`；
- available 样本的 intent 总数等于 available；
- available 样本的 relation、free/follow、weak/non-weak 各自总数等于 available；
- 当前合法 router 每个 available 样本只有一个 reason，reason 总数等于 available；
- overall 必须由四个 phase 的原始计数相加得到，不平均阶段比例。

### `PolicyStrategyRouteReport`

每个策略至少包含：

- policy name / rate；
- strategic-pass opportunity / active pass；
- requested / completed / incomplete games；
- observed turn count；
- opening / only-pass / finishing skip 计数；
- eligible / evaluated / duplicate / sample-limit-skipped 计数；
- overall bucket；
- 固定顺序的四个 phase bucket；
- 顶层 diagnostics。

守恒要求：

```text
observed_turn_count = only_pass_skipped_count + finishing_skipped_count + opening_skipped_count + eligible_sample_count
```

```text
eligible_sample_count = duplicate_sample_count + sample_limit_skipped_count + evaluated_sample_count
```

`evaluated_sample_count == overall.sample_count`，四个 phase bucket 的 sample 之和也必须等于 overall。

### `StrategyRouterBenchmarkReport`

顶层报告保留：

- 有序 policy report tuple；
- 必要的固定参数元数据，但不保留 seed 列表；
- JSON 友好的 `to_dict()`。

所有 report/bucket 使用 frozen/slots；公开 mapping 不可变。不得保留：

- seed 列表或 sample ID；
- observation / history / legal action；
- player ID 或逐玩家统计；
- 手牌、token、rank 明细；
- prompt、action ID、模型响应或真值。

## 七、diagnostics

至少覆盖：

- `duplicate_sample`
- `sample_limit_reached`
- `max_steps_reached`
- `invalid_observer`
- `invalid_step_no`
- `hand_evaluation_error`
- `router_error`
- `invalid_router_result`
- router 自身 unavailable diagnostics 的规范化 category

diagnostics 按冒号前 category 聚合；同一样本内同类只计一次。异常必须转为 invalid 样本和诊断，不泄露异常文本或中断其他独立对局。

## 八、测试要求

`tests/test_strategy_router_benchmark.py` 至少覆盖：

1. 全部输入严格校验，包括 bool、重复 seed/rate、空序列、非法级牌和非正上限。
2. report/bucket frozen/slots、mapping 不可变、`to_dict()` 可 JSON 序列化。
3. 调用方 rate 顺序保留，policy name/rate 显式匹配，不依赖 mapping 键序。
4. 四策略各自创建独立 game 和 agent；rate 0 主动 pass 为 0，rate 100 主动 pass 等于 opportunity。
5. 所有推进动作均来自当前 legal actions。
6. only-pass、一次出完、opening 跳过顺序和计数正确，不调用评分/router。
7. 合格样本的 phase 只计算一次，评分/router 各一次，router 收到原始 legal actions 和同一 phase。
8. available 的四 intent、reason、relation、free/follow 和 weak/non-weak 聚合正确。
9. unavailable 与多 diagnostics 按样本内类别去重。
10. 评分异常、router 异常、错误类型返回均记 invalid，不泄露异常文本。
11. 重复样本、每阶段样本上限与步数上限 diagnostics。
12. policy 内部、phase-to-overall 和各分类计数守恒。
13. 相同 seed/参数双运行 report 和 `to_dict()` 完全相等，canonical JSON SHA-256 一致。
14. 报告不含 seed、sample ID、observation、history、action、player、hand、token、rank、prompt 或 truth 明细。
15. 源码边界扫描不读取 network、DeepSeek、API key、`.env`、ground truth 或 `game._state`。

测试可使用最小 fake game/router 验证边界，但至少要有一个真实 `GuanDanGame` 固定 seed 的双运行一致性测试。

## 九、开发容量试验

代码和回归通过后，运行两次完全相同的开发试验：

- seeds：`200..209`（10 局）
- rates：`(0, 25, 50, 100)`
- 级牌：`2`
- `max_steps=5000`
- `max_samples_per_phase_per_game=128`

两次都在内存中独立构建报告，不把运行产物写入仓库。报告：

- 两次耗时；
- report、`to_dict()` 和 canonical JSON 是否相等；
- canonical SHA-256；
- 每策略对局完成数、opportunity / active pass；
- observed/skip/eligible/evaluated/available/unavailable/invalid/duplicate/sample-limit 计数；
- 每策略×每阶段的 sample、available/unavailable/invalid；
- 每策略×每阶段的四 intent、reason 和 table relation 原始计数；
- 所有 diagnostics。

开发容量门槛只检查载体可用性：

1. 双运行完全一致；
2. 四策略均 10/10 完成，无 incomplete；
3. invalid、duplicate、sample-limit 和 diagnostics 均为 0；
4. available = evaluated，unavailable = 0；
5. 每个策略的四个 phase bucket 都至少有 1 个 available 样本；
6. rate 0 主动 pass=0，rate 100 主动 pass=opportunity，且四策略实际主动 pass 比例严格递增；
7. 全部计数守恒成立。

不要要求每个 policy/phase 都覆盖四种 intent，也不要为 intent 比例设收益门槛。稀有 intent 或零计数将用于 K-A2b2 设计分层和样本量，不在本步被解释为策略失败。

## 十、验证命令

先运行：

```bash
python -m unittest tests.test_strategy_router_benchmark -q
```

再运行相关回归：

```bash
python -m unittest tests.test_strategy_router_benchmark tests.test_strategy_router_shadow tests.test_strategy_router tests.test_pass_policy_benchmark tests.test_game_phase tests.test_hand_evaluator -q
```

最后运行：

```bash
python -m unittest discover -q
git diff --check
```

并用 `rg` 扫描新模块与 runtime 的依赖边界。

## 十一、唯一判定

按以下顺序只给出一个判定：

1. API、输入校验、策略隔离、样本口径、聚合守恒、不可变/JSON、真实对局推进、边界扫描或回归任一失败：

```text
strategy_router_distribution_harness_invalid
```

2. 载体通过，但开发双运行不一致、对局不完整、出现 invalid/unavailable/diagnostics/截断，或某策略的某个 phase 无 available 样本：

```text
strategy_router_distribution_capacity_insufficient
```

3. 载体和开发容量门槛全部通过：

```text
strategy_router_distribution_capacity_verified
```

通过只授权 K-A2b2 预注册独立 seed 正式覆盖验收。它不授权 intent 进入 prompt、RAG、剪枝或动作，不代表路由质量或胜率提升。

## 十二、最终报告

完成后报告：

1. 修改文件；
2. 公开 API 与不可变/JSON 契约；
3. 策略隔离与样本口径；
4. skip、eligible、available/unavailable/invalid 定义；
5. 所有计数守恒；
6. 定向、相关和全量回归；
7. 开发双运行耗时、等价性和 SHA-256；
8. 每策略的完整性、pass 行为与 skip 计数；
9. 每策略×每阶段的 sample、availability、intent、reason 和 relation 计数；
10. diagnostics、`git diff --check` 与边界扫描；
11. 唯一开发判定；
12. 明确说明未修改 runtime、未读取真值或隐藏状态、未调用网络、未让 intent 影响动作，未形成策略收益或胜率结论。

完成后停止，不修改 docs，不扩展到 K-A2b2。
