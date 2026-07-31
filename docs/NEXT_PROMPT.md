# 下一步实施提示词

## 使用说明

本提示词交给负责源码和测试实现的代理。项目规划代理只维护 `docs/*.md`。

## 当前唯一任务

实现 Step J-C3c1：evaluation-only 的战略性 pass 策略与多策略 rank 基准载体。

本轮只建立策略分布测试能力，不运行正式策略分布结论，不调整 J-C2b1 权重，不输出概率或置信度，也不接入 DeepSeek、RAG 或策略主链。

## 提示词

```text
请在 GuanDan 项目中实现 Step J-C3c1“战略性 pass 策略分布基准载体”。

开始前必须阅读：

- AGENTS.md
- docs/PROJECT_STATUS.md
- docs/PLAN.md
- docs/BELIEF_STATE.md
- docs/TESTS.md
- agents/base.py
- agents/rule_based_ai.py
- agents/card_signals.py
- agents/card_ranker.py
- agents/game_phase.py
- engine/game.py
- evaluation/rank_benchmark.py
- evaluation/ranking_metrics.py
- tests/test_rank_benchmark.py
- tests/test_ranking_metrics.py

当前基线：

- HEAD `39bd0247b9459999cdeb489703ff288eed7df791` 为 J-C3a；
- J-C3a 定向 130 项、全量 240 项测试通过；
- J-C3b 使用 seed 1000..1199 完成两次可重复正式运行；
- J-C3b 共 8719 个有效样本，无 invalid、skip 或 diagnostics；
- candidate recall 与 Top-1/Top-3 recall 无回退；
- overall Top-1 precision delta +0.007357；
- overall Top-3 precision delta +0.006385；
- overall worst-case MRR delta +0.003233；
- 唯一判定为 `retain_for_policy_diverse_validation`；
- 该结果只覆盖 RuleBasedAIAgent 的被迫 pass。

问题定义：

现有 RuleBasedAIAgent 在有非 pass 合法动作时总会出牌。因此 J-C3b
没有覆盖“面对敌方 single，明明存在合法压制动作但主动 pass”的策略行为。
J-C3c1 要构造只读取公开 observation 和 legal actions 的确定性压力策略，
并复用 J-C3a 的真值隔离和聚合能力。

范围要求：

1. 新增 `evaluation/pass_policy_benchmark.py`。
2. 新增 `tests/test_pass_policy_benchmark.py`。
3. 允许对 `evaluation/rank_benchmark.py` 做最小、向后兼容的 agent factory 扩展。
4. 如确有需要，只允许对 `evaluation/__init__.py` 做最小导出调整。
5. 不修改 `engine/`、`agents/`、CLI、RAG、DeepSeek 或 docs。
6. 不修改 J-A 至 J-C3a 的数据契约、指标定义和默认运行结果。
7. 不修改 `opponent_single_pass` 的分值或累计上限。
8. 不新增第三方依赖，不访问网络，不调用 DeepSeek。
9. 不写正式 benchmark JSON、日志或其他运行产物。
10. 不实现 J-C3c2 的正式独立种子验收、J-C3d 置信度或 Step K。

J-C3a 最小扩展：

为 `run_rank_benchmark()` 增加可选 keyword-only agent factory。

建议类型：

`Callable[[int, int], BaseAgent]`

两个参数分别为：

- 当前 game seed；
- player_id。

要求：

1. 未传 factory 时，行为必须与当前版本逐字段完全一致。
2. 默认仍为每位玩家创建现有 `RuleBasedAIAgent`。
3. 每个 seed、每位玩家只调用一次 factory。
4. 不向 factory 传递 game、GameState、真实手牌或其他隐藏信息。
5. 自定义 agent 返回值仍必须经过 `require_legal_action_id()`。
6. factory 为 evaluation 扩展点，不得暴露到 runtime 主链。

evaluation-only 策略：

新增不可访问真值的 `StrategicPassAIAgent`，可以继承 `BaseAgent`。

输入至少包括：

- `player_id`
- `strategic_pass_rate`，整数百分比 0、25、50 或 100

允许支持任意 0..100 的整数用于单元测试，但正式策略集合固定为
0 / 25 / 50 / 100。

它的 `select_action(observation, legal_actions)` 只能读取这两个公开参数。
禁止读取：

- `GuanDanGame`
- `game._state`
- `GameState` / `PlayerState`
- 真实手牌
- benchmark ground truth
- seed 对应的隐藏牌

战略性 pass 机会必须同时满足：

1. 当前桌面约束是 `single`；
2. 能从公开当前 round/history 找到本轮最近有效非 pass 领出玩家；
3. 领出玩家与当前玩家属于不同 team；
4. 当前 legal actions 中存在合法 pass；
5. 当前 legal actions 中至少存在一个非 pass 动作；
6. 公开 `step_no` 和 `player_id` 格式有效。

以下情况不得计为机会：

- 队友领出；
- 非 single；
- 新 round 中没有可关联的非 pass；
- round 回退或上下文无法验证；
- 仅有 pass；
- 没有 pass；
- observation/history/team 字段缺失或格式错误。

不要自己推断牌型合法性。桌面牌型和动作候选均以公开 payload 为准。

确定性门控：

1. 使用公开 `step_no`、`player_id` 和固定整数算式生成 0..99 的 gate。
2. 不使用 Python `hash()`，避免进程随机化。
3. 不使用随机模块或系统时间。
4. 不使用 seed 计算 gate，避免 seed 与隐藏发牌产生不必要关联。
5. 当 `gate < strategic_pass_rate` 时选择合法 pass。
6. 未命中 gate 时调用现有 `RuleBasedAIAgent.select_action()`。
7. 不复制或重写 RuleBasedAIAgent 的动作排序。
8. rate=0 时从不主动 pass，动作轨迹必须与 RuleBasedAIAgent 完全相同。
9. rate=100 时每个合格机会都选择 pass。

策略 agent 公开计数：

- `strategic_pass_opportunity_count`
- `strategic_pass_count`

计数规则：

1. 每个合格机会 opportunity 加 1；
2. 只有门控命中并实际返回 pass action ID 时 pass count 加 1；
3. `0 <= strategic_pass_count <= opportunity_count`；
4. rate=0 时 pass count 为 0；
5. rate=100 时两个计数相等；
6. 被迫 pass 不计入 strategic pass count。

建议报告：

- frozen/slots `PolicyVariantRankReport`
- frozen/slots `PassPolicyBenchmarkReport`
- `run_pass_policy_benchmark(...)`

PolicyVariantRankReport 至少包含：

- policy_name
- strategic_pass_rate
- strategic_pass_opportunity_count
- strategic_pass_count
- rank_benchmark

PassPolicyBenchmarkReport 至少包含：

- requested_policy_count
- by_policy

固定策略命名：

- rate 0：`forced_only`
- rate 25：`strategic_pass_25`
- rate 50：`strategic_pass_50`
- rate 100：`strategic_pass_100`

多策略运行：

1. 默认 rates 固定为 `(0, 25, 50, 100)`。
2. 每个 rate 必须调用一次独立的 `run_rank_benchmark()`。
3. 每个策略必须创建全新 game 和 agent，不能共享对局、计数器或推断状态。
4. 所有策略使用完全相同的 seeds 和 benchmark 参数。
5. 保留输入 seed 顺序，但报告不得包含 seed 列表。
6. rate 列表必须非空、唯一；每项是非 bool 的 0..100 整数。
7. 固定策略名不得因序列化顺序变化。
8. 相同输入重复运行报告必须完全一致。

报告安全：

1. 所有报告使用 `@dataclass(frozen=True, slots=True)`。
2. 映射字段不可变，不暴露可变内部状态。
3. 每层提供 JSON 友好的 `to_dict()`。
4. `json.dumps(..., allow_nan=False)` 必须成功。
5. 报告不得包含：
   - seed 值或逐 seed 结果
   - observation/history 明细
   - 逐步动作
   - ground truth hands
   - 逐玩家真实 token/rank
   - 可逆隐藏牌信息
6. 允许包含策略名、rate、机会/主动 pass 聚合计数和现有安全 RankBenchmarkReport。

测试要求：

`tests/test_pass_policy_benchmark.py` 至少覆盖：

1. 空 rates、重复 rates、bool、负数、超过 100 和非整数被拒绝；
2. rate 0/25/50/100 的稳定策略名；
3. enemy single + pass + 非 pass 动作被识别为机会；
4. teammate single 不计机会；
5. 非 single 不计机会；
6. 孤立或跨 round 的历史不计机会；
7. 仅 pass 不计战略机会；
8. 没有 pass 不计机会；
9. malformed observation/history/team/step 不抛异常且不计机会；
10. rate=0 每次回退 RuleBasedAIAgent，主动 pass 数为 0；
11. rate=100 每个合格机会选择合法 pass，机会数等于主动 pass 数；
12. 25%/50% 门控只依赖公开 step/player，固定输入重复结果一致；
13. 门控不使用 Python hash、随机数、时间或 seed；
14. 未命中门控时动作与 RuleBasedAIAgent 相同；
15. 所有返回 action ID 来自传入 legal actions；
16. 被迫 pass 不计 strategic pass；
17. J-C3a 未传 factory 时固定 seed 报告与修改前基线一致；
18. rate=0 的完整对局轨迹/RankBenchmarkReport 与默认 RuleBasedAI 完全一致；
19. factory 每 seed/player 只调用一次；
20. 多策略运行使用独立 agent 和独立计数；
21. opportunity/pass 聚合计数正确且满足上下界；
22. `by_policy` 稳定包含请求的全部策略；
23. 相同 seeds/参数重复运行报告完全一致；
24. `to_dict()` 可 JSON 序列化且没有 NaN/Infinity；
25. 报告不含 seed、逐动作、observation、真实手牌/token/rank 明细；
26. 输出不可变，运行不修改输入；
27. `StrategicPassAIAgent` 不访问 `_state` 或导入引擎状态模型；
28. `agents/`、CLI、RAG、DeepSeek 不新增对 `evaluation` 的反向导入。

测试应优先使用小型公开 observation/legal action fixtures验证策略边界。
真实对局集成只使用极少 seed 和较小样本上限，避免在单元测试中运行正式多策略 corpus。

兼容要求：

- `tests/test_rank_benchmark.py` 必须保持通过；
- `tests/test_ranking_metrics.py` 必须保持通过；
- `tests/test_card_ranker.py` 必须保持通过；
- `tests/test_card_signals.py` 必须保持通过；
- `tests/test_belief_metrics.py` 必须保持通过；
- `tests/test_card_allocations.py` 必须保持通过；
- `tests/test_card_constraints.py` 必须保持通过；
- `tests/test_card_belief.py` 必须保持通过；
- `tests/test_card_tracker.py` 必须保持通过；
- `tests/test_game_phase.py` 必须保持通过；
- 全量 unittest 必须无回归。

完成后运行：

python -m unittest tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q
git diff --check

最终报告必须包含：

- 修改文件；
- J-C3a agent factory 的向后兼容方式；
- 战略性 pass 机会定义；
- 公开信息边界和确定性 gate 算式；
- 0/25/50/100 策略行为；
- 机会数与主动 pass 数口径；
- 报告安全边界；
- 定向和全量测试数量；
- 未解决风险；
- 明确说明 J-C3c1 只建立策略分布基准载体，尚未运行正式独立种子策略分布验收、校准概率/置信度、接入策略或提升胜率。
```

## 完成判定

只有同时满足以下条件，Step J-C3c1 才能标记完成：

- evaluation-only 策略只读取公开 observation 和 legal actions；
- 战略机会严格限定为敌方 single 且同时存在 pass/非 pass；
- rate=0 与现有 RuleBasedAI 完全等价；
- rate=100 在所有合格机会主动 pass；
- 25%/50% gate 确定、稳定且不依赖 seed/隐藏牌；
- 多策略对局和计数互相隔离；
- 默认 J-C3a 报告不变；
- 报告不泄露 seed、轨迹或真值；
- 未修改 engine、runtime agents、RAG、DeepSeek、CLI 或 docs；
- 现有 240 项测试无回归；
- 实施代理向项目规划代理报告实际测试结果。
